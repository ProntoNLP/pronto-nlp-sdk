import sys
import urllib.request
from typing import Union, List, Dict, AsyncGenerator
import requests
import re
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


def GetListRulesets(authToken):
  requestObj = {"request": "GetRulesetsList",}
  requestResult = PerformRequest({"Authorization": authToken}, "https://prontonlp.net/fiefserver/main/guihelper", requestObj)
  return requestResult['rulesets']


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
        if response.status_code != 200:
            print(f"Request Failed. Status code: {response.status_code}, Response: {response.text}")
    try:
        return response.json()
    except json.JSONDecodeError:
        return response


def _strip_file_suffix(filename):
    return os.path.splitext(filename)[0]


def _safe_get(d, key, default=None):
    try:
        return d[key]
    except KeyError:
        return default


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
        self.URL_Platform_Doc_Upload = "https://server-prod.prontonlp.com/reflect/documents"
        self.URL_Platform_Doc_Analyze = "https://server-prod.prontonlp.com/reflect/analyze-document"
        self.URL_Platform_Doc_Results = "https://server-prod.prontonlp.com/reflect/results"
        self.URL_Doc_Results_WebSocket = "wss://socket-prod.prontonlp.com/"
        self.user, self.password = user, password
        self.authToken = None
        self.base_headers = None
        self.doc_list = list()
        self.request_meta_map = dict()
        self._refresh_authToken()
        self.allowed_models = ['LLMAlpha'] + GetListRulesets(self.authToken)  # 'LLMMacro'

    def _refresh_authToken(self):
        self.authToken = SignIn(self.user, self.password)
        self.base_headers = {"Content-Type": "application/json", "Authorization": self.authToken,
                             "pronto-granted": "R$w#8k@Pmz%2x2Dg#5fGz"}

    def get_doc_list(self, refresh: bool = True) -> List:
        if self.doc_list and not refresh:
            return self.doc_list
        if self.authToken is None:
            self._refresh_authToken()
        requestResult = PerformRequest(self.base_headers, self.URL_Platform_Doc_Upload, method='GET')
        docs_sorted = sorted(requestResult['Items'], key=lambda x: x['lastRun'], reverse=True)
        self.doc_list = docs_sorted
        print(f"Found {len(self.doc_list)} documents")
        return self.doc_list

    def delete_doc(self, docmeta):
        if self.authToken is None:
            self._refresh_authToken()
        _req = {'runId': docmeta['runId'], 'fileKey': docmeta['fileKey']}
        res = PerformRequest(self.base_headers, self.URL_Platform_Doc_Upload, _req, method='DELETE', encode_url=True)
        if not res:
            print(f"Succeeded to delete document: {docmeta['name']} - fileKey: {docmeta['fileKey']}")

    def get_doc_analytics(self, docmeta, out_path: str = None) -> Dict:
        if self.authToken is None:
            self._refresh_authToken()
        if docmeta['status'] != 'Completed':
            print(f'Document: {docmeta["name"]} - is still being analyzed. Results may be partial.')

        _req = {'ExclusiveStartKey': {}, 'runId': docmeta['runId'], 'fileKey': docmeta['fileKey']}
        requestResult = PerformRequest(self.base_headers, self.URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
        doc_analytics = requestResult['data']
        if requestResult['ExclusiveStartKey']:
            while requestResult['ExclusiveStartKey']:
                _req['ExclusiveStartKey'] = requestResult['ExclusiveStartKey']
                requestResult = PerformRequest(self.base_headers, self.URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
                doc_analytics.append(requestResult['data'])

        doc_analytics = sorted(doc_analytics, key=lambda x: x['index'])
        doc_results = {"doc_meta": docmeta, "doc_analytics": doc_analytics}
        if out_path is not None:
            self._save_to_json(
                os.path.join(out_path, f"{_strip_file_suffix(docmeta['name'])}_{docmeta['onModel']}.json"), doc_results)

        return doc_results

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

        if doc_model['onModel'] not in self.allowed_models:
            return False, f"doc-model request is using an invalid model: {doc_model['onModel']} -- Allowed Models: {self.allowed_models}"

        if not doc_model['name'].endswith('.txt'):
            return False, f"doc-model request is using an invalid doc type: {doc_model['name']} -- Doc type must be .txt"

        return True, ''

    @staticmethod
    def count_event_sentiments(data, isLLM):
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
        url = self.URL_Platform_Doc_Upload
        headers = self.base_headers
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
                        self.request_meta_map[
                            f"{requestResult['document']['runId']}{requestResult['document']['fileKey']}"] = requestResult['document']
                    else:
                        response_text = await response.text()
                        raise Exception(
                            f"Failed to upload file '{file_path}'. Status code: {response.status}, Response: {response_text}")

    async def _call_platform_analyzer(self, requestResult):
        """
        Asynchronously call the platform analyzer for a given document.
        """
        headers = {"Authorization": self.authToken, "pronto-granted": "R$w#8k@Pmz%2x2Dg#5fGz"}
        doc_req = {"document": requestResult, "onModel": requestResult['onModel'], "streaming": False}
        cntr = 0

        async with aiohttp.ClientSession() as session:
            while cntr < 120:
                try:
                    async with session.post(self.URL_Platform_Doc_Analyze, json=doc_req, headers=headers) as response:
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
        if self.authToken is None:
            self._refresh_authToken()
        if docmeta['status'] != 'Completed':
            print(f'Document: {docmeta["name"]} - is still being analyzed. Results may be partial.')

        _req = {'ExclusiveStartKey': {}, 'runId': docmeta['runId'], 'fileKey': docmeta['fileKey']}
        doc_analytics = []
        async with aiohttp.ClientSession() as session:
            requestResult = await self._perform_request_async(session, self.base_headers, self.URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
            doc_analytics.extend(requestResult['data'])

            while requestResult.get('ExclusiveStartKey'):
                _req['ExclusiveStartKey'] = requestResult['ExclusiveStartKey']
                requestResult = await self._perform_request_async(session, self.base_headers, self.URL_Platform_Doc_Results, _req, method='GET', encode_url=True)
                doc_analytics.extend(requestResult['data'])

        doc_analytics = sorted(doc_analytics, key=lambda x: x['index'])
        doc_results = {"doc_meta": docmeta, "doc_analytics": doc_analytics}
        return doc_results

    async def analyze_docs(self, doc_models: List[dict], out_dir: str = None, keep_results: bool = True) -> AsyncGenerator[Dict, None]:
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)

        doc_model_reqs = []
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
        websocket_coro = analyze_docs_websocket(self.URL_Doc_Results_WebSocket, self.authToken, self._get_doc_analytics_async, len(self.request_meta_map))

        # Give the WebSocket a moment to establish connection
        await asyncio.sleep(1)

        # Initiate analysis on the uploaded documents
        analysis_tasks = [self._call_platform_analyzer(doc) for doc in self.request_meta_map.values()]
        await asyncio.gather(*analysis_tasks)  # Start analysis concurrently
        print("Document analysis initiated for all documents.")

        # Process results from the WebSocket as they come in
        async for result in websocket_coro:
            try:
                # format results
                docmeta = _safe_get(self.request_meta_map, f"{result['doc_meta']['runId']}{result['doc_meta']['fileKey']}", default=dict())
                result['doc_meta'] = {**docmeta, **result['doc_meta']}
                if result['doc_meta']['isLLM']:
                    result['doc_meta']['onModel'] = f"LLM{result['doc_meta']['onModel']}"

                dlscore_counts, event_sentiment_counts, importance_sentiment_counts = self.count_event_sentiments(result['doc_analytics'], isLLM=result['doc_meta']['isLLM'])
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
            for k, doc_meta in self.request_meta_map.items():
                self.delete_doc(doc_meta)
        self.request_meta_map = dict()  # Clear the map after processing is complete

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
