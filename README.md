# flasquelistan

## Setting up a development environment
### uv

We use `uv` for package management, you can find an introduction and
installation instructions over [at their website](https://docs.astral.sh/uv/).

You can use `uv sync` to manually initialize or update the virtual environment,
and then activate it in your shell.

    $ uv sync
    $ source .venv/bin/activate

Once the environment is activated, you can run commands normally, such as the ones
listed in the sections below.

Alternatively, you can use `uv run <command>` to run individual commands in the
virtual environment. This will automatically make sure the environment is up to
date.

### Initializing the application

Tell Flask where the app is located:

    $ export FLASK_APP=app.py

Now you might want to create the database and populate it with some mock data:

    $ flask initdb
    $ flask populatetestdb

Create a user with admin privileges with which you can log in:

    $ flask createadmin

Run the development server with helpful debug pages when exceptions occur:

    $ FLASK_DEBUG=1 flask run

The server is now live on [http://localhost:5000](http://localhost:5000).

If you haven't already created `/instance/config.py`, one is generated for you
with some sane defaults. The config in `/instance` overrides the default config
and is not checked in to git. The generated config sets the database file to be
created in `/instance`.

## Testing
[Pytest](https://docs.pytest.org/en/latest/) is used for testing, tests are
located in `tests/`. Run the tests from the root directory with

    $ pytest

You can also add the -n auto flag if you want to run the tests in paralell, and the -v flag for a more verbose output:

    $ pytest -v -n auto

If you want to only run a certain set of tests you can use the -k flag to filter the tests:

    $ pytest -k quote

### Messure test coverage
You can test the test coverage by running:

    $ coverage run -m pytest

And then show the result with:

    $ coverage report

