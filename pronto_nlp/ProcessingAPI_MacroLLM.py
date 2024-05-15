# import os
# import re
# import sys
# import json
# import urllib.request
# import boto3
# import websocket
# import argparse
# import csv
#
#
# if os.environ.get("AWS_FIEF_STAGE", "prod") == "prod":
#   URL_WSS_LLMAPI = "wss://wss.prontonlp.net/llmapi"
# else:
#   URL_WSS_LLMAPI = "wss://9v62gujku4.execute-api.us-west-2.amazonaws.com/dev"
#
#
# def SignIn(user, password):
#   organization = "dev"
#   M = re.match(r'^(.*?):(.*)$', user)
#   if M:
#     organization = M.group(1)
#     user = M.group(2)
#   authURL = ("https://server-staging.prontonlp.com/token" if (organization == "dev" or organization == "staging") else
#              "https://server-prod.prontonlp.com/token")
#
#   requestObj = {"email": user, "password": password, "organization": organization}
#   body = json.dumps(requestObj, ensure_ascii=True).encode('ascii')
#   request = urllib.request.Request(authURL, data=body,
#                                    headers={"Content-Type": "application/json",
#                                             "pronto-granted": "R$w#8k@Pmz%2x2Dg#5fGz"})
#   try:
#     response = urllib.request.urlopen(request)
#     if response.status == 200:
#       result = response.read().decode('utf-8')
#       if not result.startswith('{'): return result
#   except:
#     pass
#
#   authParameters = {'USERNAME': user, 'PASSWORD': password}
#   client = boto3.client('cognito-idp', region_name='us-west-2')
#   response = client.initiate_auth(AuthFlow='USER_PASSWORD_AUTH',
#                                   AuthParameters=authParameters,
#                                   ClientId='88nt7a64nkbukf7r49p8q82ht')
#   authToken = response['AuthenticationResult']['IdToken']
#   return authToken
#
#
# def ReadMessageFromWebsocket(ws):
#   body = ws.recv()
#   if not body:
#     print("\nWarning: empty message - ignoring", file=sys.stderr)
#     return None
#   try:
#     return json.loads(body)
#   except:
#     print(f"\nError: JSON failed to decode message: '{body}'", file=sys.stderr)
#     raise
#
#
# def ProcessSentences(authToken, sentences, progressReportCallback=None, iMaxParallel=8):
#   results = [None for _ in sentences]
#   iCountResults = 0
#   ws = websocket.create_connection(URL_WSS_LLMAPI, header={"Authorization":authToken})
#   try:
#     iAt = 0
#     iInFlight = 0
#     while True:
#       while iInFlight < iMaxParallel and iAt < len(sentences):
#         ws.send(json.dumps({'authtoken': authToken, 'request': 'MacroLLM_ProcessSentence_Async',
#                             'index': iAt, 'sentence': sentences[iAt]}))
#         iAt += 1
#         iInFlight += 1
#       if iInFlight == 0: break
#       message = ReadMessageFromWebsocket(ws)
#       if not message: continue
#       if isinstance(message, str):
#         print(message, file=sys.stderr)
#         continue
#       #print(message, file=sys.stderr)
#       index, data = message['index'], message['data']
#       if results[index] is not None:
#         print("\nWarning: repeated result - ignoring", file=sys.stderr)
#         continue
#       results[index] = data
#       iCountResults += 1
#       iInFlight -= 1
#       if progressReportCallback: progressReportCallback(iCountResults)
#     return results
#   finally:
#     ws.close()
#
#
# if __name__ == '__main__':
#   parser = argparse.ArgumentParser(description='Process document using Macro LLM.')
#   parser.add_argument('-u', '--user', type=str, required=True)
#   parser.add_argument('-p', '--password', type=str, required=True)
#   parser.add_argument('-i', '--input', type=str, help='Path to the input text file', required=True)
#   parser.add_argument('-o', '--output', type=str, help='Path to the output CSV file', required=True)
#   parser.add_argument('-n', '--maxparallel', type=int, help='Maximal number of sentences processed in parallel', default=8)
#   args = vars(parser.parse_args())
#
#   authToken = SignIn(args['user'], args['password'])
#   print("Authentication successful")
#
#   with open(args['input'], 'rt', encoding='utf-8', errors="ignore") as F:
#     sentences = F.readlines()
#   sentences = [s.strip() for s in sentences if s.strip()]
#
#   def ProgressReport(iAt):
#     print(f"Processed: {iAt} of {len(sentences)} ({iAt*100.0/len(sentences):.4f}%)", end='\r', file=sys.stderr)
#   allResults = ProcessSentences(authToken, sentences, ProgressReport, args['maxparallel'])
#   print(file=sys.stderr)
#
#   with open(args['output'], "w", encoding="utf-8", errors="ignore") as FOut:
#     CSVWriter = csv.writer(FOut, lineterminator='\n')
#     CSVWriter.writerow(["sentence", "result"])
#     for sentence, result in zip(sentences, allResults):
#       CSVWriter.writerow([sentence, json.dumps(result)])
