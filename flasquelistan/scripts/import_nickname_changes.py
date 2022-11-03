import click
import sys
import sh
from pathlib import Path
from datetime import datetime
import re

from flasquelistan import models


def run(path):
    """Go through a number of database backups to populate the current db with old
    nickname changes. Please make sure to backup the database before running this
    script."""
    p = Path(path)
    strequelistan = list(p.glob('*.sqlite3'))
    flasquelistan = list(p.glob('*.sqlite'))

    db_queries = []
    for db in sorted(strequelistan):
        db_queries.append((db, "SELECT id, first_name, last_name, nickname FROM EmailUser_myuser WHERE nickname != '';"))

    for db in sorted(flasquelistan):
        db_queries.append((db, "SELECT id, first_name, last_name, nickname FROM user WHERE nickname != '';"))

    users = {}
    last_timestamp = datetime.fromtimestamp(0)

    with models.db.session.begin():
        for path, query in db_queries:
            m = re.search(r'(\d{8})T(\d{6})Z', str(path))
            date, time = m.group(1, 2)
            timestamp = datetime(int(date[:4]), int(date[4:6]), int(date[6:8]), int(time[:2]), int(time[2:4]), int(time[4:6]))

            output = sh.sqlite3(path, _in=query)
            lines = output.strip().split("\n")
            for line in lines:
                fields = line.strip().split("|")
                assert len(fields) == 4
                user_id, first_name, last_name, nickname = fields
                
                # Lex Oskar (he accidentally deleted his account)
                if user_id == '27':
                    user_id = '184'

                if user_id not in users:
                    users[user_id] = ""
                
                if nickname != users[user_id]:
                    print(f"Between {last_timestamp.isoformat()} and {timestamp.isoformat()}, {first_name} {last_name} ({user_id}) got nickname '{nickname}'.")
                    users[user_id] = nickname

                    user = models.User.query.get(int(user_id))
                    change = models.NicknameChange(
                        user_id=int(user_id),
                        nickname=nickname,
                        status=models.NicknameChangeStatus.APPROVED,
                        created_timestamp=timestamp,
                        reviewed_timestamp=timestamp,
                        lower_bound_timestamp=last_timestamp
                    )
                    user.nickname_changes.append(change)
                    models.db.session.add(change)
            
            last_timestamp = timestamp
        
        if len(models.db.session.dirty) == 0:
            click.echo("No changes to the database were performed.")
        elif click.confirm("Do you want to commit the changes to the database?"):
            models.db.session.commit()
        else:
            models.db.session.rollback()
