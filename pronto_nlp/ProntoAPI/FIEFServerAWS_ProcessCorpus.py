import ProcessingAPI

import sys
import argparse
import csv


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Process a corpus using FIEF Server.')
  parser.add_argument('-u', '--user', type=str, required=True)
  parser.add_argument('-p', '--password', type=str, required=True)
  parser.add_argument('-r', '--ruleset', help='Full name of the ruleset (e.g., "Users/username/rulesetname" for private rulesets)', required=True)
  parser.add_argument('-o', '--outputtype', choices=['XML', 'JSON', 'events'], help='Type of the processing output', default='XML')
  parser.add_argument('-n', '--numthreads', type=int, help='Number of concurrent processing threads', default=10)
  parser.add_argument('inputCSV', type=str, help='Path to the input corpus CSV file')
  parser.add_argument('outputCSV', type=str, help='Path to the output CSV file')
  args = vars(parser.parse_args())

  authToken = ProcessingAPI.SignIn(args['user'], args['password'])
  print("Authentication successful")

  with open(args['inputCSV'], "r", encoding="utf-8", errors="ignore") as FCSV:
    CSVReader = csv.reader(FCSV, csv.excel)
    headers = next(CSVReader)
    iTextColumn = -1
    for i, h in enumerate(headers):
      if h in ['document', 'doc', 'text', 'content', 'contents', 'input', 'sentence', 'article_text']:
        iTextColumn = i
        break
    if iTextColumn < 0: raise Exception("Missing document text column ('document', or 'text', or 'content', etc...)")

    iResultColumn = len(headers)
    headers.append('processing results')
    with open(args['outputCSV'], "w", encoding="utf-8", errors="ignore") as FOutCSV:
      CSVWriter = csv.writer(FOutCSV, lineterminator='\n')
      CSVWriter.writerow(headers)

      if(args['numthreads'] > 1):
        for row, result in ProcessingAPI.DoBatchProcessing(authToken, args['ruleset'], args['outputtype'],
                                             CSVReader, getTextFunc=lambda row: row[iTextColumn],
                                             numThreads=args['numthreads']):
          while len(row) <= iResultColumn: row.append("")
          row[iResultColumn] = result
          CSVWriter.writerow(row)

      else:
        for iDoc, row in enumerate(CSVReader):
          print(f"Processing doc: {iDoc+1}", end='\r', file=sys.stderr)
          text = row[iTextColumn].strip()
          result = ProcessingAPI.ProcessDoc(authToken, args['ruleset'], args['outputtype'], text) if text else ""
          while len(row) <= iResultColumn: row.append("")
          row[iResultColumn] = result
          CSVWriter.writerow(row)
        print(file=sys.stderr)
