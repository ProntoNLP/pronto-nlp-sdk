from setuptools import setup, find_packages

setup(
    name='pronto_nlp',
    version='0.1.2',
    packages=find_packages(),
    install_requires=[
        'boto3',
        'websocket',
    ],
)