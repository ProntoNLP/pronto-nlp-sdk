from pronto_nlp import fief

print('Generating signal CSV')
signalCSV = fief.generate_signal_csv(
    ruleset="Alpha",
    db="SnP_Transcripts_ParseCache.db3",
    startdate="2021-01-01",
    enddate="2021-01-31",
    tags="#DocType_EarningsCalls_Answer #SpeakerType_Executives_CEO",
    outputCSV="output_signal.csv",
    user="user@example.com",
    password="password",
)
print(signalCSV)

print('Generating find matches CSV')
matchesCSV = fief.generate_find_matches_csv(
    ruleset="Alpha",
    events="Revenue",
    db="SnP_Transcripts_ParseCache.db3",
    startdate="2021-01-01",
    enddate="2021-01-02",
    tags="#SpeakerType_Executives_CEO",
    outputCSV="output_matches.csv",
    metadata=True,
    user="user@example.com",
    password="password",
)
print(matchesCSV)

print('Listing parse cache DBs')
dbs = fief.list_parse_cache_dbs(
    user="user@example.com",
    password="password",
)
print(dbs)

print('Listing rulesets')
rulesets = fief.list_rulesets(
    user="user@example.com",
    password="password",
)
print(rulesets)

print('Processing corpus')
resultsCSV = fief.process_corpus(
    ruleset="Alpha",
    inputCSV="../samples/UserDocsTest.csv",
    outputCSV="output_corpus.csv",
    user="user@example.com",
    password="password",
    outputtype="events",
    numthreads=10
)
print(resultsCSV)
