import ProcessingAPI
import sys

import argparse

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='List rulesets available for a user on the FIEF Server.')
  parser.add_argument('-u', '--user', type=str, required=True)
  parser.add_argument('-p', '--password', type=str, required=True)
  args = vars(parser.parse_args())

  authToken = ProcessingAPI.SignIn(args['user'], args['password'])
  print("Authentication successful", file=sys.stderr)

  rulesets = ProcessingAPI.GetListRulesets(authToken)
  for ruleset in rulesets:
    print(ruleset)
    rels = ProcessingAPI.GetListRelationsForRuleset(authToken, ruleset)
    for r in rels:
      print("  " + r)
    print()
