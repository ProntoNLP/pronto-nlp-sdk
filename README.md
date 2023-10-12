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

## Parameters

- `input` (str): Path to the input text file.
- `output` (str): Path to the output CSV file.
- `user` (str): Your username.
- `password` (str): Your password.

## Support

For support or any questions, please reach out to us at [support@prontonlp.com](mailto:support@prontonlp.com).
