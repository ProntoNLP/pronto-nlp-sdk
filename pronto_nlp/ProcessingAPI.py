from gevent import monkey, spawn, sleep
monkey.patch_all()

import sys
import re
import json
import urllib.request
import boto3
from time import time
import websocket

from queue import Queue
import heapq

#from ProcessingAPI_Misc import CreateJSContext
from .FindMatches_Misc_JS import AddNewMatchForFindMatches, GetAllDocIDsForFindMatches, GenerateCSVForMatches_ProcessingAPI
from .SelectRelation_ExtraMetadata_JS import GetFirstBatchOfDocIDsToDownloadExtraMetadataForDocIDSet, AddNewExtraMetadata, GetNextBatchOfDocIDsToDownloadExtraMetadata
from .SignalGeneration_Misc_JS import AddNewFullSignalData, GetAllDocIDsForSignals, GenerateSignalCSV_ProcessingAPI



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
  try:
    response = urllib.request.urlopen(request)
    if response.status == 200:
      result = response.read().decode('utf-8')
      if not result.startswith('{'): return result
  except:
    pass

  authParameters = {'USERNAME': user, 'PASSWORD': password}
  client = boto3.client('cognito-idp', region_name='us-west-2')
  response = client.initiate_auth(AuthFlow='USER_PASSWORD_AUTH',
                                  AuthParameters=authParameters,
                                  ClientId='88nt7a64nkbukf7r49p8q82ht')
  authToken = response['AuthenticationResult']['IdToken']
  return authToken


def PerformFIEFRequest(authToken, URL, requestObj):
  body = json.dumps(requestObj, ensure_ascii=True).encode('ascii')
  request = urllib.request.Request(URL, data=body, headers={"Authorization": authToken})
  response = urllib.request.urlopen(request)
  if response.status != 200:
    raise Exception(f"Request failed, status: {response.status}")
  requestResult = json.loads(response.read())
  return requestResult


def GetListRulesets(authToken):
  requestObj = {
    "request": "GetRulesetsList",
  }
  requestResult = PerformFIEFRequest(authToken, 'https://prontonlp.net/fiefserver/main/guihelper', requestObj)
  return requestResult['rulesets']


def GetListRelationsForRuleset(authToken, ruleset):
  requestObj = {
    "request": "GetRelationTypesList",
    "ruleset": ruleset
  }
  requestResult = PerformFIEFRequest(authToken, 'https://prontonlp.net/fiefserver/main/guihelper', requestObj)
  return requestResult['relationtypes'][1]


def GetListDBs(authToken):
  requestObj = {
    "request": "GetParseCacheDBList",
  }
  requestResult = PerformFIEFRequest(authToken, 'https://prontonlp.net/fiefserver/main/guihelper', requestObj)
  return requestResult['DBs']


def ProcessDoc_RESTAPI(authToken, ruleset, outputtype, text):
  requestObj = {
    "request": "ProcessDoc",
    "ruleset": ruleset,
    "outputtype": outputtype,
    "text": text
  }
  requestResult = PerformFIEFRequest(authToken, 'https://prontonlp.net/fiefserver/main', requestObj)
  return requestResult['data']


def ProcessDoc_websocketAPI(authToken, ruleset, outputtype, text):
  ws = websocket.create_connection("wss://3c5qlj48hi.execute-api.us-west-2.amazonaws.com/main")
  try:
    iAt = 0
    iIndex = 0
    while iAt < len(text) - 20000:
      #print(f"Storing {iIndex} {iAt}", file=sys.stderr)
      ws.send(json.dumps({'request': 'WSProcessDoc-StoreData', 'authtoken': authToken,
                          'index': iIndex, 'data': text[iAt:iAt+20000]}))
      ack = ws.recv()
      #print(f"Storing-ack {ack}", file=sys.stderr)
      if json.loads(ack)['Collected'] != iIndex: raise Exception("Incorrect store-data acknowledgement")
      iAt += 20000
      iIndex += 1

    #print(f"WSProcessDoc", file=sys.stderr)
    ws.send(json.dumps({'request': 'WSProcessDoc', 'authtoken': authToken,
                        'ruleset': ruleset, 'outputtype': outputtype, 'text': text[iAt:]}))

    #print(f"Receiving", file=sys.stderr)
    iSize = int(ws.recv())
    #print(f"Received size {iSize}", file=sys.stderr)
    result = ""
    while len(result) < iSize:
      #print(f"Receiving next", file=sys.stderr)
      result += json.loads(ws.recv())

    return result

  finally:
    ws.close()


def ProcessDoc(authToken, ruleset, outputtype, text, maxAttempts=2, verbose=True):
  attempts = 0
  while True:
    try:
      if len(text) >= 16*1024 or attempts > 0:
        return ProcessDoc_websocketAPI(authToken, ruleset, outputtype, text)
      else:
        return ProcessDoc_RESTAPI(authToken, ruleset, outputtype, text)
    except:
      attempts += 1
      if attempts >= maxAttempts: raise
      if verbose:
        print("Warning: Exception in ProcessDoc - retrying after 10 sec")
      sleep(10)


# Input: inputDocSource, a generator of docs
#        getTextFunc, a function that takes a doc and returns its text (by default, doc is the text)
#        outputtype = 'XML' or 'JSON' or 'events'
# Output: a generator of pairs (doc, result)
def DoBatchProcessing(authToken, ruleset, outputtype, inputDocSource, getTextFunc=lambda doc: doc,
                      maxAttempts=2, numThreads=10, verbose=True):
  inputQueue = Queue()  # queue of [iDocIndex, Doc, text]
  resultsHeapQ = []     # priority queue of [iDocIndex, Doc, text, result]
  iDocsRead = 0
  iDocsWritten = -1
  timeStart = 0
  iDocsProcessed = 0
  iProcessedSize = 0

  def PrintStatus():
    if not verbose: return
    secs = time() - timeStart
    if secs == 0: secs = 1
    speedKBperMin = int(1000 * (iProcessedSize / 1024) / (secs / 60)) / 1000
    print(f"Docs in: {iDocsRead}, processed: {iDocsProcessed}, out: {iDocsWritten}, speed: {speedKBperMin} KB/min", end='\r', file=sys.stderr)

  def InputThread():
    nonlocal iDocsRead
    nonlocal iDocsWritten
    nonlocal timeStart
    timeStart = time()
    for iDocIndex, doc in enumerate(inputDocSource):
      text = getTextFunc(doc).strip()
      inputQueue.put([iDocIndex, doc, text])
      iDocsRead = iDocIndex + 1
      if iDocsWritten < 0:  iDocsWritten = 0
      PrintStatus()
      while inputQueue.qsize() > 50 + numThreads:
        sleep(0.01)

  def ProcessingThread():
    nonlocal iDocsProcessed
    nonlocal iProcessedSize
    while inputQueue.qsize() > 0:
      nextTask = inputQueue.get()
      result = ProcessDoc(authToken, ruleset, outputtype, nextTask[2], maxAttempts=maxAttempts, verbose=verbose) if nextTask[2] else ""
      nextTask.append(result)
      heapq.heappush(resultsHeapQ, nextTask)
      iDocsProcessed += 1
      iProcessedSize += len(nextTask[2])
      PrintStatus()

  spawn(InputThread)
  for i in range(numThreads):
    spawn(ProcessingThread)

  while iDocsWritten < iDocsRead:
    sleep(0.01)
    while resultsHeapQ and resultsHeapQ[0][0] == iDocsWritten:
      nextOutput = heapq.heappop(resultsHeapQ)
      iDocsWritten += 1
      PrintStatus()
      yield (nextOutput[1], nextOutput[3])

  if verbose: print(file=sys.stderr)


def ReadMessageFromWebsocket(ws):
  body = ws.recv()
  if not body:
    print("\nWarning: empty message - ignoring", file=sys.stderr)
    return None
  try:
    return json.loads(body)
  except:
    print(f"\nError: JSON failed to decode message: '{body}'", file=sys.stderr)
    raise


def GenerateSignalCSV(authToken, sRuleset, sDB, sStartDate=None, sEndDate=None, sTickerFilter=None, tags=None, progressReportCallback=None, fDownloadExtraMetadata=True):
  if progressReportCallback: progressReportCallback("Starting...")

  if isinstance(sRuleset, str):
    rulesets = re.split(r'[;|]', sRuleset)
  else:
    rulesets = sRuleset
  rules = ["<.*>" for _ in rulesets]

  #JScontext = CreateJSContext()

  ws = websocket.create_connection("wss://3c5qlj48hi.execute-api.us-west-2.amazonaws.com/main")
  try:
    ws.send(json.dumps({'authtoken': authToken,
                        'DB': [sDB], 'ruleset':rulesets, 'rule':rules,
                        'StartDate': sStartDate, 'EndDate': sEndDate, 'TickerFilter': sTickerFilter,
                        'Tags': tags,
                        'UseEntities': True}))

    while True:
      message = ReadMessageFromWebsocket(ws)
      if not message or 'FullSignalData' not in message: continue
      signalData = message['FullSignalData']
      if signalData == '<Done>': break
      AddNewFullSignalData(message['FullSignalData']) # JScontext.
      if progressReportCallback: progressReportCallback(f"Reading signal cache ({message['Percentage']}%)")

    if fDownloadExtraMetadata:
      if progressReportCallback: progressReportCallback("\n")
      allDocIDs = GetAllDocIDsForSignals() # JScontext.
      DownloadExtraMetadata(authToken, ws, allDocIDs, progressReportCallback) # JScontext,

    return GenerateSignalCSV_ProcessingAPI()  # JScontext.

  finally:
    ws.close()


def DownloadExtraMetadata(authToken, ws, allDocIDs, progressReportCallback):  # JScontext,
  docIDs, iCountDocs = GetFirstBatchOfDocIDsToDownloadExtraMetadataForDocIDSet(allDocIDs, iMaxDocIDs=123)  # JScontext.
  while docIDs:
    if progressReportCallback: progressReportCallback(f"Downloading document information: {iCountDocs} docs remaining  ")
    ws.send(json.dumps({'authtoken': authToken, 'request': 'GetExtraMetadata', 'DocIDs': docIDs}))
    message = ReadMessageFromWebsocket(ws)
    if not message or 'ExtraMetadata' not in message: continue
    iCountDocs = AddNewExtraMetadata(message['ExtraMetadata'])  # JScontext.
    docIDs = GetNextBatchOfDocIDsToDownloadExtraMetadata(iMaxDocIDs=123)  # JScontext.
  if progressReportCallback: progressReportCallback(f"Downloading document information: done             ")


def GenerateFindMatchesCSV(authToken, sRuleset, DBsList, sRule, sStartDate=None, sEndDate=None, sTickerFilter=None, tags=None, progressReportCallback=None, fDownloadExtraMetadata=True):
  #JScontext = CreateJSContext()

  if isinstance(DBsList, str): DBsList = DBsList.split(';')

  ws = websocket.create_connection("wss://3c5qlj48hi.execute-api.us-west-2.amazonaws.com/main")

  try:
    ws.send(json.dumps({'authtoken': authToken,
                        'DB': DBsList, 'ruleset':sRuleset, 'rule':sRule,
                        'StartDate': sStartDate, 'EndDate': sEndDate, 'TickerFilter': sTickerFilter,
                        'Tags': tags,
                        'UseEntities': True}))
    _DBQuery2Info = {}
    while True:
      message = ReadMessageFromWebsocket(ws)
      if not message: continue

      if 'ExtraMetadata' in message or 'FullSignalData' in message:
        print(f"\nError: unexpected message: {message}", file=sys.stderr)
        continue

      #queryID = message["DB"] + ":" + message["query"]
      #if queryID not in _DBQuery2Info:
      if message["DB"] not in _DBQuery2Info:
        _DBQuery2Info[message["DB"]] = {}
      if message["query"] not in _DBQuery2Info[message["DB"]]:
        _DBQuery2Info[message["DB"]][message["query"]] = {
          'Total': 0, 'Checked': 0, 'Matches': 0,
          'CountPings': -1, 'NextPing': 0, 'PingsQueue': [],
          'DocID2DLCountsMap': {},
          'DateTicker2DLCountsMap': {}
        }
      DBInfo = _DBQuery2Info[message["DB"]][message["query"]]

      if 'Total' in message: DBInfo['Total'] = message['Total']
      if 'Checked' in message and DBInfo['Checked'] < message['Checked']: DBInfo['Checked'] = message['Checked']
      if 'CountPings' in message: DBInfo['CountPings'] = message['CountPings']
      if 'pingUpdate' in message:
        heapq.heappush(DBInfo['PingsQueue'], message['pingUpdate'])
        while DBInfo['PingsQueue'] and DBInfo['PingsQueue'][0] == DBInfo['NextPing']:
          heapq.heappop(DBInfo['PingsQueue'])
          DBInfo['NextPing'] += 1
        #print(f"pingUpdate: {_DBQuery2Info}    ", file=sys.stderr)

      iMatches = 0
      iTotal = 0
      iChecked = 0
      fAllPingsArrived = True
      for DBInfoQ in _DBQuery2Info.values():
        for DBInfo in DBInfoQ.values():
          iTotal += DBInfo['Total']
          iChecked += DBInfo['Checked']
          iMatches += DBInfo['Matches']
          if DBInfo['CountPings'] < 0  or  DBInfo['NextPing'] < DBInfo['CountPings']:
            fAllPingsArrived = False

      if 'Match' in message:
        match = message['Match']
        AddNewMatchForFindMatches(match[0], match[1])  # JScontext.
        if isinstance(match[1], str):
          iNewMatches = match[1].count('<EVENT')
        else:
          iNewMatches = len(match[1]['Events'])
        DBInfo['Matches'] += iNewMatches
        iMatches += iNewMatches

      if progressReportCallback:
        dCorpusPercent = iChecked * 100.0 / iTotal if iTotal > 0 else 100.0 if iTotal == 0 else -1
        sReportHTML = f"Searching (%.3f%%): {iMatches} matches out of {iChecked} sentences    " % (dCorpusPercent,)
        progressReportCallback(sReportHTML)

      fIsStopping = fAllPingsArrived and (iChecked >= iTotal) and (len(_DBQuery2Info) >= len(DBsList))
      #print(f"fIsStopping = {fIsStopping} = {fAllPingsArrived} and {iChecked >= iTotal} and {len(_DBQuery2Info) >= len(DBsList)}    ", file=sys.stderr)
      if fIsStopping and fDownloadExtraMetadata:
        if progressReportCallback: progressReportCallback("\n")
        allDocIDs = GetAllDocIDsForFindMatches()  # JScontext.
        DownloadExtraMetadata(authToken, ws, allDocIDs, progressReportCallback)  # JScontext,

      if fIsStopping: break

    return GenerateCSVForMatches_ProcessingAPI()  # JScontext.

  finally:
    ws.close()
