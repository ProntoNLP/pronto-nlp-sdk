from setuptools import setup, find_packages

setup(
    name='prontoNLP',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'boto3',
        'websocket',
    ],
)