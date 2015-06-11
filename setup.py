from setuptools import setup, find_packages

setup(
    name="shepherd",
    description="Shepherd is a platform independent resource management package",
    long_description=open('README.rst').read(),
    version="0.0.1",
    license="Mozilla Public License 2.0",
    author="Rory Finnegan",
    author_email='rory.finnegan@invenia.ca',
    url="https://github.com/invenia/shepherd",

    packages=find_packages(),
    include_package_data=True,
    # scripts=['stackman'],

    install_requires=[
        'future',
        'Yapsy',
        'python-dateutil',
        'jsonschema',
        'pyyaml',
        'boto',
        'within',
        'anyconfig',
        'arbiter==0.4.0',
        'attrdict',
        'jinja2',
        'gitpython',
        'envoy'
    ],

    dependency_links=[
        'git+https://github.com/invenia/Arbiter.git@retries#egg=arbiter-0.4.0',
    ],

    classifiers=(
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators"
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ),
)
