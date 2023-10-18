import argparse
import json
import os
import pkg_resources
import boto3
from sagemaker.huggingface import HuggingFaceModel

sagemaker_client = boto3.client('sagemaker')  

def initialize_endpoint():

    # sagemaker config
    instance_type = "ml.g5.8xlarge"
    health_check_timeout = 300

    model_name = 'huggingface-pytorch-tgi-inference-2023-10-08-20-41-57-496'

    # Retrieve model information from SageMaker
    model_info = sagemaker_client.describe_model(ModelName=model_name)
    model_data = model_info['PrimaryContainer']['ModelDataUrl']
    image_uri = model_info['PrimaryContainer']['Image']
    role = model_info['ExecutionRoleArn']

    config = {
        'HF_MODEL_ID': "/opt/ml/model", # path to where sagemaker stores the model
        'SM_NUM_GPUS': json.dumps(1), # Number of GPU used per replica
        'MAX_INPUT_LENGTH': json.dumps(1024), # Max length of input text
        'MAX_TOTAL_TOKENS': json.dumps(2048), # Max length of the generation (including input text)
        'HF_MODEL_QUANTIZE': "bitsandbytes",# Comment in to quantize
    }
    
    # create HuggingFaceModel with the image uri
    llm_model = HuggingFaceModel(
        model_data=model_data,
        image_uri=image_uri,
        role=role,
        env=config,
        sagemaker_session=None
    )

    llm = llm_model.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name='huggingface-pytorch-tgi-inference-2023-10-08-20-41-59-104',  # Optional: specify endpoint name
        # volume_size=400, # If using an instance with local SSD storage, volume_size must be None, e.g. p4 but not p3
        container_startup_health_check_timeout=health_check_timeout, # 10 minutes to be able to load the model
    )

    return llm

def process_document(input: str, output: str, user: str, password: str, maxparallel=8):
    script_path = pkg_resources.resource_filename('pronto_nlp', 'ProcessingAPI_MacroLLM.py')
    os.system(f'python {script_path}  -u "{user}" -p "{password}" -i "{input}" -o "{output}" -n {str(maxparallel)}')

def run(args):
    # llm = initialize_endpoint()

    if os.path.isfile(args['input']):
        process_document(args['input'], args['output'], args['user'], args['password'], args['maxparallel'])
    elif os.path.isdir(args['input']):
        for file in os.listdir(args['input']):
            process_document(os.path.join(args['input'], file), args['output'], args['user'], args['password'], args['maxparallel'])
    
    # llm.delete_endpoint()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process document using Macro LLM.')
    parser.add_argument('-u', '--user', type=str, required=True)
    parser.add_argument('-p', '--password', type=str, required=True)
    parser.add_argument('-i', '--input', type=str, help='Path to the input text file', required=True)
    parser.add_argument('-o', '--output', type=str, help='Path to the output CSV file', required=True)
    parser.add_argument('-n', '--maxparallel', type=int, help='Maximal number of sentences processed in parallel', default=8)
    args = vars(parser.parse_args())

    run(args)