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

```python
from pronto_nlp import macro

# Process a document
macro.process_document(
    input="input.txt",
    output="output.csv",
    user="user@example.com",
    password="password"
)
```

### From Command Line Interface (CLI)

You can also use Pronto NLP SDK from the command line:

```bash
pronto_nlp macro process_document -u "user@example.com" -p "password" -i input.txt -o output.csv
```

Fief Commands
```bash
pronto_nlp fief generate_signal_csv -u "user@example.com" -p "password" -r "Alpha" -d "SEC_10K.db3" -s "2021-01-01" -e "2021-12-31" -t "SnP-500" -g "#DocItem_Answer #SpeakerType_Executives_CEO" output.csv

pronto_nlp fief generate_find_matches_csv -u "user@example.com" -p "password" -r "Alpha" -v ".*" -d "SEC_10K.db3" -s "2021-01-01" -e "2021-12-31" -t "SnP-500" -g "#DocItem_Answer #SpeakerType_Executives_CEO" -m output.csv

pronto_nlp fief list_parse_cache_dbs -u "user@example.com" -p "password"

pronto_nlp fief list_rulesets -u "user@example.com" -p "password"

pronto_nlp fief process_corpus -u "user@example.com" -p "password" -r "Users/username/rulesetname" -o XML -n 10 input.csv output.csv
```

## Parameters

- `input` (str): Path to the input text file.
- `output` (str): Path to the output CSV file.
- `user` (str): Your username.
- `password` (str): Your password.
- `maxparallel` (int, optional): Maximal number of sentences processed in parallel. Default is 8.
- `ruleset` (str, optional): Name of the ruleset (e.g. "Alpha" or "ESG").
- `db` (str, optional): Name of the parse cache database (e.g. "SEC_10K.db3").
- `startdate` (str, optional): Start date (YYYY-MM-DD).
- `enddate` (str, optional): End date (YYYY-MM-DD).
- `tickerlist` (str, optional): Ticker list name (e.g. "SnP-500").
- `tags` (str, optional): Tags (e.g. "#DocItem_Answer #SpeakerType_Executives_CEO").
- `events` (str, optional): Regexp specifying events to extract (e.g. ".*" or "Acquisitions|Dividend").
- `metadata` (bool, optional): Download extra metadata flag, set to true to download extra metadata.
- `outputtype` (str, optional): Type of the processing output, choices are ['XML', 'JSON', 'events']. Default is 'XML'.
- `numthreads` (int, optional): Number of concurrent processing threads. Default is 10.

## Support

For support or any questions, please reach out to us at [support@prontonlp.com](mailto:support@prontonlp.com).
