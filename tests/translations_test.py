import pytest

def test_missing_en_translation():
    f = open("flasquelistan/translations/en/LC_MESSAGES/messages.po").read()
    empty = 'msgstr ""\n\n'
    assert f.count(empty) == 0
