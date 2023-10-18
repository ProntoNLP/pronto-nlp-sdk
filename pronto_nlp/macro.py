import os
import pkg_resources

def process_document(input: str, output: str, user: str, password: str, maxparallel=8):
    script_path = pkg_resources.resource_filename('pronto_nlp', 'ProcessingAPI_MacroLLM.py')
    os.system(f'python {script_path}  -u "{user}" -p "{password}" -i "{input}" -o "{output}" -n {str(maxparallel)}')
