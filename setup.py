from setuptools import setup, find_packages

setup(
    name='pronto_nlp',
    version='0.3.5',
    packages=find_packages(),
    install_requires=[
        'boto3',
        'gevent',
        'websocket-client',
        'requests',
        'websockets',
        'asyncio',
        'aiohttp',
        'aiofiles',
        'tqdm',
    ],
    entry_points={
        'console_scripts': [
            'pronto_nlp = pronto_nlp.cli:main',
        ],
    },
)
