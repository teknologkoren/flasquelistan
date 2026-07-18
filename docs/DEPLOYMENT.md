# Deploying Strequelistan

The app runs on a VPS as user `streque` in `/home/streque/flasquelistan`,
as a Docker container: gunicorn (1 worker, websocket-capable) listens on
`127.0.0.1:8000`, nginx (`streque.se`) terminates TLS, proxies to it and
serves `/static/` directly from the checkout. The database is SQLite in
`instance/`; it and the uploads directory are bind-mounted into the
container, so all state lives as plain files in the checkout.

## Deploying a new version

```
ssh <you>@<server>
sudo su - streque
cd ~/flasquelistan
git pull
GIT_SSH_COMMAND="ssh -i /home/streque/flasquelistan/ssh/github_deploy_key" \
    git submodule update --init songbook-viewer
docker compose up --build -d
```

Verify that the production website loads. If it doesn't:
`docker compose logs --tail 50 app`.

The image build compiles translations and builds the songbook — there are no
separate steps for those anymore.

### Rollback

```
git log --oneline           # find the last good commit
git reset --hard <commit>
GIT_SSH_COMMAND="ssh -i ~/.ssh/<songbook-deploy-key>" \
    git submodule update --init songbook-viewer
docker compose up --build -d
```

## The songbook

The songbook at `/bok/` is a separate React app, built automatically during
the image build from the `songbook-viewer` git submodule (private repo — the
SSH deploy key is in `ssh/` in the checkout, outside git). The build also needs two files that
are deliberately **not in any git repo** (they were placed there manually
once; ask a previous webmaster if they're missing):

```
ls songbook-viewer/public/Flerstämt.pdf songbook-viewer/songs.json
```

**The songbook is optional at build time.** If the submodule is not checked
out, or `songs.json` is missing, the image build prints a warning and
succeeds without the songbook — `/bok/` returns 404, everything else works.

To ship a songbook change: commit and push in the songbook-viewer repo, then
update the submodule pin here (`git add songbook-viewer` + commit + push) and
deploy as usual.

## Running the container elsewhere

`docker compose up --build -d` works the same on any machine with Docker.
Notes for a fresh environment:

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

## Server configuration notes

- nginx site: `/etc/nginx/sites-available/flasquelistan.conf`. It serves
  `/static/` straight from the checkout, verifies signed profile-picture URLs
  (`secure_link`) and resizes images (`image_filter` on an internal port),
  and proxies everything else — including `/socket.io` websockets — to the
  container on `127.0.0.1:8000`. A copy is documented in the private
  `teknologkoren/docs` repo (`streque.md`) — server configs are **never**
  committed to this public repo.
- There is no systemd unit for the app anymore: the container has
  `restart: unless-stopped`, so Docker restarts it on crashes and on boot.
- The nginx `Content-Security-Policy` on the `www` server block was widened
  for the songbook (Google Fonts + `worker-src blob:` for the PDF renderer).
  If the songbook loads but renders broken/unstyled, compare the live CSP
  against the copy in `teknologkoren/docs`.
- Secrets live in `instance/config.py` (never in git): Flask secret key,
  SMTP, Discord OAuth, and `IMAGE_SECRET` — which must equal the
  `secure_link` salt in the nginx config, since the app signs the URLs nginx
  verifies.
