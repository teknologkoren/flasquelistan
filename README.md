# flasquelistan

## Setting up a development environment
If you haven't already (why not!?), install
[Pipenv](https://docs.pipenv.org/). ✨🍰✨

Clone the repo and `cd` to the root folder. Run
```sh
$ pipenv sync
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
located in `tests/`. Run the tests with
```sh
$ pytest tests/flasquelistan_test.py
```
