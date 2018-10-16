#!/bin/bash
export FLASK_APP=app.py
pipenv run flask initdb
pipenv run flask populatetestdb
pipenv run flask createadmin
./start_dev_server.sh
