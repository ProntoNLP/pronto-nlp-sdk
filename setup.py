from setuptools import setup, find_packages

setup(
    name='pronto_nlp',
    version='0.4.9',
    packages=find_packages(),
    install_requires=[
        'boto3',
        'gevent',
        'websocket-client',
        'requests',
        'websockets<14',
        'asyncio',
        'aiohttp',
        'aiofiles',
        'tqdm',
        'mixpanel',
        'pyjwt',
    ],
    entry_points={
        'console_scripts': [
            'pronto_nlp = pronto_nlp.cli:main',
        ],
    },
)
