# Deploying Strequelistan

This describes what a production deployment of the app needs. The
`Dockerfile` and compose files are for local development only (see
README.md); production runs the app directly.

## Requirements

- Python (see `requires-python` in `pyproject.toml`) and
  [uv](https://docs.astral.sh/uv/)
- Node and npm, to build the songbook (optional, see below)
- ffmpeg, for `process_gifs.py` (see below)
- A front-end web server in front of gunicorn (see below)

## Setting up

In a checkout of the repo:

```
uv sync --locked --no-dev
(cd flasquelistan && ../.venv/bin/pybabel compile -d translations)
```

Create `instance/config.py` before the first start. Otherwise one is
auto-generated with `DEBUG = True` and placeholder secrets — fine locally,
but it **must be edited** for anything reachable from the internet. It holds
all the secrets, which never go in git: at least `SECRET_KEY`,
`IMAGE_SECRET` (see below), `DEBUG = False` and
`SESSION_COOKIE_SECURE = True`, plus the SMTP and Discord settings from
`config.py` if you use them.

Run the app with gunicorn and a single websocket-capable worker (the
`/socket.io` websockets need it):

```
.venv/bin/gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
    -w 1 -b <address> app:app
```

Keep it running with a process manager that restarts it on failure and starts
it on boot. Create an admin user with
`FLASK_APP=app.py .venv/bin/flask createadmin`.

## The front-end web server

The front-end server terminates TLS and proxies requests to gunicorn,
including the websocket upgrade on `/socket.io`. In production the app
expects it to also handle:

- **Static files:** serve `/static/` from `flasquelistan/static/`. The app
  generates cache-busted URLs of the form `/static/c<hash>/<path>`
  (`cachebust.py`), which must map to `/static/<path>`.
- **Signed image URLs:** the app signs the URLs of uploaded images with an
  expiry time and an MD5 hash over the expiry, the path, the client's address
  and `IMAGE_SECRET`, in the format of nginx's `secure_link_md5` (see
  `generate_secure_path_hash` in `util.py`). The server must verify them with
  the same secret.
- **Resized images:** outside debug mode, the app links to resized images at
  `.../img<width>/<filename>` (widths 200 to 1600). The server must serve
  those resized from the originals. Animated GIF and WebP files can be served
  unresized. Resizing decodes the whole original in memory (with libgd about
  4 bytes per pixel), so a single huge upload, such as a 108-megapixel phone
  photo, needs ~430 MB per resize. Cache the resized images.

## Deploying a new version

```
git pull
uv sync --locked --no-dev
(cd flasquelistan && ../.venv/bin/pybabel compile -d translations)
```

Then rebuild the songbook if its submodule pin moved (see below), and
restart gunicorn.

The compiled translations (`*.mo`) are gitignored, so compile them after
every pull. Only compile in production: `update_translations.sh` also
re-extracts the catalogs, which rewrites tracked files in the checkout and can
make the next `git pull` conflict. Run it in development when you change
strings, and commit the result.

To roll back, `git reset --hard <commit>` to the last good commit and repeat
the steps above.

## The songbook

The songbook at `/bok/` is a separate React app in the `songbook-viewer` git
submodule (a private repo, so it needs read access to it, e.g. a deploy
key). It is built with npm into `flasquelistan/songbook_dist/` (gitignored),
which the app serves. The build also needs two files that are deliberately
**not in any git repo** (ask a previous webmaster if they're missing):

```
ls songbook-viewer/public/Flerstämt.pdf songbook-viewer/songs.json
```

To build the songbook at the pinned commit:

```
git submodule update --init songbook-viewer
(cd songbook-viewer && npm ci && npm run build)
rm -rf flasquelistan/songbook_dist
mkdir flasquelistan/songbook_dist
cp -r songbook-viewer/dist/. flasquelistan/songbook_dist/
```

`build_songbook.sh [path-to-ssh-key]` runs the same npm build, but it
updates the submodule to the latest commit of songbook-viewer's `main`
(`--remote`) instead of the pinned commit, and copies over the old build
without clearing it first.

If the songbook has not been built, `/bok/` returns 404 and everything else
works.

To ship a songbook change: commit and push in the songbook-viewer repo, then
update the submodule pin here (`git add songbook-viewer` + commit + push),
deploy, and rebuild the songbook.

## Converting GIF profile pictures

`process_gifs.py` converts the oldest GIF profile picture to an animated WebP
with ffmpeg (one per run) and updates the database to point at it. Run it
periodically, e.g. from cron every 10 minutes, with the virtualenv's Python:

```
.venv/bin/python process_gifs.py
```
