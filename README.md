# ProntoNLP SDK

ProntoNLP SDK is a Python library for performing tasks using the ProntoNLP infrastructure.

## Installation

Install ProntoNLP SDK directly from GitHub using pip:

```bash
pip install git+https://github.com/ProntoNLP/pronto-nlp-sdk.git
```

## Usage

### User Authentication
Users must authenticate each request with their org:username and password.
Your org name appears in the URL used for accessing the ProntoNLP platform.

For example, if your URL to access the ProntoNLP platform is:
'prontofund.prontonlp.com'

Then your username for all API requests should be:

`prontofund:user@example.com`

### PlatformAPI Module

The ProntoNLP Platform API SDK allows users to interact with the ProntoNLP platform for document analysis. 
This SDK provides methods for uploading and analyzing documents using ProntoNLPs state-of-the-art NLP Platform.

All documents uploaded via the PlatformAPI are also readily accessible on the ProntoNLP Platform for viewing and analytics.
Simply log in to the platform and navigate to the 'Documents' tab on the left ribbon to view.

To begin using the SDK, initialize the ProntoPlatformAPI class with your user credentials.
```python
from pronto_nlp import PlatformAPI as pAPI

# Initialize the Pronto Platform API
pronto = pAPI.ProntoPlatformAPI(user, password)
```

**Retrieve Document List**

You can retrieve the list of your previously analyzed documents available on the platform using the get_doc_list method.
```python
# Get the list of documents
docs = pronto.get_doc_list()
print("Documents:", docs)
```

**Retrieve Document Analytics**

To get the analytics for a specific document which was already analzyed, use the get_doc_analytics method. 
This method takes a document object from the list retrieved by get_doc_list.
```python
# Get the analytics for the first document in the list
doc_analytics = pronto.get_doc_analytics(docs[0])
print("Document Analytics:", doc_analytics)
```

**Delete a Document**

If you need to delete a document from the platform, use the delete_doc method. This method also takes a document object from the list retrieved by get_doc_list.
```python
# Delete the first document in the list
pronto.delete_doc(docs[0])
print("Document deleted successfully")
```

### Asynchronous Document Processing

The SDK supports asynchronous document processing for uploading, analyzing, and saving results. 
The main entry is via 'analyze_docs' which expects to receive a list or generator of document_requests.

Each document_request must contain:
- 'name': filepath to document
- 'onModel': name of model to use

If you provide an out_dir, results will be written out to JSON files in that directory.
If no out_dir is given, results will be returned for the user to further process.
All results will be written or returned as they become available.

Currently, the SDK supports '.txt' inputs only.

The models can be any of your FIEF models (see below) or one of ProntoNLP's LLMs.

LLM Models currently available are: 'LLMAlpha'.

Here is an example of how to process documents asynchronously
```python
from pronto_nlp import PlatformAPI as pAPI
import asyncio

async def process_documents():
    # Initialize the Pronto Platform API
    pronto = pAPI.ProntoPlatformAPI(user, password)

    # Define the document models to be processed
    doc_models = [{"name": "brokerReport.txt", "onModel": "LLMAlpha"}, 
                  {"name": "earningReport.txt", "onModel": "LLMAlpha"}, 
                  {"name": "earningReport.txt", "onModel": "Alpha"}]

    # Analyze documents and optionally save the results to a specified directory
    async for result in pronto.analyze_docs(doc_models, out_dir='./pronto_results'):
        print("Saved result:", result)

    # Alternatively, analyze documents without saving results to a directory
    # async for result in pronto.analyze_docs(doc_models):
    #     print("Received result:", result['doc_meta'])

if __name__ == "__main__":
    asyncio.run(process_documents())
```

Users can also process text strings directly
```python
from pronto_nlp import PlatformAPI as pAPI
import asyncio

async def process_texts():
    pronto = pAPI.ProntoPlatformAPI(user, password)

    async for result in pronto.analyze_text([
        "Fourth quarter Data Center growth was driven by both training and inference of generative AI and large language models across a broad set of industries, use cases and regions.",
        "During fiscal year '24, we utilized cash of $9.9 billion towards shareholder returns, including $9.5 billion in share repurchases."
        ],
        model='LLMAlpha',
        out_dir='./pronto_results'):
        print("Saved result:", result)

if __name__ == "__main__":
    asyncio.run(process_texts())
```



### FIEF Module
```python
from pronto_nlp import fief

# Generate a signal CSV using FIEF Server.
success = fief.generate_signal_csv(
    ruleset="Alpha",
    db="SnP_Transcripts_ParseCache.db3",
    startdate="2021-01-01",
    enddate="2021-12-31",
    tags="#DocType_EarningsCalls #SpeakerType_Executives_CEO #Sector_Energy",
    outputCSV="output_signal.csv",
    user="org:user@example.com",
    password="password"
)
print(success)  # True if successful, False otherwise

# Generate a Find Matches CSV using FIEF Server.
success = fief.generate_find_matches_csv(
    ruleset="Alpha",
    events="Revenue|Margin",
    db="SnP_Transcripts_ParseCache.db3",
    startdate="2022-01-01",
    enddate="2022-04-31",
    tags="#Sector_Financials #SpeakerType_Executives_CFO",
    outputCSV="output_matches.csv",
    metadata=True,
    user="org:user@example.com",
    password="password"
)
print(success)  # True if successful, False otherwise

# Process a corpus using FIEF Server.
success = fief.process_corpus(
    ruleset="Alpha",
    inputCSV="input_corpus.csv",
    outputCSV="output_corpus.csv",
    user="org:user@example.com",
    password="password",
    outputtype="events",
    numthreads=10
)
print(success)  # True if successful, False otherwise

# List parse cache databases available on the FIEF Server.
success = fief.list_parse_cache_dbs(
    user="org:user@example.com",
    password="password"
)
print(success)  # True if successful, False otherwise

# List rulesets available for a user on the FIEF Server.
success = fief.list_rulesets(
    user="org:user@example.com",
    password="password"
)
print(success)  # True if successful, False otherwise
```

**Custom Rulesets**

Users can also run Find Matches and Process Corpus functions using a Custom Ruleset built on the Platform.  
Simply reference the ruleset as:  ruleset="Users/org/ruleset-name"

```python
ruleset="Users/prontofund/pfAlpha"
```

### From Command Line Interface (CLI)

You can also use Pronto NLP SDK from the command line:

**FIEF Commands**
```bash
pronto_nlp fief generate_signal_csv -u "org:user@example.com" -p "password" -r "Alpha" -d "SnP_Transcripts_ParseCache.db3" -s "2021-01-01" -e "2021-12-31" -g "#DocType_EarningsCalls #SpeakerType_Executives_CEO #Sector_Energy" output_signal.csv

pronto_nlp fief generate_find_matches_csv -u "org:user@example.com" -p "password" -r "Alpha" -v ".*" -d "SnP_Transcripts_ParseCache.db3" -s "2021-01-01" -e "2021-04-31" -g "#Sector_ConsumerStaples #SpeakerType_Executives" -m output_matches.csv

pronto_nlp fief list_parse_cache_dbs -u "org:user@example.com" -p "password"

pronto_nlp fief list_rulesets -u "org:user@example.com" -p "password"

pronto_nlp fief process_corpus -u "org:user@example.com" -p "password" -r "Alpha" -o events -n 10 input_corpus.csv output_corpus.csv
```

## Parameters

- `input` (str): Path to the input text file.
- `output` (str): Path to the output CSV file.
- `user` (str): Your org:username.
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
