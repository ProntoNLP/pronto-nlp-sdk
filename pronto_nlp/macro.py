import os
import pkg_resources
from pronto_nlp import generate_command_string

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
        bool: True if the document processing was successful, False otherwise.
    """
    script_path = pkg_resources.resource_filename('pronto_nlp', 'ProcessingAPI_MacroLLM.py')
    parameters = {'input': input, 'output': output, 'maxparallel': maxparallel, 'user': user, 'password': password}
    success = os.system(generate_command_string(script_path, parameters))

    return bool(not success)