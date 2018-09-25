#!/bin/bash
pipenv run pybabel extract -F babel.cfg -o messages.pot .
pipenv run pybabel compile -d flasquelistan/translations
pipenv run pybabel update -i messages.pot -d flasquelistan/translations
