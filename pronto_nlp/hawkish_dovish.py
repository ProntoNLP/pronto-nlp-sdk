import sys
import json
import urllib.request
import boto3
import websocket
import argparse
import csv
import os
from . import ProcessingAPI_MacroLLM
# from .ProcessingAPI_MacroLLM import SignIn, ProcessSentences

# def process_document(args):
#     authToken = SignIn(args['user'], args['password'])
#     print("Authentication successful")

#     with open(args['input'], 'rt', encoding='utf-8', errors="ignore") as F:
#         sentences = F.readlines()
#     sentences = [s.strip() for s in sentences if s.strip()]

#     def ProgressReport(iAt):
#         print(f"Processed: {iAt} of {len(sentences)} ({iAt*100.0/len(sentences):.4f}%)", end='\r', file=sys.stderr)

#     allResults = ProcessSentences(authToken, sentences, ProgressReport, args['maxparallel'])
#     print(file=sys.stderr)

#     with open(args['output'], "w", encoding="utf-8", errors="ignore") as FOut:
#         CSVWriter = csv.writer(FOut, lineterminator='\n')
#         CSVWriter.writerow(["sentence", "result"])
#         for sentence, result in zip(sentences, allResults):
#             CSVWriter.writerow([sentence, json.dumps(result)])

def process_document(input: str, output: str, user: str, password: str, maxparallel=8):
    os.system('python ./hawkish_dovish.py  -u ' + user + ' -p ' + password + ' -i ' + input + ' -o ' + output + ' -n ' + str(maxparallel))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process document using Macro LLM.')
    parser.add_argument('-u', '--user', type=str, required=True)
    parser.add_argument('-p', '--password', type=str, required=True)
    parser.add_argument('-i', '--input', type=str, help='Path to the input text file', required=True)
    parser.add_argument('-o', '--output', type=str, help='Path to the output CSV file', required=True)
    parser.add_argument('-n', '--maxparallel', type=int, help='Maximal number of sentences processed in parallel', default=8)
    args = vars(parser.parse_args())

    process_document(args['input'], args['output'], args['user'], args['password'], args['maxparallel'])

    # python pronto_nlp/hawkish_dovish.py -u ... -p ... -i _DocForMacroTest.TXT -o RESULTS.CSV