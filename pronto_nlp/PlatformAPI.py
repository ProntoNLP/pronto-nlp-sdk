import copy
import sys
import urllib.request
from typing import Union, List, Dict, AsyncGenerator
import requests
import math
from collections import defaultdict
from itertools import takewhile
from tqdm import tqdm
from multiprocessing import Pool
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
import asyncio
import websockets
import json
from aiofiles import tempfile
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
import os
import aiohttp
import aiofiles


def SignIn(user, password):
    organization = "dev"
    M = re.match(r'^(.*?):(.*)$', user)
    if M:
        organization = M.group(1)
        user = M.group(2)
    authURL = ("https://server-staging.prontonlp.com/token" if (organization == "dev" or organization == "staging") else
               "https://server-prod.prontonlp.com/token")

    requestObj = {"email": user, "password": password, "organization": organization}
    body = json.dumps(requestObj, ensure_ascii=True).encode('ascii')
    request = urllib.request.Request(authURL, data=body,
                                     headers={"Content-Type": "application/json",
                                              "pronto-granted": "R$w#8k@Pmz%2x2Dg#5fGz"})
    response = urllib.request.urlopen(request)
    if response.status == 200:
        result = response.read().decode('utf-8')
        if not result.startswith('{'):
            print("Authentication successful")
            return result


def PerformRequest(headers, url, request_obj=None, method='POST', check_response=True, encode_url=False):
    if encode_url and request_obj:
        encoded_params = urlencode(request_obj)
        url = f"{url}?{encoded_params}"

    if method.upper() == 'POST':
        body = json.dumps(request_obj)
        response = requests.post(url, headers=headers, data=body)
    elif method.upper() == 'GET':
        if request_obj is None:
            response = requests.get(url, headers=headers)
        else:
            response = requests.get(url, headers=headers, params=request_obj)
    elif method.upper() == 'DELETE':
        body = json.dumps(request_obj)
        response = requests.delete(url, headers=headers, data=body)
    else:
        raise ValueError("Invalid method. Supported methods are 'POST' and 'GET'")

    if check_response:
        if response.status_code == 504:
            response = requests.post(url, headers=headers, data=body, timeout=120)

        if response.status_code != 200:
            print(f"Request Failed. Status code: {response.status_code}, Response: {response.text}")

    try:
        if url == 'https://server-prod.prontonlp.com/reflect/convert':
            return response
        return response.json()
    except json.JSONDecodeError as e:
        return response
    except ValueError as e:
        return response


def _strip_file_suffix(filename):
    return os.path.splitext(filename)[0]


def _safe_get(d, key, default=None):
    try:
        return d[key]
    except KeyError:
        return default


def _get_dict_record(records, key, value):
    """
    Finds the first dictionary in a list of dictionaries where the specified key has the given value.

    Parameters:
    records (list): A list of dictionaries to search through.
    key (str): The key to search for.
    value: The value to match with the key.

    Returns:
    dict or None: The first dictionary that matches the key-value pair, or None if no match is found.
    """
    for record in records:
        if key in record and record[key] == value:
            return record
    return None


def _chunk_list(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _is_valid_date_format(date_string):
    try:
        # Try to parse the date string in the YYYY-MM-DD format
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        # If a ValueError is raised, the format is incorrect
        return False


class ProntoWebSocketClient:
    def __init__(self, base_uri, authToken, result_callback, reconnect_interval=5):
        self.base_uri = base_uri
        self.authToken = quote(authToken)
        self.uri = f"{self.base_uri}?token={self.authToken}"
        self.result_callback = result_callback
        self.reconnect_interval = reconnect_interval
        self.websocket = None
        self.running = True

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
        except Exception as e:
            print(f"Failed to connect: {e}")
            await asyncio.sleep(self.reconnect_interval)
            await self.connect()

    async def listen(self):
        while self.running:
            try:
                if self.websocket is None or self.websocket.closed:
                    await self.connect()
                message = await self.websocket.recv()
                result = await self.process_message(message)
                if result:
                    yield result
            except ConnectionClosedError as e:
                print(f"Connection closed with error: {e}")
                self.websocket = None
                await asyncio.sleep(self.reconnect_interval)
            except ConnectionClosedOK:
                print("Connection closed normally")
                self.running = False
            except Exception as e:
                print(f"An error occurred: {e}")
                await asyncio.sleep(self.reconnect_interval)

    async def process_message(self, message):
        try:
            data = json.loads(message)
            if not data.get('completed', False):
                print(f"An error occurred when retrieving results for fileKey: {data['fileKey']}")
                return None
            data['status'] = 'Completed'
            processed_result = await self.result_callback(data)
            return processed_result
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON message: {e}")
        except Exception as e:
            print(f"Failed to process message: {e}")

    async def close(self):
        self.running = False
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()


async def analyze_docs_websocket(base_uri, authToken, result_callback, expected_results):
    res_cntr = 0
    client = ProntoWebSocketClient(base_uri, authToken, result_callback)
    async for result in client.listen():
        yield result
        res_cntr += 1
        if res_cntr >= expected_results:
            break
    await client.websocket.close()


class ProntoPlatformAPI:
    def __init__(self, user, password):
        self._request_meta_map = dict()
        self._URL_Platform_Doc_Upload = "https://server-prod.prontonlp.com/reflect/documents"
        self._URL_Platform_Doc_Analyze = "https://server-prod.prontonlp.com/reflect/analyze-document"
        self._URL_Platform_Doc_Results = "https://server-prod.prontonlp.com/reflect/results"
        self._URL_Doc_Results_WebSocket = "wss://socket-prod.prontonlp.com/"

        self._URL_Platform_Vector_Search = "https://server-prod.prontonlp.com/get-vector-search-results"
        self._URL_Platform_Result_Filters = "https://server-prod.prontonlp.com/get-filters"
        self._URL_Platform_Result_Datas = "https://server-prod.prontonlp.com/get-sentences"

        self._URL_Platform_Watchlist = "https://server-prod.prontonlp.com/watchlists"
        self._URL_Get_Models_Events = "https://server-prod.prontonlp.com/models/get-models-events"
        self._URL_Get_Fief_Event_Rules = "https://server-prod.prontonlp.com/event-rules"
        self._URL_Create_Fief_Model = "https://server-prod.prontonlp.com/save-user-model"
        self._URL_Delete_Fief_Model = "https://server-prod.prontonlp.com/delete-user-model"
        self._URL_Create_Fief_Event = "https://server-prod.prontonlp.com/save-user-event"
        self._URL_Delete_Fief_Event = "https://server-prod.prontonlp.com/delete-user-event"
        self._URL_Create_Fief_Pattern = ""
        self._URL_Delete_Fief_Pattern = "https://server-prod.prontonlp.com/delete-user-pattern"
        self._URL_Get_Meta_Data = "https://server-prod.prontonlp.com/get-metadata-results"

        self._URL_Paltform_Topic_Research_Results = "https://server-prod.prontonlp.com/researches/topic"
        self._URL_Paltform_Topic_Research = "https://server-prod.prontonlp.com/get-research-results"
        self._URL_Convert_Pdf_to_Text = "https://server-prod.prontonlp.com/reflect/convert"
        self._platform_corpus_map = {'transcripts': 'S&P Transcripts', 'sec': 'SEC Filings',
                                     'nonsec': 'Non-SEC Filings'}
        self._user, self._password = user, password
        self._authToken = None
        self._base_headers = None
        self._refresh_authToken()
        self.doc_list = list()
        self.models = dict()
        self.get_model_list()

    def _refresh_authToken(self):
        self._authToken = SignIn(self._user, self._password)
        self._base_headers = {"Content-Type": "application/json", "Authorization": self._authToken,
                             "pronto-granted": "R$w#8k@Pmz%2x2Dg#5fGz"}

    def get_doc_list(self, refresh: bool = True) -> List:
        if self.doc_list and not refresh:
            return self.doc_list
        if self._authToken is None:
            self._refresh_authToken()
        requestResult = PerformRequest(self._base_headers, self._URL_Platform_Doc_Upload, method='GET')
        docs_sorted = sorted(requestResult['Items'], key=lambda x: x['lastRun'], reverse=True)
        self.doc_list = docs_sorted
        print(f"Found {len(self.doc_list)} documents")
        return self.doc_list

    @staticmethod
    def _organize_fief_model_response(data_dict):
        organized_data = {}
        for modtype, mods in data_dict.items():
            pref = ""
            if modtype == 'llm':
                pref = 'LLM'
            for modname, modevents in mods.items():
                organized_data[f"{pref}{os.path.basename(modname)}"] = {'EventTypes': modevents['EventTypes'], 'modelPath': f"{pref}{modname}"}
        return organized_data

    def get_model_list(self, refresh: bool = True) -> Dict:
        if self.models and not refresh:
            return self.models
        if self._authToken is None:
            self._refresh_authToken()
        requestResult = PerformRequest(self._base_headers, self._URL_Get_Models_Events, method='GET')
        self.models = self._organize_fief_model_response(requestResult)
        ## set LLMAlpha event types
        self.models['LLMAlpha']['EventTypes'] = self._get_LLM_EventTypes()
        return self.models

    async def convertPdfToText(self, fileKey):
        key = last_part = fileKey.split('/')[-1]
        try:
            requestResult = PerformRequest(self._base_headers, self._URL_Convert_Pdf_to_Text,
                                           request_obj={'fileKey': key},
                                           method='POST')
            return requestResult
        except Exception as e:
            print(f'Error occured: {e}')

    def get_fief_event_rules(self, modelName, eventType) -> List:
        if self._authToken is None:
            self._refresh_authToken()
        self.get_model_list()
        if modelName in ['LLMAlpha', 'LLMMacro']:
            print("FIEF event rules can only be retrieved for FIEF models, not LLMs")
            return []
        if modelName not in self.models.keys():
            print(f"Model {modelName} does not exist - cannot get FIEF event in Model that does not exist")
            return []
        model_obj = self.models[modelName]
        if eventType not in model_obj['EventTypes']:
            print(f"Event {eventType} does not exist")
            return []
        requestResult = PerformRequest(self._base_headers, self._URL_Get_Fief_Event_Rules,
                                       request_obj={'modelName': model_obj['modelPath'], 'eventType': eventType},
                                       method='POST')
        return requestResult['data']

    def create_fief_model(self, modelName):
        if self._authToken is None:
            self._refresh_authToken()
        self.get_model_list()
        if modelName in self.models.keys():
            print(f"Model {modelName} already exists")
            return False
        requestResult = PerformRequest(self._base_headers, self._URL_Create_Fief_Model, request_obj={'modelName': modelName}, method='POST')
        self.get_model_list()
        return requestResult['data']

    def getCompanyId(self, companyName):
        request_obj = {"retrieveType": "company"}

        if len(companyName) > 2:
            request_obj["searchCompaniesQuery"] = companyName

        requestResult = PerformRequest(self._base_headers, self._URL_Get_Meta_Data,
                                       request_obj=request_obj, method='POST')

        companies = []
        if requestResult['data']['results']:
            for res in requestResult['data']['results']:
                company = {'id': res['id'], 'name': res['displayName'], 'ticker': res['ticker']}
                companies.append(company)
            return companies
        else:
            response =  'no company found'
            return response

    def delete_fief_model(self, modelName):
        if self._authToken is None:
            self._refresh_authToken()
        self.get_model_list()
        if modelName not in self.models.keys():
            print(f"Model {modelName} does not exist")
            return False
        requestResult = PerformRequest(self._base_headers, self._URL_Delete_Fief_Model,
                                       request_obj={'modelName': modelName}, method='POST')
        self.get_model_list()
        if 'error' in requestResult:
            return requestResult['error']
        else:
            return requestResult['data']

    def create_fief_event(self, modelName, eventType, categoryName='myEvents'):
        if self._authToken is None:
            self._refresh_authToken()
        self.get_model_list()
        if modelName not in self.models.keys():
            print(f"Model {modelName} does not exist - cannot create FIEF event in Model that does not exist")
            return False
        requestResult = PerformRequest(self._base_headers, self._URL_Create_Fief_Event,
                                       request_obj={'id': '', 'modelName': modelName, 'eventType': eventType, 'categoryName': categoryName},
                                       method='POST')
        self.get_model_list()
        return requestResult['data']

    def delete_fief_event(self, modelName, eventType):
        if self._authToken is None:
            self._refresh_authToken()
        self.get_model_list()
        if modelName not in self.models.keys():
            print(f"Model {modelName} does not exist - cannot delete FIEF event in Model that does not exist")
            return False
        model_obj = self.models[modelName]
        if eventType not in model_obj['EventTypes']:
            print(f"Event Type {eventType} does not exist - cannot delete FIEF event that does not exist")
            return False
        requestResult = PerformRequest(self._base_headers, self._URL_Delete_Fief_Event,
                                       request_obj={'id': "", 'modelName': modelName, 'eventType': eventType},
                                       method='POST')
        self.get_model_list()
        if 'data' in requestResult:
            return requestResult['data']
        else:
            return requestResult

    def delete_doc(self, docmeta):
        if self._authToken is None:
            self._refresh_authToken()
        _req = {'runId': docmeta['runId'], 'fileKey': docmeta['fileKey']}
        res = PerformRequest(self._base_headers, self._URL_Platform_Doc_Upload, _req, method='DELETE', encode_url=True)
        if not res:
            print(f"Succeeded to delete document: {docmeta['name']} - fileKey: {docmeta['fileKey']}")

    def get_doc_analytics(self, docmeta, out_path: str = None) -> Dict:
        if self._authToken is None:
            self._refresh_authToken()
        if docmeta['status'] != 'Completed':
            print(f'Document: {docmeta["name"]} - is still being analyzed. Results may be partial.')

        _req = {'ExclusiveStartKey': {}, 'runId': docmeta['runId'], 'fileKey': docmeta['fileKey']}
        requestResult = PerformRequest(self._base_headers, self._URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
        doc_analytics = requestResult['data']
        if requestResult['ExclusiveStartKey']:
            while requestResult['ExclusiveStartKey']:
                _req['ExclusiveStartKey'] = requestResult['ExclusiveStartKey']
                requestResult = PerformRequest(self._base_headers, self._URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
                doc_analytics.append(requestResult['data'])

        doc_analytics = sorted(doc_analytics, key=lambda x: x['index'])
        doc_results = {"doc_meta": docmeta, "doc_analytics": doc_analytics}
        if out_path is not None:
            self._save_to_json(
                os.path.join(out_path, f"{_strip_file_suffix(docmeta['name'])}_{docmeta['onModel']}.json"), doc_results)

        return doc_results

    @staticmethod
    def aggregate_filter_records(records):
        if 'groupKey' in records[0]:  # Check if the first record contains 'groupKey'
            aggregated = defaultdict(list)
            for record in records:
                aggregated[record['groupKey']].append(record['label'])
            return dict(aggregated)
        else:
            # If no groupKey is present, just return the labels as a list
            return {'marketCaps': [record['label'] for record in records]}

    def get_smart_search_filters(self, corpus):
        corpus = corpus.lower()
        if corpus not in ('transcripts', 'sec', 'nonsec'):
            raise ValueError(f"Corpus must be one of these options -> ['transcripts', 'sec', 'nonsec'], you chose: '{corpus}'")
        platform_corpus_name = self._platform_corpus_map[corpus]
        resFilters =  PerformRequest(self._base_headers, self._URL_Platform_Result_Filters,  request_obj={'corpus': platform_corpus_name}, method='POST')['data']

        doctype_filters = self.aggregate_filter_records(resFilters['documentTypes'])
        sector_filters = self.aggregate_filter_records(resFilters['subSectors'])
        # marketcap_filters = self.aggregate_filter_records(resFilters['marketCaps'])

        # get watchlist filters
        watchlist_filters = self.get_watchlists()

        return {'docTypes': doctype_filters, 'sectors': sector_filters, 'watchLists': watchlist_filters} #, 'marketCaps': marketcap_filters}

    def get_watchlists(self):
        watchlist_filters = {}
        requestResult = PerformRequest(self._base_headers, self._URL_Platform_Watchlist, method='GET').get('data', None)
        if requestResult:
            watchlist_filters = defaultdict(list)
            for rec in requestResult:
                watchlist_filters[rec['watchlistName']].extend(rec['companies'])
        return dict(watchlist_filters)

    def get_smart_search_full_results(self, sent_id_recs, similarity_threshold):
        # if sent_id_recs:
        # filter sent_ids by threshold
        sent_ids_fltrd = [r for r in takewhile(lambda x: x['score'] >= similarity_threshold, sent_id_recs)]
        sent_ids_dict = {record['id']: record['score'] for record in sent_ids_fltrd}
        exclude_fields = ['keywordsPositions', 'events', 'DLSentiment', 'speakerNameId', 'speakerCompanyId']

        full_results = []
        for sent_id_chunk in _chunk_list(sent_ids_fltrd, 100):
            sent_ids = [x['id'] for x in sent_id_chunk]
            request_obj = {'sentencesIds': sent_ids, 'excludes': exclude_fields}
            requestResult = PerformRequest(self._base_headers, self._URL_Platform_Result_Datas, request_obj=request_obj, method='POST')
            if requestResult.get('data', None):
                res = [{**record['_source'], '_id': record['_id'], 'similarity_score': sent_ids_dict[record['_id']]} for record in requestResult['data']['sentences']]
                full_results.append(res)

        full_results[:] = [item for sublist in full_results for item in sublist]
        full_results.sort(key=lambda x: x['similarity_score'], reverse=True)

        return full_results

    def get_topic_research_full_results(self, sent_id_recs):
        transformed_data = []

        # Check if sent_id_recs is a list with a single item
        if isinstance(sent_id_recs, list) and len(sent_id_recs) == 1:
            sent_id_recs = sent_id_recs[0]

        # Ensure we're working with the "data" key
        data_to_process = sent_id_recs.get("data", sent_id_recs)

        # If data_to_process is still a list with one item, unpack it
        if isinstance(data_to_process, list) and len(data_to_process) == 1:
            data_to_process = data_to_process[0]

        # Loop over each element in the "data" list
        for element in sent_id_recs["data"]:
            # Extract necessary values for the transformation
            document_meta = element.get("documentMeta", {})
            event_data = element.get("event", {})
            slots_filter = element.get("slotsFilter", {})
            tags = element.get("tags", [])

            # Create the transformed element
            transformed_element = {
                "DLSentiment": element.get("DLSentiment", ""),
                "importance": slots_filter.get("importance", ""),
                "aspect": slots_filter.get("aspect", ""),
                "comment": slots_filter.get("comment", ""),
                "documentMeta": {
                    "date": document_meta.get("date", ""),
                    "country": document_meta.get("country", ""),
                    "ticker": document_meta.get("ticker", ""),
                    "documentType": document_meta.get("documentType", ""),
                    "companyName": document_meta.get("companyName", ""),
                    "corpus": document_meta.get("corpus", ""),
                    "title": document_meta.get("title", ""),
                    "hqCountry": document_meta.get("hqCountry", ""),
                    "subSector": document_meta.get("subSector", ""),
                    "companyId": document_meta.get("companyId", ""),
                    "transcriptId": document_meta.get("transcriptId", ""),
                    "exchange": document_meta.get("exchange", ""),
                    "sector": document_meta.get("sector", ""),
                    "day": document_meta.get("day", ""),
                    "marketCap": document_meta.get("marketCap", 0)
                },
                "tags": tags,
                "sentenceIndex": element.get("sentenceIndex", 0),
                "paragraphIndex": element.get("paragraphIndex", 0),
                "model": element.get("model", ""),
                "text": element.get("text", ""),
                "EventType": event_data.get("EventType", ""),
                "EventText": event_data.get("EventText", ""),
                "Polarity": event_data.get("Polarity", ""),
                "llmTag": element.get("llmTag", "")
            }

            # Append the transformed element to the results list
            transformed_data.append(transformed_element)

        return transformed_data

    def process_subQ(self, args):
        q_name, request_obj, similarity_threshold = args
        requestResult = PerformRequest(self._base_headers, self._URL_Platform_Vector_Search, request_obj=request_obj, method='POST')
        recs = self.get_smart_search_full_results(requestResult.get('data',[]), similarity_threshold)
        return q_name, recs

    def process_research_topicQ(self, request_obj, nResults):
        size = 1_000
        requestResultList = []

        if isinstance(nResults, str):
            if nResults == 'all':
                nResults = 10_000
            else:
                raise ValueError(f"Parameter 'nResults' must be 'all' or an integer, got {nResults}")

        if nResults <= size:
            size = nResults
            request_obj['size'] = size
            requestResult = PerformRequest(self._base_headers, self._URL_Paltform_Topic_Research,
                                           request_obj=request_obj,
                                           method='POST')
            if requestResult:
                recs = self.get_topic_research_full_results(requestResult['data'])
                requestResultList.extend(recs)
        else:
            numLoops = math.ceil(nResults / size)
            for i in range(numLoops):
                request_obj['from'] = i * size
                size = min(nResults - i*size, size)
                request_obj['size'] = size
                requestResult = PerformRequest(self._base_headers, self._URL_Paltform_Topic_Research,
                                               request_obj=request_obj,
                                               method='POST')
                if requestResult:
                    recs = self.get_topic_research_full_results(requestResult['data'])
                    requestResultList.extend(recs)

        # request_obj['size'] = size
        return requestResultList

    def checkRequest(self, corpus, companies=None ,sector=None, watchlist=None, doc_type=None, start_date=None, end_date=None):
        if not corpus:
            raise ValueError("'corpus' must be specified")

        search_type = None
        resFilters = self.get_smart_search_filters(corpus)
        available_doctypes = list(resFilters['docTypes'].values())[0]
        available_sectors = list(resFilters['sectors'].keys())
        available_watchlists = list(resFilters['watchLists'].keys())

        default_doctypes = {
            'transcripts': {'label': 'Earnings Calls'},
            'sec': {'label': '10-Q'},
            'nonsec': {'label': 'QR'},
            'S&P Transcripts' : {'label': 'Earnings Calls'}
        }

        if sector is None and watchlist is None and companies is None:
            raise ValueError(
                f"Sector or Watchlist must be specified\n Sectors -> {available_sectors}\n Watchlists -> {available_watchlists}")

        if companies is not None:
            search_type = 'company'
        elif sector is not None:
            if sector not in available_sectors:
                raise ValueError(f"Sector must be one of these options -> {available_sectors}, you chose: '{sector}'")
            else:
                search_type = 'sector'
        elif watchlist is not None:
            if watchlist not in available_watchlists:
                raise ValueError(
                    f"Watchlist must be one of these options -> {available_watchlists}, you chose: '{watchlist}'")
            else:
                search_type = 'watchlist'

        if doc_type is None:
            doc_type = default_doctypes[corpus]
            print(f"No doc_type provided, defaulting to '{doc_type['label']}'")
        else:
            if doc_type not in available_doctypes:
                raise ValueError(
                    f"doc_type must be one of these options -> {available_doctypes}, you chose: '{doc_type}'")
            else:
                doc_type = {'label': doc_type}

        if start_date is None:
            start_date = (datetime.today() - timedelta(days=90)).strftime("%Y-%m-%d")
            print(f"No start_date provided, defaulting to '{start_date}'")
        elif not _is_valid_date_format(start_date):
            raise ValueError(f"start_date must be of type 'YYYY-MM-DD', you chose: '{start_date}'")

        if end_date is None:
            end_date = datetime.today().strftime("%Y-%m-%d")
            print(f"No end_date provided, defaulting to '{end_date}'")
        elif not _is_valid_date_format(end_date):
            raise ValueError(f"end_date must be of type 'YYYY-MM-DD', you chose: '{end_date}'")

        return search_type, doc_type, start_date, end_date, resFilters

    def _get_LLM_EventTypes(self):
        platform_corpus_name = self._platform_corpus_map['transcripts']
        eventTypes = PerformRequest(self._base_headers, self._URL_Platform_Result_Filters,
                                    request_obj={'corpus': platform_corpus_name, 'isLLM':True}, method='POST')['data']['eventTypes']
        allEventTypes = []
        for filter in eventTypes:
            if filter['groupKey'] == 'AlphaLLM':
                allEventTypes.append(filter['label'])

        allEventTypes.sort()
        return allEventTypes

    def run_topic_research(self, corpus, nResults=1_000, companies=None, country = None, sentiment = None, eventType=None, freeText=None, sector=None, watchlist=None, doc_type=None, start_date=None, end_date=None) -> List:
        search_type, doc_type, start_date, end_date, resFilters = self.checkRequest(corpus, companies, sector, watchlist, doc_type, start_date, end_date)
        size = 1_000
        platform_corpus_name = self._platform_corpus_map[corpus]
        doc_type = doc_type['label']
        request_obj = {
            "dateRange": {'gte': start_date, 'lte': end_date},
            "documentTypes": [doc_type],
            "size": size,
            "from" : 0,
            "sort" : "desc",
            "isLLM": True,
            "corpus": platform_corpus_name,
            "searchEventTextQuery": ""
        }

        if sentiment:
            request_obj['patternSentiment'] = [sentiment.capitalize()]

        if country:
            request_obj['hqCountries'] = [country]

        # if researchName:
        #     request_obj['researchName'] = researchName
        if freeText:
            request_obj['freeText'] = [freeText]

        if eventType:
            ## for now only Alpha and LLMAlpha Topics are available
            if corpus == 'transcripts':
                avail_topics = self.models['LLMAlpha']['EventTypes']
            else:
                avail_topics = self.models['Alpha']['EventTypes']

            if eventType in avail_topics:
                request_obj['eventTypes'] = [eventType]
            else:
                raise ValueError(f"eventType must be one of these options -> {avail_topics}")

        if search_type == 'company':
            request_obj['companiesIds'] = companies
            request_obj['retrieveType'] = 'company'
        elif search_type == 'sector':
            subSector = []
            request_obj['sectors'] = [sector]
            for subsector in resFilters['sectors'][sector]:
                subSector.append(subsector)
            request_obj['subSectors'] = subSector
        elif search_type == 'watchlist':
            request_obj['watchlist'] = resFilters['watchLists'][watchlist]
        else:
            raise NotImplementedError

        results = self.process_research_topicQ(request_obj, nResults)

        return results

    def run_smart_search(self, corpus, searchQ, sector=None, watchlist=None,sentiment=None, companies =None,country = None,  doc_type=None, start_date=None, end_date=None, similarity_threshold=.50) -> Dict:
        if not searchQ:
            raise ValueError("'searchQ' must be specified")
        search_type, doc_type, start_date, end_date, resFilters = self.checkRequest(corpus,companies,  sector, watchlist, doc_type, start_date, end_date)

        request_obj = {
            'dateRange': {'gte': start_date, 'lte': end_date},
            'documentTypes': [doc_type],
            'isMacro': False,
            'searchQuery': searchQ,
            'size': 6_000,
            'returnPineconeResults': True,
        }

        if sentiment:
            request_obj['sentiment'] = sentiment

        if country:
            request_obj['country'] = country

        if search_type == 'sector':
            print('Running Sector based Query')
            request_obj['focusOn'] = 'sectors'
            with Pool(4) as pool:
                tasks = []
                for subsector in resFilters['sectors'][sector]:
                    req_obj = copy.deepcopy(request_obj)
                    req_obj['subSectors'] = [{'label': subsector, 'groupKey': sector}]
                    tasks.append((subsector, req_obj, similarity_threshold))

                results = list(tqdm(pool.imap(self.process_subQ, tasks), total=len(tasks)))

        elif search_type == 'watchlist':
            print('Running Watchlist based Query')
            request_obj['focusOn'] = 'watchlist'
            request_obj['focusOnValues'] = [{'key': watchlist, 'value': resFilters['watchLists'][watchlist]}]
            task = (watchlist, request_obj, similarity_threshold)
            results = [self.process_subQ(task)]

        elif search_type == 'company':
            request_obj['focusOnValues'] = []
            for company in companies:
                compObj={'key': '', 'value': [company]}
                request_obj['focusOnValues'].append(compObj)
            request_obj['focusOn'] = 'companies'
            task = ('companies', request_obj, similarity_threshold)
            results = [self.process_subQ(task)]
            # request_obj['retrieveType'] = 'company'

        else:
            raise NotImplementedError

        # Combine results into a single dictionary
        datas = defaultdict(list)
        for qname, recs in results:
            if search_type == 'company':
                for rec in recs:
                    company_id = rec['documentMeta']['companyId']
                    # Add each record to the list of the corresponding companyId
                    datas[company_id].append(rec)
            else:
                datas[qname].extend(recs)
        return dict(datas)

    def _validate_doc_model(self, doc_model):
        """
        Validate if the input object is a dictionary with specific keys and string values.

        Args:
        doc_model (dict): The object to validate.

        Returns:
        bool: True if the object is valid, False otherwise.
        """
        if not isinstance(doc_model, dict):
            return False, "doc-model request is not a valid dict"

        required_keys = ['name', 'onModel']
        for key in required_keys:
            if key not in doc_model or not isinstance(doc_model[key], str):
                return False, f"doc-model request is missing required key: {key}"

        if doc_model['onModel'] not in self.models:
            return False, f"doc-model request is using an invalid model: {doc_model['onModel']} -- Allowed Models: {self.models}"

        if not (doc_model['name'].endswith('.txt') or doc_model['name'].endswith('.pdf')):
            return False, f"doc-model request is using an invalid doc type: {doc_model['name']} -- Doc type must be .txt or .pdf"

        return True, ''

    @staticmethod
    def _count_event_sentiments(data, isLLM):
        def extract_importance(slotrec):
            for item in slotrec:
                if item.get('SlotName') == 'importance':
                    return item.get('Value').lower()
            return None

        dlscore_counts = {"positive": 0, "negative": 0, "neutral": 0}
        event_sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        importance_sentiment_counts = {'negative': {'high': 0, 'low': 0, 'medium': 0},
                                       'neutral': {'high': 0, 'low': 0, 'medium': 0},
                                       'positive': {'high': 0, 'low': 0, 'medium': 0}}

        for entry in data:
            # Count DLScore values
            if not isLLM:
                if 'Sentences' in entry:
                    for sentence in entry['Sentences']:
                        if 'DLScore' in sentence:
                            if sentence['DLScore'] > 0:
                                dlscore_counts['positive'] += 1
                            elif sentence['DLScore'] < 0:
                                dlscore_counts['negative'] += 1
                            else:
                                dlscore_counts['neutral'] += 1

            # Count Event Sentiment values
            if 'Events' in entry:
                for event in entry['Events']:
                    if 'Polarity' in event:
                        sentiment_value = event['Polarity'].lower()
                    else:
                        sentiment_value = 'neutral'
                    event_sentiment_counts[sentiment_value] += 1

                    # get importance if exists
                    if isLLM:
                        importance = extract_importance(event['Slots'])
                        if importance is not None:
                            importance_sentiment_counts[sentiment_value][importance] += 1

        return dlscore_counts, event_sentiment_counts, importance_sentiment_counts

    @staticmethod
    def _save_to_json(filename, data):
        if not filename.endswith('.json'):
            filename += '.json'
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Saved result to {filename}")
        except IOError as e:
            print(f"An error occurred while writing to the file: {e}")

    @staticmethod
    async def _save_result_to_json_async(result, out_dir):
        filename = os.path.join(out_dir, f"{_strip_file_suffix(result['doc_meta']['name'])}_{result['doc_meta']['onModel']}.json")
        if not filename.endswith('.json'):
            filename += '.json'
        try:
            async with aiofiles.open(filename, 'w') as f:
                await f.write(json.dumps(result, indent=4))
            print(f"Saved result to {filename}")
        except IOError as e:
            print(f"An error occurred while writing to the file: {e}")

    @staticmethod
    async def _perform_request_async(session, headers, url, params=None, method='POST', encode_url=False):
        if method.upper() == 'POST':
            body = json.dumps(params)
            async with session.post(url, headers=headers, data=body) as response:
                response.raise_for_status()
                return await response.json()
        elif method.upper() == 'GET':
            if encode_url and params:
                encoded_params = urlencode(params)
                url = f"{url}?{encoded_params}"
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                async with session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    return await response.json()
        else:
            raise ValueError("Invalid method. Supported methods are 'POST' and 'GET'")

    async def _get_platform_upload_link(self, doc_model):
        """
        Asynchronously retrieve the upload link for a document from the platform.
        """
        url = self._URL_Platform_Doc_Upload
        headers = self._base_headers
        _req = doc_model.copy()
        _req['name'] = os.path.basename(doc_model['name'])
        _req['isLLM'] = False
        if _req['onModel'].lower() == 'llmalpha':
            _req['onModel'] = 'Alpha'
            _req['isLLM'] = True
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=_req, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result[0]
                else:
                    raise Exception(
                        f"Failed to retrieve upload link. Status code: {response.status}, Response: {await response.text()}")

    async def _upload_doc_to_platform(self, doc_model):
        requestResult = await self._get_platform_upload_link(doc_model)
        signed_url = requestResult['signedUrl']
        file_path = doc_model['name']

        url = signed_url['url']
        fields = signed_url['fields']

        # Asynchronously upload the file using aiohttp
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            for key, value in fields.items():
                data.add_field(key, value)

            # Open the file and add it to the FormData within the async context
            async with aiofiles.open(file_path, 'rb') as file:
                file_content = await file.read()
                data.add_field('file', file_content, filename=os.path.basename(file_path),
                               content_type='application/octet-stream')

                # Make the request to upload the file asynchronously
                async with session.post(url, data=data) as response:
                    if response.status == 204:
                        print(f"File '{file_path}' uploaded successfully")
                        self._request_meta_map[
                            f"{requestResult['document']['runId']}{requestResult['document']['fileKey']}"] = requestResult['document']
                    else:
                        response_text = await response.text()
                        raise Exception(
                            f"Failed to upload file '{file_path}'. Status code: {response.status}, Response: {response_text}")
        if file_path.endswith('.pdf'):
            res = await self.convertPdfToText(signed_url['fields']['key'])
            print (f'{file_path} converted successfully')
        return signed_url

    async def _call_platform_analyzer(self, requestResult):
        """
        Asynchronously call the platform analyzer for a given document.
        """
        headers = {"Authorization": self._authToken, "pronto-granted": "R$w#8k@Pmz%2x2Dg#5fGz"}
        doc_req = {"document": requestResult, "onModel": requestResult['onModel'], "streaming": False}
        cntr = 0

        async with aiohttp.ClientSession() as session:
            while cntr < 120:
                try:
                    async with session.post(self._URL_Platform_Doc_Analyze, json=doc_req, headers=headers) as response:
                        response_data = await response.json()
                        if response.status == 200:
                            print(f"Starting to analyze document '{requestResult['name']}'")
                            return response_data
                        else:
                            print(f"Analysis request failed, retrying in 5 seconds...")
                            cntr += 1
                            await asyncio.sleep(5)
                except Exception as e:
                    print(f"An error occurred: {e}")
                    cntr += 1
                    await asyncio.sleep(5)

            raise Exception(f"Failed to analyze file after several attempts")

    async def _get_doc_analytics_async(self, docmeta):
        if self._authToken is None:
            self._refresh_authToken()
        if docmeta['status'] != 'Completed':
            print(f'Document: {docmeta["name"]} - is still being analyzed. Results may be partial.')

        _req = {'ExclusiveStartKey': {}, 'runId': docmeta['runId'], 'fileKey': docmeta['fileKey']}
        doc_analytics = []
        async with aiohttp.ClientSession() as session:
            requestResult = await self._perform_request_async(session, self._base_headers, self._URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
            doc_analytics.extend(requestResult['data'])

            while requestResult.get('ExclusiveStartKey'):
                _req['ExclusiveStartKey'] = requestResult['ExclusiveStartKey']
                requestResult = await self._perform_request_async(session, self._base_headers, self._URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
                doc_analytics.extend(requestResult['data'])

        doc_analytics = sorted(doc_analytics, key=lambda x: x['index'])
        doc_results = {"doc_meta": docmeta, "doc_analytics": doc_analytics}
        return doc_results

    async def analyze_docs(self, doc_models: List[dict], out_dir: str = None, keep_results: bool = True) -> AsyncGenerator[Dict, None]:
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)

        doc_model_reqs = []
        # pdfDocs = []
        for d_m in doc_models:
            chk, reason = self._validate_doc_model(d_m)
            if not chk:
                print(f"Invalid document-model request: {d_m} --> {reason}")
            else:
                doc_model_reqs.append(d_m)

        if not doc_model_reqs:
            print(f"No valid document-model requests found")
            sys.exit()

        print(f"Uploading {len(doc_model_reqs)} documents")
        upload_tasks = [self._upload_doc_to_platform(d_m) for d_m in doc_model_reqs]
        await asyncio.gather(*upload_tasks)  # Upload documents concurrently
        print("All documents uploaded successfully.")

        # Setup and start the WebSocket connection first
        websocket_coro = analyze_docs_websocket(self._URL_Doc_Results_WebSocket, self._authToken, self._get_doc_analytics_async, len(self._request_meta_map))

        # Give the WebSocket a moment to establish connection
        await asyncio.sleep(1)

        # Initiate analysis on the uploaded documents
        analysis_tasks = [self._call_platform_analyzer(doc) for doc in self._request_meta_map.values()]
        await asyncio.gather(*analysis_tasks)  # Start analysis concurrently
        print("Document analysis initiated for all documents.")

        # Process results from the WebSocket as they come in
        async for result in websocket_coro:
            try:
                # format results
                docmeta = _safe_get(self._request_meta_map, f"{result['doc_meta']['runId']}{result['doc_meta']['fileKey']}", default=dict())
                result['doc_meta'] = {**docmeta, **result['doc_meta']}
                if result['doc_meta']['isLLM']:
                    result['doc_meta']['onModel'] = f"LLM{result['doc_meta']['onModel']}"

                dlscore_counts, event_sentiment_counts, importance_sentiment_counts = self._count_event_sentiments(result['doc_analytics'], isLLM=result['doc_meta']['isLLM'])
                result['doc_meta']['sentiment'] = event_sentiment_counts
                result['doc_meta']['DLSentiment'] = dlscore_counts
                result['doc_meta']['importanceSentiment'] = importance_sentiment_counts

                if out_dir:
                    # Save results asynchronously to the specified output directory
                    await self._save_result_to_json_async(result, out_dir)
                    yield result['doc_meta']
                else:
                    # Yield the result if no output directory is provided
                    yield result
            except Exception as e:
                print(f"Error while analyzing document: {e}")
                continue

        print("Analyzer completed")
        if not keep_results:
            # delete documents
            for k, doc_meta in self._request_meta_map.items():
                self.delete_doc(doc_meta)
        self._request_meta_map = dict()  # Clear the map after processing is complete

    async def analyze_text(self, text: Union[str, List[str]], model: str, out_dir: str = None, keep_results: bool = True) -> AsyncGenerator[Dict, None]:
        if isinstance(text, str):
            text = [text]

        temp_files = []
        try:
            for item in text:
                if not item:
                    continue
                # Create a filename from the first few words of the text
                filename = '_'.join(item.split()[:5])  # Take first 5 words
                filename = ''.join(c for c in filename if c.isalnum() or c in ['_', '-'])  # Remove special characters
                filename = f"{filename[:50]}__"  # Limit to 50 characters

                async with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', prefix=filename, delete=False) as temp_file:
                    await temp_file.write(item)
                    temp_files.append(temp_file.name)

            doc_models = [{'name': file_path, 'onModel': model} for file_path in temp_files]

            async for result in self.analyze_docs(doc_models, out_dir, keep_results):
                yield result

        finally:
            for file_path in temp_files:
                os.unlink(file_path)

