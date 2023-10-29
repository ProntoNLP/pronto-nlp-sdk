from pronto_nlp import fief

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
print(success)

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
print(success)

success = fief.list_parse_cache_dbs(
    user="user@example.com",
    password="password",
)
print(success)

success = fief.list_rulesets(
    user="user@example.com",
    password="password",
)
print(success)

success = fief.process_corpus(
    ruleset="Alpha",
    inputCSV="input_corpus.csv",
    outputCSV="output_corpus.csv",
    user="user@example.com",
    password="password",
    outputtype="events",
    numthreads=10
)
print(success)