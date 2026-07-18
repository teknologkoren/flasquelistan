# Deploying Strequelistan

The app runs on a VPS as user `streque` in `/home/streque/flasquelistan`:
gunicorn (1 worker, websocket-capable) listens on a unix socket, nginx
(`streque.se`) proxies to it and serves `/static/` directly. The database is
SQLite in `instance/`. The songbook at `/bok/` is a separate React app, built
from the `songbook-viewer` git submodule into `flasquelistan/songbook_dist/`
(gitignored — it must be built on the server, it is never in git).

## 0. Running with Docker

The repo has a multi-stage `Dockerfile` and a `docker-compose.yml` that will
replace steps 1–2 below once the server has been migrated (the migration
runbook lives in the private `teknologkoren/docs` repo). Until then, this is
how you run the containerized app anywhere:

```
docker compose up --build -d
```

This builds the songbook (Node 22) and the app image (Python 3.10, uv,
gunicorn on port 8000, bound to localhost only) and starts it with `instance/`
and `flasquelistan/static/uploads/` bind-mounted, so the database, local
config and uploads live as plain files in the checkout and survive rebuilds.

- **Songbook is optional at build time.** If the `songbook-viewer` submodule
  is not checked out, or `songbook-viewer/songs.json` is missing, the build
  prints a warning and succeeds without the songbook — `/bok/` returns 404,
  everything else works. With the submodule and both out-of-band files
  (`songs.json`, `public/Flerstämt.pdf`) in place, the songbook is built and
  served automatically.
- **First run:** an `instance/config.py` is auto-generated with `DEBUG = True`
  and placeholder secrets — fine locally, but it **must be edited** for
  anything reachable from the internet. Create an admin with
  `docker compose exec app flask createadmin`.
- **The container runs as UID 1000.** If the mounted `instance/` and uploads
  directories are owned by another user, set `user:` in a compose override.
- **Development:** `docker compose -f docker-compose.yml -f
  docker-compose.dev.yml up --build` bind-mounts the source tree and reloads
  gunicorn on changes, for prod-parity testing. Plain `flask run` per
  README.md remains the quickest dev loop.

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
- nginx site: `/etc/nginx/sites-available/flasquelistan.conf`. Copies of both
  are documented in the private `teknologkoren/docs` repo (`streque.md`) —
  server configs are **never** committed to this public repo.
- The nginx `Content-Security-Policy` on the `www` server block was widened
  for the songbook (Google Fonts + `worker-src blob:` for the PDF renderer).
  If the songbook loads but renders broken/unstyled, compare the live CSP
  against the snapshot.
- Secrets live in `instance/config.py` (never in git): Flask secret key, SMTP,
  Discord OAuth. The profile-picture `secure_link` salt is embedded in the
  nginx config. The songbook SSH deploy key is in `~streque/.ssh/`.

## 4. Migrating the server to Docker

The Docker image and compose files (section 0) are ready; the VPS still runs
the bare-gunicorn setup from sections 1–2. The one-time migration —
installing Docker, pointing the two nginx `proxy_pass` lines at
`http://127.0.0.1:8000`, retiring the old systemd unit — is documented step
by step in the private `teknologkoren/docs` repo (`streque.md`). After the
migration, deploying is `git pull && docker compose up --build -d` and
sections 1–2 become history.
