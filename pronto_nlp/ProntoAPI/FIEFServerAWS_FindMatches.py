import ProcessingAPI

import argparse


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Generate a Find Matches CSV using FIEF Server.')
  parser.add_argument('-u', '--user', type=str, required=True)
  parser.add_argument('-p', '--password', type=str, required=True)
  parser.add_argument('-r', '--ruleset', help='Name of the ruleset (e.g. "Alpha" or "ESG")', required=True)
  parser.add_argument('-v', '--events', help='Regexp specifying events to extract (e.g. ".*" or "Acquisitions|Dividend")', required=True)
  parser.add_argument('-d', '--db', help='Name of the parse cache databse (e.g. "SEC_10K.db3")', required=True)
  parser.add_argument('-s', '--startdate', help='Start date (YYYY-MM-DD)', required=False)
  parser.add_argument('-e', '--enddate', help='End date (YYYY-MM-DD)', required=False)
  parser.add_argument('-t', '--tickerlist', help='Ticker list name (e.g. "SnP-500")', required=False)
  parser.add_argument('-g', '--tags', help='Tags (e.g. "#DocItem_Answer #SpeakerType_Executives_CEO")', required=False)
  parser.add_argument('-m', '--metadata', help='Download extra metadata flag', action="store_true")
  parser.add_argument('outputCSV', type=str, help='Path to the output CSV file')
  args = vars(parser.parse_args())

  authToken = ProcessingAPI.SignIn(args['user'], args['password'])
  print("Authentication successful")

  def ProgressReport(sMsg): print(sMsg, end='\r')
  sRule = "<" + args['events'] + ">"
  matchesCSV = ProcessingAPI.GenerateFindMatchesCSV(authToken, args['ruleset'], args['db'], sRule, args['startdate'], args['enddate'], args['tickerlist'], args['tags'], ProgressReport, args['metadata'])
  print()

  with open(args['outputCSV'], "w", encoding="utf-8", errors="ignore") as FOutCSV:
    FOutCSV.write(matchesCSV)
