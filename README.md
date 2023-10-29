# Pronto NLP SDK

Pronto NLP SDK is a Python library for performing tasks using the Pronto NLP infrastructure.

## Installation

Install Pronto NLP SDK directly from GitHub using pip:

```bash
pip install git+https://github.com/ProntoNLP/pronto-nlp-sdk.git
```

## Usage

### From Code

You can use Pronto NLP SDK in your Python code as follows:

**Macro Module:**
```python
from pronto_nlp import macro

# Process document using Macro LLM.
macro.process_document(
    input="input.txt",
    output="output.csv",
    user="user@example.com",
    password="password"
)
```

**Fief Module:**
```python
from pronto_nlp import fief

# Generate a signal CSV using FIEF Server.
success = fief.generate_signal_csv(
    ruleset="Alpha",
    db="SnP_Transcripts_ParseCache.db3",
    startdate="2021-01-01",
    enddate="2021-01-02",
    tags="#DocItem_Answer #SpeakerType_Executives_CEO",
    outputCSV="output_signal.csv",
    user="user@example.com",
    password="password"
)
print(success)  # True if successful, False otherwise

# Generate a Find Matches CSV using FIEF Server.
success = fief.generate_find_matches_csv(
    ruleset="Alpha",
    events=".*",
    db="SnP_Transcripts_ParseCache.db3",
    startdate="2021-01-01",
    enddate="2021-12-02",
    tags="#DocItem_Answer #SpeakerType_Executives_CEO",
    outputCSV="output_matches.csv",
    metadata=True,
    user="user@example.com",
    password="password"
)
print(success)  # True if successful, False otherwise

# List parse cache databases available on the FIEF Server.
success = fief.list_parse_cache_dbs(
    user="user@example.com",
    password="password"
)
print(success)  # True if successful, False otherwise

# List rulesets available for a user on the FIEF Server.
success = fief.list_rulesets(
    user="user@example.com",
    password="password"
)
print(success)  # True if successful, False otherwise

# Process a corpus using FIEF Server.
success = fief.process_corpus(
    ruleset="Users/username/rulesetname",
    inputCSV="input_corpus.csv",
    outputCSV="output_corpus.csv",
    user="user@example.com",
    password="password",
    outputtype="XML",
    numthreads=10
)
print(success)  # True if successful, False otherwise
```

### From Command Line Interface (CLI)

You can also use Pronto NLP SDK from the command line:

Macro Commands
```bash
pronto_nlp macro process_document -u "user@example.com" -p "password" -i input.txt -o output.csv
```

Fief Commands
```bash
pronto_nlp fief generate_signal_csv -u "user@example.com" -p "password" -r "Alpha" -d "SnP_Transcripts_ParseCache.db3" -s "2021-01-01" -e "2021-01-02" -t "SnP-500" -g "#DocItem_Answer #SpeakerType_Executives_CEO" output_signal.csv

pronto_nlp fief generate_find_matches_csv -u "user@example.com" -p "password" -r "Alpha" -v ".*" -d "SnP_Transcripts_ParseCache.db3" -s "2021-01-01" -e "2021-01-02" -t "SnP-500" -g "#DocItem_Answer #SpeakerType_Executives_CEO" -m output_matches.csv

pronto_nlp fief list_parse_cache_dbs -u "user@example.com" -p "password"

pronto_nlp fief list_rulesets -u "user@example.com" -p "password"

pronto_nlp fief process_corpus -u "user@example.com" -p "password" -r "Users/username/rulesetname" -o XML -n 10 input_corpus.csv output_corpus.csv
```

## Parameters

- `input` (str): Path to the input text file.
- `output` (str): Path to the output CSV file.
- `user` (str): Your username.
- `password` (str): Your password.
- `maxparallel` (int, optional): Maximal number of sentences processed in parallel. Default is 8.
- `ruleset` (str, optional): Name of the ruleset (e.g. "Alpha" or "ESG").
- `db` (str, optional): Name of the parse cache database (e.g. "SnP_Transcripts_ParseCache.db3").
- `startdate` (str, optional): Start date (YYYY-MM-DD).
- `enddate` (str, optional): End date (YYYY-MM-DD).
- `tags` (str, optional): Tags (e.g. "#DocItem_Answer #SpeakerType_Executives_CEO").
- `events` (str, optional): Regexp specifying events to extract (e.g. ".*" or "Acquisitions|Dividend").
- `metadata` (bool, optional): Download extra metadata flag, set to true to download extra metadata.
- `outputtype` (str, optional): Type of the processing output, choices are ['XML', 'JSON', 'events']. Default is 'XML'.
- `numthreads` (int, optional): Number of concurrent processing threads. Default is 10.

## Support

For support or any questions, please reach out to us at [support@prontonlp.com](mailto:support@prontonlp.com).
