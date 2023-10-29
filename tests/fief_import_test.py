from pronto_nlp import fief

# Generate a signal CSV using FIEF Server.
success = fief.generate_signal_csv(
    ruleset="Alpha",
    db="SnP_Transcripts_ParseCache.db3",
    startdate="2021-01-01",
    enddate="2021-01-31",
    tags="#DocType_EarningsCalls_Answer #SpeakerType_Executives_CEO",
    outputCSV="output_signal.csv",
    user="user@example.com",
    password="password",
)
print(success)  # True if successful, False otherwise

# Generate a Find Matches CSV using FIEF Server.
success = fief.generate_find_matches_csv(
    ruleset="Alpha",
    events=".*",
    db="SnP_Transcripts_ParseCache.db3",
    startdate="2021-01-01",
    enddate="2021-01-02",
    tags="#SpeakerType_Executives_CEO",
    outputCSV="output_matches.csv",
    metadata=True,
    user="user@example.com",
    password="password",
)
print(success)  # True if successful, False otherwise

# List parse cache databases available on the FIEF Server.
success = fief.list_parse_cache_dbs(
    user="user@example.com",
    password="password",
)
print(success)  # True if successful, False otherwise

# List rulesets available for a user on the FIEF Server.
success = fief.list_rulesets(
    user="user@example.com",
    password="password",
)
print(success)  # True if successful, False otherwise

# Process a corpus using FIEF Server.
success = fief.process_corpus(
    ruleset="Alpha",
    inputCSV="input_corpus.csv",
    outputCSV="output_corpus.csv",
    user="user@example.com",
    password="password",
    outputtype="events",
    numthreads=10
)
print(success)  # True if successful, False otherwise