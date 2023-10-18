import ProcessingAPI
import sys

import argparse


def PrintTagsTree(tagsTree, indent=0):
  if tagsTree[0]:
    print((' ' * indent) + tagsTree[0])
  for subTree in tagsTree[1]:
    PrintTagsTree(subTree, indent+2)


def PrintTags(tagsTree, prefix=None):
  name = tagsTree[0].replace(' ', '')
  if name:
    prefix = prefix + '_' + name if prefix else name
  if tagsTree[2]:
    print("  #" + prefix)
  for subTree in tagsTree[1]:
    PrintTags(subTree, prefix)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='List parse cache databases available on the FIEF Server.')
  parser.add_argument('-u', '--user', type=str, required=True)
  parser.add_argument('-p', '--password', type=str, required=True)
  args = vars(parser.parse_args())

  authToken = ProcessingAPI.SignIn(args['user'], args['password'])
  print("Authentication successful", file=sys.stderr)

  DBs = ProcessingAPI.GetListDBs(authToken)
  for sDB, tags in DBs:
    print(sDB)
    PrintTags(tags)
    print()
