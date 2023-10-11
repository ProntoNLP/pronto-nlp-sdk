import argparse
from pronto_nlp import macro

def main():
    main_parser = argparse.ArgumentParser(description='Pronto-NLP Toolkit')
    subparsers = main_parser.add_subparsers(dest='command')
    hd_parser = subparsers.add_parser('macro', help='Macro commands')
    hd_subparsers = hd_parser.add_subparsers(dest='sub_command')

    process_doc_parser = hd_subparsers.add_parser('process_document', help='Process document using Macro LLM.')
    process_doc_parser.add_argument('-u', '--user', type=str, required=True)
    process_doc_parser.add_argument('-p', '--password', type=str, required=True)
    process_doc_parser.add_argument('-i', '--input', type=str, help='Path to the input text file', required=True)
    process_doc_parser.add_argument('-o', '--output', type=str, help='Path to the output CSV file', required=True)
    process_doc_parser.add_argument('-n', '--maxparallel', type=int, help='Maximal number of sentences processed in parallel', default=8)

    args = main_parser.parse_args()

    if args.command == 'macro':
        if args.sub_command == 'process_document':
            args = vars(args)
            # Call the function to process the document
            macro.process_document(args['input'], args['output'], args['user'], args['password'], args['maxparallel'])

if __name__ == '__main__':
    main()