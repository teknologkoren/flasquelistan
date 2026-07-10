# Deploying Strequelistan

The app runs on a VPS as user `streque` in `/home/streque/flasquelistan`:
gunicorn (1 worker, websocket-capable) listens on a unix socket, nginx
(`streque.se`) proxies to it and serves `/static/` directly. The database is
SQLite in `instance/`. The songbook at `/bok/` is a separate React app, built
from the `songbook-viewer` git submodule into `flasquelistan/songbook_dist/`
(gitignored — it must be built on the server, it is never in git).

## 1. Deploying the app

```
ssh <you>@<server>
sudo su - streque
cd ~/flasquelistan
git pull
uv sync
exit                                        # back to your sudo-capable user
sudo systemctl restart flasquelistan
```

Verify that the production website loads. If it doesn't:
`sudo journalctl -u flasquelistan -n 50`.

If translations changed, also run `./update_translations.sh` (as `streque`,
before the restart).

### Rollback

```
git log --oneline          # find the last good commit
git reset --hard <commit>
uv sync
sudo systemctl restart flasquelistan
```

## 2. Deploying the songbook

The songbook build needs **Node 22 or newer**. Download a modern Node into the
home directory:

```
sudo su - streque
cd ~
curl -fsSL https://nodejs.org/dist/v22.23.1/node-v22.23.1-linux-x64.tar.xz | tar -xJ
export PATH="$HOME/node-v22.23.1-linux-x64/bin:$PATH"
node --version             # should print v22.23.1
```

(One-time download; on later deploys just re-run the `export PATH=...` line.)

Then check that the two files that are deliberately **not in git** are present
in the submodule (they were placed there manually once; ask a previous
webmaster if they're missing):

```
cd ~/flasquelistan
ls songbook-viewer/public/Flerstämt.pdf songbook-viewer/songs.json
```

Then build and restart. The script pulls the latest songbook-viewer commit
(needs the SSH deploy key that can read the private
`teknologkoren/songbook-viewer` repo), runs the npm build, and copies the
result into `flasquelistan/songbook_dist/`:

```
./build_songbook.sh ~/.ssh/<songbook-deploy-key>
exit
sudo systemctl restart flasquelistan
```

Verify: log in at https://www.streque.se and open 📘 Flerstämt (`/bok/`).

## 3. Server configuration notes

- systemd unit: `/etc/systemd/system/flasquelistan.service` (gunicorn,
  `GeventWebSocketWorker`, unix socket `/run/flasquelistan/flasquelistan.sock`).
- nginx site: `/etc/nginx/sites-available/flasquelistan.conf`. Snapshots of
  both live in jj/git history ("WIP: snapshot of live server configs").
- The nginx `Content-Security-Policy` on the `www` server block was widened
  for the songbook (Google Fonts + `worker-src blob:` for the PDF renderer).
  If the songbook loads but renders broken/unstyled, compare the live CSP
  against the snapshot.
- Secrets live in `instance/config.py` (never in git): Flask secret key, SMTP,
  Discord OAuth. The profile-picture `secure_link` salt is embedded in the
  nginx config. The songbook SSH deploy key is in `~streque/.ssh/`.

## 4. Where this is heading (Docker)

The plan (see [ROADMAP.md](ROADMAP.md)) is to replace steps 1–2 with a Docker
image that bakes in pinned Python and Node versions, builds the songbook
automatically during `docker compose up --build`, and makes the VPS's system
packages irrelevant. Until that lands, this document is the process.
