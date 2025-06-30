import csv
from . import ProcessingAPI
import jwt
from .APIStats import APIUserStats


def user_login(user, password):
    """
    Authenticate the user and return an APIUserStats object.

    Args:
        user (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        APIUserStats: An instance of APIUserStats with the authenticated user.
    """
    authToken = ProcessingAPI.SignIn(user, password)
    print("Authentication successful")
    _user_stats = APIUserStats()
    _user_auth_obj = jwt.decode(authToken, options={"verify_signature": False})
    _user_stats.identify_user(_user_auth_obj)
    _user_stats.track(event_name='SDK FIEF Login')
    return authToken, _user_stats

def generate_signal_csv(ruleset: str, db: str, startdate: str, enddate: str, tags: str, outputCSV: str, user: str, password: str):
    """
    Generates a CSV file containing a signal based on the specified ruleset.

    Args:
        ruleset (str): The name of the ruleset to be used for generating the signal.
        db (str): The name of the database to be queried for data.
        startdate (str): The start date of the data range.
        enddate (str): The end date of the data range.
        tags (str): The tags to be applied to the signal.
        outputCSV (str): The path where the generated CSV file should be saved.
        user (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        signalCSV (str): The generated CSV file containing the signal.
    """

    authToken, _user_stats = user_login(user, password)

    def ProgressReport(sMsg): print(sMsg, end='\r')
    _user_stats.track(event_name='SDK FIEF Generate Signal', properties={'ruleset': ruleset, 'DB': db, 'startdate': startdate, 'enddate': enddate, 'tags': tags})

    signalCSV = ProcessingAPI.GenerateSignalCSV(authToken, ruleset, db, startdate, enddate, None, tags, ProgressReport)
    print()

    with open(outputCSV, "w", encoding="utf-8", errors="ignore") as FOutCSV:
        FOutCSV.write(signalCSV)
    
    return signalCSV

def generate_find_matches_csv(ruleset: str, events: str, db: str, startdate: str, enddate: str, tags: str, outputCSV: str, metadata: bool, user: str, password: str):
    """
    Generate a CSV file with matching results based on the given ruleset and parameters.

    Args:
        ruleset (str): The name of the ruleset to use for matching.
        events (str): The name of the events file to use.
        db (str): The name of the database to query.
        startdate (str): The start date for the matching process.
        enddate (str): The end date for the matching process.
        tags (str): A list of tags to include in the matching process.
        outputCSV (str): The name of the output CSV file.
        metadata (bool): A flag indicating whether to include metadata in the output.
        user (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        matchesCSV (str): The generated CSV file containing the matching results.
    """

    authToken, _user_stats = user_login(user, password)

    def ProgressReport(sMsg): print(sMsg, end='\r')
    _user_stats.track(event_name='SDK FIEF Generate Find Matches', properties={'ruleset': ruleset, 'events': events, 'DB': db, 'startdate': startdate, 'enddate': enddate, 'tags': tags})

    sRule = "<" + events + ">"
    matchesCSV = ProcessingAPI.GenerateFindMatchesCSV(authToken, ruleset, db, sRule, startdate, enddate, None, tags, ProgressReport, metadata)
    print()

    with open(outputCSV, "w", encoding="utf-8", errors="ignore") as FOutCSV:
        FOutCSV.write(matchesCSV)

    return matchesCSV

def list_parse_cache_dbs(user: str, password: str, print_output: bool = False):
    """
    List the parse cache databases for a given user and password.

    Args:
        user (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        DBs (list): A list of parse cache databases and their tags.
    """

    authToken, _user_stats = user_login(user, password)

    def print_tags(tagsTree, prefix=None):
        name = tagsTree[0].replace(' ', '')
        if name:
            prefix = prefix + '_' + name if prefix else name
        if tagsTree[2]:
            print("  #" + prefix)
        for subTree in tagsTree[1]:
            print_tags(subTree, prefix)

    DBs = ProcessingAPI.GetListDBs(authToken)

    if print_output:
        for sDB, tags in DBs:
            print(sDB)
            print_tags(tags)
            print()

    _user_stats.track(event_name='SDK FIEF List ParseCache DBs')

    return DBs

def list_rulesets(user: str, password: str, print_output: bool = False):
    """
    List the rulesets for a given user.

    Args:
        user (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        rulesets (dict): A dictionary of ruleset names and their relations.
    """

    authToken, _user_stats = user_login(user, password)

    rulesets = {}
    ruleset_names = ProcessingAPI.GetListRulesets(authToken)
    for ruleset_name in ruleset_names:
        rulesets[ruleset_name] = ProcessingAPI.GetListRelationsForRuleset(authToken, ruleset_name)

        if print_output:
            print(ruleset_name)
            for r in rulesets[ruleset_name]:
                print("  " + r)
            print()

    _user_stats.track(event_name='SDK FIEF List Rulesets', properties={'rulesets': list(rulesets.keys())})

    return rulesets

def process_corpus(ruleset: str, inputCSV: str, outputCSV: str, user: str, password: str, outputtype: ('XML', 'JSON', 'events') = 'XML', numthreads: int = 10):
    """
    Process a corpus using the specified ruleset, input CSV file, output CSV file, user credentials, and optional parameters.
    
    Args:
        ruleset (str): The name of the ruleset to use for matching.
        inputCSV (str): The name of the input CSV file.
        outputCSV (str): The name of the output CSV file.
        user (str): The username for authentication.
        password (str): The password for authentication.
        numthreads (str): The number of threads to use for processing. Defaults to 10.
        outputtype (str): The format of the output file. Defaults to 'XML'.

    Returns:
        outputCSV (str): The path to the generated CSV file containing the processing results.
    """

    authToken, _user_stats = user_login(user, password)

    _user_stats.track(event_name='SDK FIEF Process Corpus', properties={'ruleset': ruleset})

    with open(inputCSV, "r", encoding="utf-8", errors="ignore") as FCSV:
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
        with open(outputCSV, "w", encoding="utf-8", errors="ignore") as FOutCSV:
            CSVWriter = csv.writer(FOutCSV, lineterminator='\n')
            CSVWriter.writerow(headers)

            if(numthreads > 1):
                for row, result in ProcessingAPI.DoBatchProcessing(authToken, ruleset, outputtype, CSVReader, getTextFunc=lambda row: row[iTextColumn], numThreads=numthreads):
                    while len(row) <= iResultColumn: row.append("")
                    row[iResultColumn] = result
                    CSVWriter.writerow(row)

            else:
                for iDoc, row in enumerate(CSVReader):
                    print(f"Processing doc: {iDoc+1}", end='\r')
                    text = row[iTextColumn].strip()
                    result = ProcessingAPI.ProcessDoc(authToken, ruleset, outputtype, text) if text else ""
                    while len(row) <= iResultColumn: row.append("")
                    row[iResultColumn] = result
                    CSVWriter.writerow(row)
                print()

    return outputCSV
