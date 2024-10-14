# ProntoNLP SDK

ProntoNLP SDK is a Python library for performing tasks using the ProntoNLP infrastructure.
Users can take advantage of a wide array of tools and services, accessing state-of-the-art NLP models and analytics.
&nbsp;
## Installation

Install ProntoNLP SDK directly from GitHub using pip:

```bash
pip install git+https://github.com/ProntoNLP/pronto-nlp-sdk.git
```
&nbsp;
## User Authentication
Users must authenticate the ProntoNLP API with their org:username and password.
Your org name appears in the URL used for accessing the ProntoNLP platform.

For example, if your URL to access the ProntoNLP platform is:
'prontofund.prontonlp.com'

Then your username for should be:
`prontofund:user@example.com`

To begin using the SDK, initialize the ProntoPlatformAPI class with your user credentials.
```python
from pronto_nlp import PlatformAPI as pAPI

# Initialize the Pronto Platform API
pronto = pAPI.ProntoPlatformAPI(user, password)
```

&nbsp;

## PlatformAPI Module

The ProntoNLP Platform API SDK allows users to interact with the ProntoNLP platform for document analysis. 
This SDK provides methods for uploading and analyzing documents using ProntoNLPs advanced NLP Platform.

These are the main functions powered by the PlatformAPI Module:
1. Document Management and Analytics
2. Document Upload and Processing
3. Corpus Smart Search
4. Topic Research

&nbsp;
### Document Management and Analytics

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

&nbsp;
### Document Upload and Processing

The SDK supports asynchronous document processing for uploading, analyzing, and saving results. 
The main entry is via 'analyze_docs' which expects to receive a list or generator of document_requests.

Each document_request must contain:
- 'name': filepath to document
- 'onModel': name of model to use

If you provide an out_dir, results will be written out to JSON files in that directory.
If no out_dir is given, results will be returned for the user to further process.

The analyzer functions also accept a 'keep_results' parameter (default: True), which will store the document analytics on the ProntoNLP Platform in User Documents.
(Reminder: all documents uploaded are completely secure and private to the user)

All results will be written or returned as they become available.

Currently, the SDK supports '.txt', '.pdf', and string inputs.

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
                  {"name": "earningReport.pdf", "onModel": "LLMAlpha"}, 
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

&nbsp;
### Corpus Smart Search

The SDK also allows users to take advantage of ProntoNLP's Smart Search capabilities.
This feature enables powerful keyword-based searches by leveraging vector search technology and ProtonNLP's advanced analytics. 
Users can perform smart searches across specified data sources, document types, sectors, and user watchlists.
The system efficiently processes large datasets, allowing for precise retrieval of documents and insights using state-of-the-art vector representations.

Users can run searches using the 'run_smart_search' function.

Input parameters include:
- corpus: ['transcripts', 'sec', 'nonsec'] (required)
- searchQ: keyword / phrase to search (required)
- sector: a sector to search over (sector or watchlist must be specified)
- watchlist: a watchlist created by the user on the platform (sector or watchlist must be specified)
- sentiment: search for a specific sentiment ('positive', 'negative', 'neutral')
- companies: search by companies using a list of companyIds
- country: search by country of company HQ
- doc_type: a document type from the corpus to search over (default: 'transcripts'='Earnings Calls', 'sec'='10-Q', 'nonsec'='QR')
- start_date: start date (YYYY-MM-DD) for document search (default=current_date - 90 days)
- end_date: end date (YYYY-MM-DD) for document search (default=current_date)
- similarity_threshold: retrieve sentences with similarity scores greater than value (default=.50)

```python
srch_res = pronto.run_smart_search(corpus='sec', sector='Industrials', searchQ='AI')

srch_res = pronto.run_smart_search(corpus='transcripts', sector='Financials', searchQ='AI', country='United States', sentiment='positive', start_date='2024-01-01')

srch_res = pronto.run_smart_search(corpus='transcripts', companies=['32307', '21835', '29096', '18749'], searchQ='inventory')
```

In order to identify which companyIds to enter, users can search by company name or company ticker symbol:
```python
companyIdList = pronto.getCompanyId(companyName='tes')
pprint(companyIdList)
[{'id': '224263', 'name': 'Tesco Corporation (TESO)', 'ticker': 'TESO'},
 {'id': '106485352', 'name': 'Tesaro, Inc. (TSRO)', 'ticker': 'TSRO'},
 {'id': '552028024', 'name': 'Tesoro Gold Ltd (TSO)', 'ticker': 'TSO'},
 {'id': '94354', 'name': 'TESSCO Technologies Incorporated (TESS)', 'ticker': 'TESS'},
 {'id': '4493024', 'name': 'Tesson Holdings Limited (1201)', 'ticker': '1201'},
 {'id': '29053039', 'name': 'Tesla Energy Operations, Inc. (SCTY)', 'ticker': 'SCTY'},
 {'id': '27444752', 'name': 'Tesla, Inc. (TSLA)', 'ticker': 'TSLA'}]
```


Search results are returned as a dictionary, with each subsector/company as a key and the list of results as the corresponding value.
For more results, users can adjust the similarity threshold and/or limit the timeframe by using start and end dates.
Note that lowering the similarity threshold will return a wider variety of results.

Users can also define a watchlist of companies on the platform, and then choose to search over just those companies:

```python
srch_res = pronto.run_smart_search(corpus='transcripts', watchlist='favs', searchQ='supply issues', start_date='2024-01-01')
```

To view the possible input filters, users can call 'get_smart_search_filters' with the desired corpus, which returns a dictionary with the various document types, sectors, and watchlists available.
The supported corpuses are: ['transcripts', 'sec', 'nonsec']:

```python
resFilters = pronto.get_smart_search_filters(corpus='transcripts')
```

&nbsp;
### Topic Research

The SDK also allows users to take advantage of ProntoNLP's Topic Research capabilities.
This feature enables powerful financial analysis across a variety of topics, powered by our proprietary AlphaLLM and FIEF models. 
Users can perform topic research across specified data sources, document types, sectors, and user watchlists.

Users can run the analysis using the 'run_topic_research' function.

Input parameters include:
- corpus: ['transcripts', 'sec', 'nonsec'] (required)
- nResults: number of results to return (default=1,000)
- companies: search by companies using a list of companyIds
- country: search by country of company HQ
- sentiment: search for a specific sentiment ('positive', 'negative', 'neutral')
- eventType: name of eventtype / topic to search (default is all topics)
- freeText: keyword term to search, can be used in conjunction with eventType or separately (default is None)
- sector: a sector to search over (sector or watchlist must be specified)
- watchlist: a watchlist created by the user on the platform (sector or watchlist must be specified)
- doc_type: a document type from the corpus to search over (default: 'transcripts'='Earnings Calls', 'sec'='10-Q', 'nonsec'='QR')
- start_date: start date (YYYY-MM-DD) for document search (default=current_date - 90 days)
- end_date: end date (YYYY-MM-DD) for document search (default=current_date)

```python
topic_res = pronto.run_topic_research(corpus='transcripts', eventType='CashFlow', sector='Information Technology', start_date='2024-01-01', nResults=500)
```

Results are returned as a list of records ordered by the document date (desc), with each record detailing the event identified along with the relevant document metadata.
For the 'transcripts' corpus, the proprietary AlphaLLM model is used. For the others, the results are identified using the FIEF Alpha model.
Results are capped at 10,000 results per query, for more results, users can adjust the timeframe by using start and end dates.

Users can also define a watchlist of companies on the platform, and then choose to search over just those companies:

```python
srch_res = pronto.run_topic_research(corpus='sec', watchlist='favs', start_date='2024-01-01')
```

To view the possible eventType inputs, users can view the 'pronto.models' attribute:
```python
llmalpha_events = pronto.models['LLMAlpha']['EventTypes']
alpha_events = pronto.models['Alpha']['EventTypes']
```

To view the possible input filters, users can call 'get_smart_search_filters' with the desired corpus, which returns a dictionary with the various document types, sectors, and watchlists available.
The supported corpuses are: ['transcripts', 'sec', 'nonsec']:

```python
resFilters = pronto.get_smart_search_filters(corpus='transcripts')
```

&nbsp;
## FIEF Module
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

### Parameters

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

&nbsp;
# Support

For support or any questions, please reach out to us at [support@prontonlp.com](mailto:support@prontonlp.com).
