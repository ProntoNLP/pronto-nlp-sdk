from setuptools import setup, find_packages

setup(
    name='pronto_nlp',
    version='0.1.6',
    packages=find_packages(),
    install_requires=[
        'boto3',
        'websocket',
    ],
    entry_points={
        'console_scripts': [
            'pronto_nlp = pronto_nlp.cli:main',
        ],
    },
)