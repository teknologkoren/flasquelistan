#!/bin/bash
export FLASK_APP=app.py
sh update_translations.sh
flask initdb
flask populatetestdb
flask createadmin
./start_dev_server.sh
