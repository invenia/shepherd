.. _contributing:
Contributing
================

Issues
-------

If you run into a problems please file an issue on GitHub. When creating a new issue please label it as a bug or feature and provide the following information.

1. Platform - what OS are you running and what version of it?
2. Python Version - what python version are you running?
3. Shepherd Version - what version of shepherd are you running? NOTE: you can get the package version with pip by running ``pip freeze``.
4. Summary - what is the problem and what are you trying to do?
5. Steps to Reproduce - please provide the steps needed to reproduce the bug. Sample code and commands are helpful here.
6. Expected Result - what should the behaviour of those steps be? Should it error, return a different result, etc?
7. Actual Result - what is the current behaviour? If it errors please provide the stack trace.


Development
--------------

Please start by following the installation instructions in the README. Whether you're contributing code or fixing up documentation you should be using tox::

    pip install tox

When contributing code changes please install all supported versions of python listed in the .python-version file shown below.

.. literalinclude:: ../../.python-version

I'd suggest using `pyenv <https://github.com/yyuu/pyenv>`_ for managing your installed python versions.

After updating the documentation either in the source file docstrings or the .rst files in ``docs/source``, please run ``tox -e docs`` and view the changes locally before pushing them to github and making a pull request. After making code changes please run ``tox``, which will test your changes on all supported python versions and also run flake8 on the codebase as we try to follow the pep8 coding standards. You can also run pylint on your code with ``tox -e lint`` to find potential issues that the tests and flake8 might not catch, since, pylint is rather strict and opinionated we don't have a minimum required score, but generally if it is below 0.9 you probably have some issues that can be fixed.


Merge Requests
--------------------

Once, you've added/updated the documentation or codebase you can open a pull request on github. If you're simply fixing a small issue please make the pull request to 'master', otherwise make it to 'dev'. Also, if possible, try and pull the latest changes from the target branch into your source branch before making the pull request so that the changes can be automatically merged. Before your request can be merged all the tests on travis should pass and the test coverage should still remain above 90%. If possible try and pull in the most recent changes fromPlease include a description summarizing what the changes are for. For example, if they are fixing a bug please summarize how you fixed it and link to the issue for it.
