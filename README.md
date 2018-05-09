# flasquelistan

## Setting up a development environment
If you haven't already (why not!?), install
[Pipenv](https://docs.pipenv.org/). ✨🍰✨

Clone the repo and `cd` to the root folder. Run
```sh
$ pipenv install
```
then activate the environment with
```sh
$ pipenv shell
```

Tell Flask where the app is located:
```sh
$ export FLASK_APP=app.py
```

Now you might want to create the database and populate it with some mock data:
```sh
$ flask initdb
$ flask populatetestdb
```

Run the development server with helpful debug pages when exceptions occur:
```sh
$ FLASK_DEBUG=1 flask run
```
The server is now live on [http://localhost:5000](http://localhost:5000).

## Testing
[Pytest](https://docs.pytest.org/en/latest/) is used for testing, tests are
located in `tests/`. Run the tests with
```sh
$ pytest tests/flasquelistan_tests.py
```
