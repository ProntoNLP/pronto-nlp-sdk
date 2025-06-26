import copy
import sys
import urllib.request
from typing import Union, List, Dict, AsyncGenerator
import requests
import math
import tempfile as std_tempfile
from collections import defaultdict
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
import jwt

from .APIStats import APIUserStats


def SignIn(user, password):
    organization = "prod"
    M = re.match(r'^(.*?):(.*)$', user)
    if M:
        organization = M.group(1)
        user = M.group(2)
    authURL = ("https://server-staging.prontonlp.com/api/token" if (organization == "dev" or organization == "staging") else
               "https://server-prod.prontonlp.com/api/token")

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
        eks = request_obj.get("ExclusiveStartKey")
        if isinstance(eks, dict) and eks:
            request_obj['ExclusiveStartKey'] = quote(json.dumps(request_obj['ExclusiveStartKey']))
            query_string = "&".join(f"{k}={v}" for k, v in request_obj.items())
            url = f"{url}?{query_string}"
        else:
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
            raise ValueError(f"Request Failed. Status code: {response.status_code}, Response: {response.text}")

    try:
        if url.endswith('reflect/convert'):
            return response, url
        return response.json(), url
    except json.JSONDecodeError as e:
        return response, url
    except ValueError as e:
        return response, url


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
    def __init__(self, base_uri, authToken, result_callback, reconnect_interval=3):
        self.base_uri = base_uri
        self.authToken = quote(authToken)
        self.uri = f"{self.base_uri}?token={self.authToken}"
        self.result_callback = result_callback
        self.reconnect_interval = reconnect_interval
        self.websocket = None
        self.running = True

    async def connect(self):
        while True:
            try:
                self.websocket = await websockets.connect(
                    self.uri,
                    ping_interval=5,
                    ping_timeout=120
                )
                print("Connected to the websocket.")
                break  # Exit the loop once connected
            except Exception as e:
                print(f"Failed to connect: {e}. Retrying in {self.reconnect_interval} seconds...")
                await asyncio.sleep(self.reconnect_interval)

    async def listen(self):
        retry_count = 0
        max_retries = 15
        while self.running:
            try:
                if self.websocket is None or self.websocket.closed:
                    print("Websocket connection lost. Attempting to reconnect...")
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
                print("Connection closed normally by the server.")
                self.running = False
            except json.JSONDecodeError as e:
                retry_count += 1
                print(f"JSON decode error: {e}. Retry {retry_count}/{max_retries}.")
                if retry_count < max_retries:
                    await asyncio.sleep(5)
                else:
                    raise Exception("Maximum retry attempts reached. Exiting.") from e
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                await asyncio.sleep(self.reconnect_interval)

    async def process_message(self, message):
        try:
            data = json.loads(message)
            if not data.get('completed', False):
                print(f"Incomplete result for fileKey: {data.get('fileKey')}.")
                return None
            data['status'] = 'Completed'
            processed_result = await self.result_callback(data)
            return processed_result
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON message: {e} \n {message}")
        except Exception as e:
            print(f"Failed to process message: {e} \n {message}")

    async def close(self):
        self.running = False
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            print("Websocket connection closed.")


class ProntoPlatformAPI:
    def __init__(self, user, password):
        self._request_meta_map = dict()
        self._URL_api_base = "https://server-prod.prontonlp.com/api"
        self._URL_Platform_Doc_Upload = f"{self._URL_api_base}/reflect/documents"
        self._URL_Platform_Doc_Analyze = f"{self._URL_api_base}/reflect/analyze-document"
        self._URL_Platform_Doc_Results = f"{self._URL_api_base}/reflect/results"
        self._URL_Doc_Results_WebSocket = "wss://socket-prod.prontonlp.com/"

        self._URL_Platform_Vector_Search = f"{self._URL_api_base}/get-vector-search-results"
        self._URL_Platform_Result_Filters = f"{self._URL_api_base}/get-filters"
        self._URL_Platform_Result_Datas = f"{self._URL_api_base}/get-sentences"
        self._URL_Platform_Result_Context = f"{self._URL_api_base}/research/get-sentences-context"

        self._URL_Platform_Watchlist = f"{self._URL_api_base}/watchlists"
        self._URL_Get_Models_Events = f"{self._URL_api_base}/models/get-models-events"

        self._URL_Get_Fief_Event_Rules = f"{self._URL_api_base}/models/event-rules"
        self._URL_Create_Fief_Model = f"{self._URL_api_base}/models/save-user-model"
        self._URL_Delete_Fief_Model = f"{self._URL_api_base}/models/delete-user-model"
        self._URL_Create_Fief_Event = f"{self._URL_api_base}/models/save-user-event"
        self._URL_Delete_Fief_Event = f"{self._URL_api_base}/models/delete-user-event"
        self._URL_Create_Fief_Pattern = ""
        self._URL_Delete_Fief_Pattern = f"{self._URL_api_base}/models/delete-user-pattern"

        self._URL_Get_Meta_Data = f"{self._URL_api_base}/get-metadata-results"

        self._URL_Paltform_Topic_Research_Results = f"{self._URL_api_base}/research/researches/topic"
        self._URL_Paltform_Topic_Research = f"{self._URL_api_base}/research/get-research-results"

        self._URL_Convert_Pdf_to_Text = f"{self._URL_api_base}/reflect/convert"
        self._platform_corpus_map = {'transcripts': 'S&P Transcripts', 'sec': 'SEC Filings',
                                     'nonsec': 'Non-SEC Filings'}
        self._user, self._password = user, password
        self._authToken = None
        self._base_headers = None
        self._user_auth_obj = None
        self._user_stats = APIUserStats()
        self._refresh_authToken()
        self.doc_list = list()
        self.models = dict()
        self.get_model_list()
        
    def _refresh_authToken(self):
        self._authToken = SignIn(self._user, self._password)
        self._base_headers = {"Content-Type": "application/json", "Authorization": self._authToken,
                             "pronto-granted": "R$w#8k@Pmz%2x2Dg#5fGz"}
        self._user_auth_obj = jwt.decode(self._authToken, options={"verify_signature": False})
        self._user_stats.identify_user(self._user_auth_obj)
        self._user_stats.track(event_name='SDK Login')

    def get_doc_list(self, refresh: bool = True) -> List:
        if self.doc_list and not refresh:
            return self.doc_list
        if self._authToken is None:
            self._refresh_authToken()
        requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Doc_Upload, method='GET')
        self._user_stats.track(event_name='SDK Get Document List', properties={'endpoint': url, 'documentsCount': len(requestResult['Items'])})
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
        requestResult, url = PerformRequest(self._base_headers, self._URL_Get_Models_Events, method='GET')
        self._user_stats.track(event_name='SDK Get Model List', properties={'endpoint': url})
        self.models = self._organize_fief_model_response(requestResult)
        ## set LLMAlpha event types
        self.models['LLMAlpha']['EventTypes'] = self._get_LLM_EventTypes()
        return self.models

    async def convertPdfToText(self, fileKey):
        key = last_part = fileKey.split('/')[-1]
        try:
            requestResult, url = PerformRequest(self._base_headers, self._URL_Convert_Pdf_to_Text,
                                           request_obj={'fileKey': key},
                                           method='POST')
            self._user_stats.track(event_name='SDK Convert PDF To Text', properties={'endpoint': url})
            await asyncio.sleep(10)
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
        requestResult, url = PerformRequest(self._base_headers, self._URL_Get_Fief_Event_Rules,
                                       request_obj={'modelName': model_obj['modelPath'], 'eventType': eventType},
                                       method='POST')
        self._user_stats.track(event_name='SDK Get FIEF Event Rules', properties={'endpoint': url, 'modelName': modelName, 'eventType': eventType})
        return requestResult['data']

    def create_fief_model(self, modelName):
        if self._authToken is None:
            self._refresh_authToken()
        self.get_model_list()
        if modelName in self.models.keys():
            print(f"Model {modelName} already exists")
            return False
        requestResult, url = PerformRequest(self._base_headers, self._URL_Create_Fief_Model, request_obj={'modelName': modelName}, method='POST')
        self._user_stats.track(event_name='SDK Create FIEF Model', properties={'endpoint': url, 'modelName': modelName})
        self.get_model_list()
        return requestResult['data']

    def getCompanyId(self, companyName):
        request_obj = {"retrieveType": "company"}

        if len(companyName) > 2:
            request_obj["searchCompaniesQuery"] = companyName

        requestResult, url = PerformRequest(self._base_headers, self._URL_Get_Meta_Data,
                                       request_obj=request_obj, method='POST')
        self._user_stats.track(event_name='SDK Get Company Id', properties={'endpoint': url})

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
        requestResult, url = PerformRequest(self._base_headers, self._URL_Delete_Fief_Model,
                                       request_obj={'modelName': modelName}, method='POST')
        self._user_stats.track(event_name='SDK Delete FIEF Model', properties={'endpoint': url, 'modelName': modelName})
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
        requestResult, url = PerformRequest(self._base_headers, self._URL_Create_Fief_Event,
                                       request_obj={'id': '', 'modelName': modelName, 'eventType': eventType, 'categoryName': categoryName},
                                       method='POST')
        self._user_stats.track(event_name='SDK Create FIEF Event', properties={'endpoint': url, 'modelName': modelName, 'eventType': eventType, 'categoryName': categoryName})
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
        requestResult, url = PerformRequest(self._base_headers, self._URL_Delete_Fief_Event,
                                       request_obj={'id': "", 'modelName': modelName, 'eventType': eventType},
                                       method='POST')
        self._user_stats.track(event_name='SDK Delete FIEF Event', properties={'endpoint': url, 'modelName': modelName, 'eventType': eventType})
        self.get_model_list()
        if 'data' in requestResult:
            return requestResult['data']
        else:
            return requestResult

    def delete_doc(self, docmeta):
        if self._authToken is None:
            self._refresh_authToken()
        _req = {'runId': docmeta['runId'], 'fileKey': docmeta['fileKey']}
        requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Doc_Upload, _req, method='DELETE', encode_url=True)
        self._user_stats.track(event_name='SDK Delete Document', properties={'endpoint': url, 'documentName': docmeta['name'], 'runId': docmeta['runId']})
        if not requestResult:
            print(f"Succeeded to delete document: {docmeta['name']} - fileKey: {docmeta['fileKey']}")

    def get_doc_analytics(self, docmeta, out_path: str = None) -> Dict:
        if self._authToken is None:
            self._refresh_authToken()
        if docmeta['status'] != 'Completed':
            print(f'Document: {docmeta["name"]} - is still being analyzed. Results may be partial.')

        _req = {'ExclusiveStartKey': {}, 'runId': docmeta['runId'], 'fileKey': docmeta['fileKey']}
        requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
        doc_analytics = requestResult['data']
        if requestResult['ExclusiveStartKey']:
            while requestResult['ExclusiveStartKey']:
                _req['ExclusiveStartKey'] = requestResult['ExclusiveStartKey']
                requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
                doc_analytics.extend(requestResult['data'])

        doc_analytics = sorted(doc_analytics, key=lambda x: x['index'])
        doc_results = {"doc_meta": docmeta, "doc_analytics": doc_analytics}
        if out_path is not None:
            self._save_to_json(
                os.path.join(out_path, f"{_strip_file_suffix(docmeta['name'])}_{docmeta['onModel']}.json"), doc_results)

        self._user_stats.track(event_name='SDK Get Document Analytics', 
                        properties={'endpoint': url, 'documentName': docmeta['name'], 'modelName': docmeta['onModel'], 'runId': docmeta['runId']})
        return doc_results

    @staticmethod
    def _aggregate_filter_records(records):
        if 'groupKey' in records[0]:  # Check if the first record contains 'groupKey'
            aggregated = defaultdict(list)
            for record in records:
                aggregated[record['groupKey']].append(record['label'])
            return dict(aggregated)
        else:
            # If no groupKey is present, just return the labels as a list
            return {'marketCaps': [record['label'] for record in records]}

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

    def get_smart_search_filters(self, corpus):
        corpus = corpus.lower()
        if corpus not in ('transcripts', 'sec', 'nonsec'):
            raise ValueError(f"Corpus must be one of these options -> ['transcripts', 'sec', 'nonsec'], you chose: '{corpus}'")
        platform_corpus_name = self._platform_corpus_map[corpus]
        requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Result_Filters, request_obj={'corpus': platform_corpus_name}, method='POST')
        self._user_stats.track(event_name='SDK Get Smart Search Filters', properties={'endpoint': url, 'corpus': corpus})
        requestResult = requestResult['data']

        doctype_filters = self._aggregate_filter_records(requestResult['documentTypes'])
        sector_filters = self._aggregate_filter_records(requestResult['subSectors'])
        # marketcap_filters = self.aggregate_filter_records(requestResult['marketCaps'])

        # get watchlist filters
        watchlist_filters = self.get_watchlists()

        return {'docTypes': doctype_filters, 'sectors': sector_filters, 'watchLists': watchlist_filters} #, 'marketCaps': marketcap_filters}

    def get_watchlists(self):
        watchlist_filters = {}
        requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Watchlist, method='GET')
        self._user_stats.track(event_name='SDK Get Watchlists', properties={'endpoint': url})
        requestResult = requestResult.get('data', None)

        if requestResult:
            watchlist_filters = defaultdict(list)
            for rec in requestResult:
                watchlist_filters[rec['watchlistName']].extend(rec['companies'])
        return dict(watchlist_filters)

    def get_context(self, sent_ids, N=3):
        full_results = []
        for sent_id_chunk in _chunk_list(sent_ids, 65):
            request_obj = {'resultIds': sent_id_chunk, 'beforeSentence': N, 'afterSentence': N+1, 'withEvents': True}
            requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Result_Context, request_obj=request_obj, method='POST')
            self._user_stats.track(event_name='SDK Get Context from Document', properties={'endpoint': url})
            if requestResult:
                full_results.extend(requestResult)
        return full_results

    def _get_smart_search_full_results(self, sent_id_recs, similarity_threshold):
        sent_ids_fltrd = [r for r in sent_id_recs if r['score'] >= similarity_threshold]
        sent_ids_dict = {record['id']: record['score'] for record in sent_ids_fltrd}
        exclude_fields = ['keywordsPositions', 'events', 'DLSentiment', 'speakerNameId', 'speakerCompanyId']

        full_results = []
        for sent_id_chunk in _chunk_list(sent_ids_fltrd, 100):
            sent_ids = [x['id'] for x in sent_id_chunk]
            request_obj = {'sentencesIds': sent_ids, 'excludes': exclude_fields}
            requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Result_Datas, request_obj=request_obj, method='POST')
            if requestResult.get('data', None):
                res = [{**record['_source'], '_id': record['_id'], 'similarity_score': sent_ids_dict[record['_id']]} for record in requestResult['data']['sentences']]
                full_results.append(res)

        full_results[:] = [item for sublist in full_results for item in sublist]
        full_results.sort(key=lambda x: x['similarity_score'], reverse=True)

        return full_results

    def _get_topic_research_full_results(self, sent_id_recs):
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
                '_id': f'{document_meta.get("transcriptId", "")}-{element.get("sentenceIndex", 0)}',
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

    def _process_subQ(self, args):
        q_name, request_obj, similarity_threshold = args
        requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Vector_Search, request_obj=request_obj, method='POST')
        recs = self._get_smart_search_full_results(requestResult.get('data', []), similarity_threshold)
        return q_name, recs

    def _process_research_topicQ(self, request_obj, nResults):
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
            requestResult, url = PerformRequest(self._base_headers, self._URL_Paltform_Topic_Research,
                                           request_obj=request_obj,
                                           method='POST')
            if requestResult:
                recs = self._get_topic_research_full_results(requestResult['data'])
                requestResultList.extend(recs)
        else:
            numLoops = math.ceil(nResults / size)
            for i in range(numLoops):
                request_obj['from'] = i * size
                size = min(nResults - i*size, size)
                request_obj['size'] = size
                requestResult, url = PerformRequest(self._base_headers, self._URL_Paltform_Topic_Research,
                                               request_obj=request_obj,
                                               method='POST')
                if requestResult:
                    recs = self._get_topic_research_full_results(requestResult['data'])
                    requestResultList.extend(recs)

        # request_obj['size'] = size
        return requestResultList

    def _check_request(self, corpus, companies=None, sector=None, watchlist=None, doc_type=None, start_date=None, end_date=None):
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
        requestResult, url = PerformRequest(self._base_headers, self._URL_Platform_Result_Filters,
                                    request_obj={'corpus': platform_corpus_name, 'isLLM':True}, method='POST')
        eventTypes = requestResult['data']['eventTypes']
        allEventTypes = []
        for filter in eventTypes:
            if filter['groupKey'] == 'AlphaLLM':
                allEventTypes.append(filter['label'])

        allEventTypes.sort()
        return allEventTypes

    def run_topic_research(self, corpus, nResults=1_000, companies=None, country=None, sentiment=None, eventType=None, freeText=None, sector=None, watchlist=None, doc_type=None, start_date=None, end_date=None) -> List:
        search_type, doc_type, start_date, end_date, resFilters = self._check_request(corpus, companies, sector, watchlist, doc_type, start_date, end_date)
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

        results = self._process_research_topicQ(request_obj, nResults)

        self._user_stats.track(event_name='SDK Run Topic Research', 
                               properties={'corpus': corpus, 'searchType': search_type, 'docType': doc_type, 'startDate': start_date, 'endDate': end_date})

        return results

    def run_smart_search(self, corpus, searchQ, sector=None, watchlist=None, sentiment=None, companies=None, country=None, doc_type=None, start_date=None, end_date=None, similarity_threshold=.50) -> Dict:
        if not searchQ:
            raise ValueError("'searchQ' must be specified")
        search_type, doc_type, start_date, end_date, resFilters = self._check_request(corpus, companies, sector, watchlist, doc_type, start_date, end_date)

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

                results = list(tqdm(pool.imap(self._process_subQ, tasks), total=len(tasks)))

        elif search_type == 'watchlist':
            print('Running Watchlist based Query')
            request_obj['focusOn'] = 'watchlist'
            request_obj['focusOnValues'] = [{'key': watchlist, 'value': resFilters['watchLists'][watchlist]}]
            task = (watchlist, request_obj, similarity_threshold)
            results = [self._process_subQ(task)]

        elif search_type == 'company':
            request_obj['focusOnValues'] = []
            for company in companies:
                compObj = {'key': '', 'value': [company]}
                request_obj['focusOnValues'].append(compObj)
            request_obj['focusOn'] = 'companies'
            task = ('companies', request_obj, similarity_threshold)
            results = [self._process_subQ(task)]
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

        self._user_stats.track(event_name='SDK Run Smart Search', 
                               properties={'corpus': corpus, 'searchQ': searchQ, 'searchType': search_type, 'docType': doc_type, 'startDate': start_date, 'endDate': end_date})

        return dict(datas)

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
        # ——— apply ExclusiveStartKey bug-fix for URL encoding ———
        if encode_url and params:
            eks = params.get("ExclusiveStartKey")
            if isinstance(eks, dict) and eks:
                # JSON-dump and quote the dict, then build a manual query string
                params["ExclusiveStartKey"] = quote(json.dumps(eks))
                query_string = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"{url}?{query_string}"
            else:
                # fallback to regular urlencode of all params
                encoded_params = urlencode(params)
                url = f"{url}?{encoded_params}"

        # ——— now issue the request ———
        if method.upper() == "POST":
            body = json.dumps(params)
            async with session.post(url, headers=headers, data=body) as response:
                response.raise_for_status()
                return await response.json()

        elif method.upper() == "GET":
            if encode_url and params:
                # already encoded in the URL
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                # let aiohttp handle params
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

        self._user_stats.track(event_name='SDK Upload Document', properties={'endpoint': url, 'file_path': file_path})
        if file_path.endswith('.pdf'):
            res = await self.convertPdfToText(signed_url['fields']['key'])
            print (f'{file_path} converted successfully')
        return signed_url

    async def _call_platform_analyzer(self, requestResult):
        """
        Asynchronously call the platform analyzer for a given document.
        Waits for document conversion to complete before returning results.
        """
        headers = {"Authorization": self._authToken, "pronto-granted": "R$w#8k@Pmz%2x2Dg#5fGz"}
        doc_req = {"document": requestResult, "onModel": requestResult['onModel'], "streaming": False}

        # Configuration constants
        MAX_ATTEMPTS = 120
        BASE_DELAY = 5
        MAX_DELAY = 30
        JSON_RETRY_LIMIT = 10

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            json_retry_count = 0

            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    async with session.post(
                            self._URL_Platform_Doc_Analyze,
                            json=doc_req,
                            headers=headers
                    ) as response:

                        # Handle non-200 status codes
                        if response.status != 200:
                            delay = min(BASE_DELAY * (1.2 ** (attempt - 1)), MAX_DELAY)
                            print(f"Attempt {attempt}: Request failed with status {response.status}. "
                                  f"Retrying in {delay:.1f} seconds...")
                            await asyncio.sleep(delay)
                            continue

                        try:
                            response_data = await response.json()
                        except json.JSONDecodeError as e:
                            json_retry_count += 1
                            if json_retry_count >= JSON_RETRY_LIMIT:
                                raise Exception(
                                    f"Failed to parse JSON response after {JSON_RETRY_LIMIT} attempts") from e

                            print(f"JSON parsing error (attempt {json_retry_count}/{JSON_RETRY_LIMIT}): {e}. "
                                  f"Retrying in {BASE_DELAY} seconds...")
                            await asyncio.sleep(BASE_DELAY)
                            continue

                        # Reset JSON retry counter on successful parse
                        json_retry_count = 0

                        # Check document conversion status
                        if self._is_document_still_processing(response_data):
                            # Use exponential backoff for processing delays, but cap it
                            delay = min(BASE_DELAY * (1.1 ** (attempt - 1)), MAX_DELAY)
                            # print(f"Attempt {attempt}: Document '{requestResult.get('name', 'Unknown')}' "
                            #       f"still being processed. Waiting {delay:.1f} seconds...")
                            await asyncio.sleep(delay)
                            continue

                        elif self._is_document_processing_complete(response_data):
                            print(f"Working on document '{requestResult.get('name', 'Unknown')}'")
                            self._user_stats.track(event_name='SDK Call Document Analyzer', properties={"documentName": requestResult.get('name', 'Unknown'), "modelName": requestResult['onModel']})
                            return response_data

                        else:
                            # Unexpected response format - log it and return
                            print(f"Warning: Unexpected response format for document "
                                  f"'{requestResult.get('name', 'Unknown')}'. Returning as-is.")
                            return response_data

                except asyncio.TimeoutError:
                    delay = min(BASE_DELAY * (1.2 ** (attempt - 1)), MAX_DELAY)
                    print(f"Attempt {attempt}: Request timeout. Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)

                except aiohttp.ClientError as e:
                    delay = min(BASE_DELAY * (1.2 ** (attempt - 1)), MAX_DELAY)
                    print(f"Attempt {attempt}: Network error: {e}. Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)

                except Exception as e:
                    # For unexpected errors, use shorter delay and continue
                    print(f"Attempt {attempt}: Unexpected error: {e}. Retrying in {BASE_DELAY} seconds...")
                    await asyncio.sleep(BASE_DELAY)

            # If we get here, all attempts failed
            raise Exception(f"Failed to analyze document '{requestResult.get('name', 'Unknown')}' "
                            f"after {MAX_ATTEMPTS} attempts over {MAX_ATTEMPTS * BASE_DELAY / 60:.1f} minutes")

    def _is_document_still_processing(self, response_data):
        """Check if the document is still being processed."""
        return (isinstance(response_data, dict) and
                response_data.get('data') == 'document not yet converted')

    def _is_document_processing_complete(self, response_data):
        """Check if the document processing is complete."""
        return (isinstance(response_data, dict) and
                '$metadata' in response_data)

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
        self._user_stats.track(event_name='SDK Get Document Analytics', properties={'documentName': docmeta['name'], 'runId': docmeta['runId']})
        return doc_results

    async def _process_websocket_result(self, raw_result: dict, out_dir: str = None):
        try:
            # The same formatting logic you used before
            docmeta = self._request_meta_map.get(
                f"{raw_result['doc_meta']['runId']}{raw_result['doc_meta']['fileKey']}", {}
            )
            raw_result['doc_meta'] = {**docmeta, **raw_result['doc_meta']}

            if raw_result['doc_meta'].get('isLLM'):
                raw_result['doc_meta']['onModel'] = f"LLM{raw_result['doc_meta']['onModel']}"

            dlscore_counts, event_sentiment_counts, importance_sentiment_counts = self._count_event_sentiments(
                raw_result['doc_analytics'],
                isLLM=raw_result['doc_meta']['isLLM']
            )
            raw_result['doc_meta']['sentiment'] = event_sentiment_counts
            raw_result['doc_meta']['DLSentiment'] = dlscore_counts
            raw_result['doc_meta']['importanceSentiment'] = importance_sentiment_counts

            # Optionally save to out_dir
            if out_dir:
                await self._save_result_to_json_async(raw_result, out_dir)
                return raw_result['doc_meta']
            else:
                # If not saving, just return the full result
                return raw_result

        except Exception as e:
            print(f"Error processing websocket result: {e}")
            # You could return None or re-raise
            return None

    async def _create_temp_file(self, text_content: str, unique_ids: Union[None, List[str]], idx: int, std_tempfile) -> str:
        """
        Create a temporary file for text content.
        
        Args:
            text_content: The text to write to the file
            unique_ids: Optional list of unique identifiers
            idx: Index of the current text
            std_tempfile: The tempfile module
            
        Returns:
            Path to the created temporary file
        """
        if unique_ids is not None:
            # Use provided unique_id as filename (no tempfile prefix/suffix)
            filename = self._sanitize_filename(unique_ids[idx])
            if not filename.endswith('.txt'):
                filename += '.txt'
            
            temp_dir = std_tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)
            
            async with aiofiles.open(file_path, mode='w', encoding='utf-8') as temp_file:
                await temp_file.write(text_content)
                
            return file_path
        
        else:
            # Generate filename from text content and use tempfile prefix/suffix
            base = '_'.join(text_content.split()[:5])
            prefix = self._sanitize_filename(base)[:50] or 'text'  # Fallback if empty
            
            async with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.txt', 
                prefix=f"{prefix}__", 
                delete=False,
                encoding='utf-8'
            ) as temp_file:
                await temp_file.write(text_content)
                return temp_file.name
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a string to be safe for use as a filename.
        
        Args:
            filename: The string to sanitize
            
        Returns:
            Sanitized filename string
        """
        if not filename:
            return 'unnamed'
        
        # Keep only alphanumeric characters, underscores, hyphens, and dots
        sanitized = ''.join(c for c in filename if c.isalnum() or c in ['_', '-', '.'])
        
        # Ensure it's not empty after sanitization
        return sanitized if sanitized else 'unnamed'
    
    async def _cleanup_temp_files(self, temp_files: List[str]) -> None:
        """
        Clean up temporary files.
        
        Args:
            temp_files: List of file paths to delete
        """
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except OSError as e:
                print(f"Warning: Failed to delete temporary file {file_path}: {e}")


    async def analyze_docs(self, doc_models: List[dict], out_dir: str = None, keep_results: bool = True) -> AsyncGenerator[dict, None]:
        """
        1. Upload docs
        2. Open WebSocket
        3. Start analysis tasks in parallel
        4. Read + yield WebSocket results as they arrive
        5. Don't exit until we've received all results or the analysis tasks complete
        6. Optionally clean up
        """

        # Set up
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)

        # ---------------------------
        # 1. Upload the Documents
        # ---------------------------
        doc_model_reqs = []
        for d_m in doc_models:
            chk, reason = self._validate_doc_model(d_m)
            if not chk:
                print(f"Invalid document-model request: {d_m} --> {reason}")
            else:
                doc_model_reqs.append(d_m)

        if not doc_model_reqs:
            print("No valid document-model requests found")
            sys.exit()

        print(f"Uploading {len(doc_model_reqs)} documents")
        upload_tasks = [self._upload_doc_to_platform(d) for d in doc_model_reqs]
        await asyncio.gather(*upload_tasks)
        print("All documents uploaded successfully.")

        # Build a map (or re-build) if needed
        num_docs = len(doc_model_reqs)
        print(f"Expecting results for {num_docs} documents.")

        # ----------------------------
        # 2. Open WebSocket Connection
        # ----------------------------
        client = ProntoWebSocketClient(
            base_uri=self._URL_Doc_Results_WebSocket,
            authToken=self._authToken,
            result_callback=self._get_doc_analytics_async
        )
        await client.connect()
        print("WebSocket connection established.")

        # ----------------------------
        # 3. Start Analysis in Parallel
        # ----------------------------
        # We'll launch the analysis tasks in the background...
        analysis_tasks = [
            asyncio.create_task(self._call_platform_analyzer(doc_meta))
            for doc_meta in self._request_meta_map.values()
        ]
        # ... but we do *not* await them *immediately*, so the code below can run concurrently
        print("Document analysis is starting for all documents.")

        # -----------------------------
        # 4. Read + Yield WS Results
        # -----------------------------
        web_socket_results = 0

        # Create a single gather for your analysis tasks so we can check it later
        analysis_future = asyncio.gather(*analysis_tasks)

        try:
            # We'll read messages until the server stops or we've seen enough
            async for raw_result in client.listen():
                web_socket_results += 1
                print(f"Received result #{web_socket_results} from WebSocket.")

                try:
                    # Process the result
                    processed = await self._process_websocket_result(
                        raw_result, out_dir
                    )
                    yield processed  # This is how we return data to the caller

                except Exception as e:
                    print(f"Error processing a WebSocket result: {e}")
                    continue

                # If we know exactly how many results we expect, we can stop early:
                if web_socket_results >= num_docs:
                    print("Received all expected results. Stopping WebSocket read.")
                    break

        finally:
            # -----------------------------
            # 5. Wrap Up: Wait for Analysis
            # -----------------------------
            # Make sure analysis tasks are done
            try:
                await analysis_future
            except Exception as e:
                print(f"Error from analysis tasks: {e}")
                # We can either re-raise or just log it

            # Close the WebSocket
            await client.close()
            print("WebSocket closed.")

        # -----------------------------
        # 6. Cleanup
        # -----------------------------
        if not keep_results:
            # e.g., self.delete_docs() ...
            for k, doc_meta in self._request_meta_map.items():
                self.delete_doc(doc_meta)

        self._request_meta_map.clear()
        print("Analyzer completed.")

    async def analyze_text(self, text: Union[str, List[str]], model: str, unique_ids: Union[None, List[str]] = None, out_dir: str = None, keep_results: bool = True) -> AsyncGenerator[Dict, None]:
        """
        Analyze text content using the specified model.
        
        Args:
            text: String or list of strings to analyze
            model: Model name to use for analysis
            unique_ids: Optional list of unique identifiers for each text (used as filenames)
            out_dir: Optional output directory for results
            keep_results: Whether to keep results after analysis
            
        Yields:
            Analysis results as dictionaries
        """
        # Normalize text to list
        if isinstance(text, str):
            text = [text]
        
        # Validate unique_ids if provided
        if unique_ids is not None:
            if len(unique_ids) != len(text):
                raise ValueError("Length of unique_ids must match length of text inputs.")
            if len(set(unique_ids)) != len(unique_ids):
                raise ValueError("All unique_ids must be unique.")
        
        # Filter out empty texts and track indices
        valid_texts = [(idx, item) for idx, item in enumerate(text) if item.strip()]
        
        if not valid_texts:
            raise ValueError("No non-empty text provided for analysis.")
        
        temp_files = []
        
        try:
            for idx, item in valid_texts:
                file_path = await self._create_temp_file(item, unique_ids, idx, std_tempfile)
                temp_files.append(file_path)
            
            doc_models = [{'name': file_path, 'onModel': model} for file_path in temp_files]
            
            async for result in self.analyze_docs(doc_models, out_dir, keep_results):
                yield result
                
        finally:
            # Clean up temporary files
            await self._cleanup_temp_files(temp_files)

