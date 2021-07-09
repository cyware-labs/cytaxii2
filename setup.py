from setuptools import setup

setup(
    name='cytaxii2',
    version='1.0.0',
    description='This python package is created by Cyware Labs, as a TAXII 2 Client. This can be used easily by developers to connect to a TAXII 2 Server and perform actions',
    author='Cyware Labs',
    author_email='contact@cyware.com',
    license='MIT License',
    packages=['cytaxii2'],
    install_requires=['requests'],

    classifiers=[
        'Intended Audience :: Information Technology',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)
