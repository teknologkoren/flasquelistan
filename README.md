# flasquelistan

## Setting up a development environment
Create a virtual environment:

```sh
python3 -m venv venv
```

Activate the environment:

```sh
. venv/bin/activate
```

Now you may either use `pip` directly to install the dependencies, or
you can install `pip-tools`. The latter is recommended.

### pip

```sh
pip install -r requirements.txt
```

### pip-tools
[pip-tools](https://github.com/jazzband/pip-tools) can keep your virtual
environment in sync with the `requirements.txt` file, as well as compiling a
new `requirements.txt` when adding/removing a dependency in `requirements.in`.

```sh
pip install pip-tools
pip-compile  # only necessary when adding/removing a dependency
pip-sync
```

### Initializing the application

Tell Flask where the app is located:
```sh
$ export FLASK_APP=app.py
```

Now you might want to create the database and populate it with some mock data:
```sh
$ flask initdb
$ flask populatetestdb
```

Create a user with admin privileges with which you can log in:
```sh
$ flask createadmin
```

Run the development server with helpful debug pages when exceptions occur:
```sh
$ FLASK_DEBUG=1 flask run
```
The server is now live on [http://localhost:5000](http://localhost:5000).

If you haven't already created `/instance/config.py`, one is generated for you
with some sane defaults. The config in `/instance` overrides the default config
and is not checked in to git. The generated config sets the database file to be
created in `/instance`.

## Testing
[Pytest](https://docs.pytest.org/en/latest/) is used for testing, tests are
located in `tests/`. Run the tests from the root directory with
```sh
$ pytest
```

You can also add the -n auto flag if you want to run the tests in paralell, and the -v flag for a more verbose output:
```sh
$ pytest -v -n auto
```

If you want to only run a certain set of tests you can use the -k flag to filter the tests:
```sh
$ pytest -k quote
```

### Messure test coverage
You can test the test coverage by running:
```sh
$ coverage run -m pytest
```
And then show the result with:
```sh
$ coverage report
```

