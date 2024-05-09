import csv
import json
from . import ProcessingAPI_MacroLLM

def process_document(input: str, output: str, user: str, password: str, maxparallel=8):
    """
    Process document using Macro LLM.

    Args:
        input (str): Path to the input text file.
        output (str): Path to the output CSV file.
        user (str): The username for authentication.
        password (str): The password for authentication.
        maxparallel (int, optional): The maximum number of parallel processes. Defaults to 8.

    Returns:
        allResults (list): A list of results.
    """

    authToken = ProcessingAPI_MacroLLM.SignIn(user, password)
    print("Authentication successful")

    with open(input, 'rt', encoding='utf-8', errors="ignore") as F:
        sentences = F.readlines()
    sentences = [s.strip() for s in sentences if s.strip()]

    def ProgressReport(iAt):
        print(f"Processed: {iAt} of {len(sentences)} ({iAt*100.0/len(sentences):.4f}%)", end='\r')
    allResults = ProcessingAPI_MacroLLM.ProcessSentences(authToken, sentences, ProgressReport, maxparallel)
    print()

    with open(output, "w", encoding="utf-8", errors="ignore") as FOut:
        CSVWriter = csv.writer(FOut, lineterminator='\n')
        CSVWriter.writerow(["sentence", "result"])
        for sentence, result in zip(sentences, allResults):
            CSVWriter.writerow([sentence, json.dumps(result)])

    return allResults