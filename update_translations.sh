cd flasquelistan
pybabel extract -F babel.cfg -k _l -k _ -o messages.pot .
pybabel update -i messages.pot -d translations
pybabel compile -d translations
