import argparse
from . import macro, fief

def main():
    main_parser = argparse.ArgumentParser(description='Pronto-NLP Toolkit')
    subparsers = main_parser.add_subparsers(dest='command')

    macro_parser = subparsers.add_parser('macro', help='Macro commands')
    macro_subparsers = macro_parser.add_subparsers(dest='sub_command')

    process_doc_parser = macro_subparsers.add_parser('process_document', help='Process document using Macro LLM.')
    process_doc_parser.add_argument('-u', '--user', type=str, required=True)
    process_doc_parser.add_argument('-p', '--password', type=str, required=True)
    process_doc_parser.add_argument('-i', '--input', type=str, help='Path to the input text file', required=True)
    process_doc_parser.add_argument('-o', '--output', type=str, help='Path to the output CSV file', required=True)
    process_doc_parser.add_argument('-n', '--maxparallel', type=int, help='Maximal number of sentences processed in parallel', default=8)

    fief_parser = subparsers.add_parser('fief', help='Fief commands')
    fief_subparsers = fief_parser.add_subparsers(dest='sub_command')
    
    generate_signal_csv_parser = fief_subparsers.add_parser('generate_signal_csv', help='Generate a signal CSV using FIEF Server.')
    generate_signal_csv_parser.add_argument('-u', '--user', type=str, required=True)
    generate_signal_csv_parser.add_argument('-p', '--password', type=str, required=True)
    generate_signal_csv_parser.add_argument('-r', '--ruleset', help='Name of the ruleset (e.g. "Alpha" or "ESG")', required=True)
    generate_signal_csv_parser.add_argument('-d', '--db', help='Name of the parse cache databse (e.g. "SnP_Transcripts_ParseCache.db3")', required=True)
    generate_signal_csv_parser.add_argument('-s', '--startdate', help='Start date (YYYY-MM-DD)', required=False)
    generate_signal_csv_parser.add_argument('-e', '--enddate', help='End date (YYYY-MM-DD)', required=False)
    generate_signal_csv_parser.add_argument('-g', '--tags', help='Tags (e.g. "#DocItem_Answer #SpeakerType_Executives_CEO")', required=False)
    generate_signal_csv_parser.add_argument('outputCSV', type=str, help='Path to the output CSV file')

    generate_find_matches_csv_parser = fief_subparsers.add_parser('generate_find_matches_csv', help='Generate a Find Matches CSV using FIEF Server.')
    generate_find_matches_csv_parser.add_argument('-u', '--user', type=str, required=True)
    generate_find_matches_csv_parser.add_argument('-p', '--password', type=str, required=True)
    generate_find_matches_csv_parser.add_argument('-r', '--ruleset', help='Name of the ruleset (e.g. "Alpha" or "ESG")', required=True)
    generate_find_matches_csv_parser.add_argument('-v', '--events', help='Regexp specifying events to extract (e.g. ".*" or "Acquisitions|Dividend")', required=True)
    generate_find_matches_csv_parser.add_argument('-d', '--db', help='Name of the parse cache databse (e.g. "SnP_Transcripts_ParseCache.db3")', required=True)
    generate_find_matches_csv_parser.add_argument('-s', '--startdate', help='Start date (YYYY-MM-DD)', required=False)
    generate_find_matches_csv_parser.add_argument('-e', '--enddate', help='End date (YYYY-MM-DD)', required=False)
    generate_find_matches_csv_parser.add_argument('-g', '--tags', help='Tags (e.g. "#DocItem_Answer #SpeakerType_Executives_CEO")', required=False)
    generate_find_matches_csv_parser.add_argument('-m', '--metadata', help='Download extra metadata flag', action="store_true")
    generate_find_matches_csv_parser.add_argument('outputCSV', type=str, help='Path to the output CSV file')
    
    list_parse_cache_dbs_parser = fief_subparsers.add_parser('list_parse_cache_dbs', help='List parse cache databases available on the FIEF Server.')
    list_parse_cache_dbs_parser.add_argument('-u', '--user', type=str, required=True)
    list_parse_cache_dbs_parser.add_argument('-p', '--password', type=str, required=True)

    list_rulesets_parser = fief_subparsers.add_parser('list_rulesets', help='List rulesets available for a user on the FIEF Server.')
    list_rulesets_parser.add_argument('-u', '--user', type=str, required=True)
    list_rulesets_parser.add_argument('-p', '--password', type=str, required=True)

    process_corpus_parser = fief_subparsers.add_parser('process_corpus', help='Process a corpus using FIEF Server.')
    process_corpus_parser.add_argument('-u', '--user', type=str, required=True)
    process_corpus_parser.add_argument('-p', '--password', type=str, required=True)
    process_corpus_parser.add_argument('-r', '--ruleset', help='Full name of the ruleset (e.g., "Users/username/rulesetname" for private rulesets)', required=True)
    process_corpus_parser.add_argument('-o', '--outputtype', choices=['XML', 'JSON', 'events'], help='Type of the processing output', default='XML')
    process_corpus_parser.add_argument('-n', '--numthreads', type=int, help='Number of concurrent processing threads', default=10)
    process_corpus_parser.add_argument('inputCSV', type=str, help='Path to the input corpus CSV file')
    process_corpus_parser.add_argument('outputCSV', type=str, help='Path to the output CSV file')

    args = main_parser.parse_args()

    args_items = vars(args)

    if args.command == 'macro':
        if args.sub_command == 'process_document':
            macro.process_document(args_items['input'], args_items['output'], args_items['user'], args_items['password'], args_items['maxparallel'])

    if args.command == 'fief':
        if args.sub_command == 'generate_signal_csv':
            fief.generate_signal_csv(args_items['ruleset'], args_items['db'], args_items['startdate'], args_items['enddate'], args_items['tags'], args_items['outputCSV'], args_items['user'], args_items['password'])
        if args.sub_command == 'generate_find_matches_csv':
            fief.generate_find_matches_csv(args_items['ruleset'], args_items['events'], args_items['db'], args_items['startdate'], args_items['enddate'], args_items['tags'], args_items['outputCSV'], args_items['metadata'], args_items['user'], args_items['password'])
        if args.sub_command == 'list_parse_cache_dbs':
            fief.list_parse_cache_dbs(args_items['user'], args_items['password'], True)
        if args.sub_command == 'list_rulesets':
            fief.list_rulesets(args_items['user'], args_items['password'], True)
        if args.sub_command == 'process_corpus':
            fief.process_corpus(args_items['ruleset'], args_items['inputCSV'], args_items['outputCSV'], args_items['user'], args_items['password'], args_items['outputtype'], args_items['numthreads'])

if __name__ == '__main__':
    main()