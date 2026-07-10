# Maintainability roadmap

Why: the codebase has grown organically and deploying (especially the
songbook) is fragile and undocumented. Two tracks: make the code easier to
change safely, and make deploys boring. Keep changes small and reviewable.

## Track 1 — Code

Done or in progress (each item is its own commit on master):

1. **Run the tests automatically.** A GitHub Actions workflow runs the test
   suite on every push and pull request. (Previously ~1400 lines of tests
   existed but nothing ran them; `.travis.yml` was dead.)
2. **Linting.** `ruff` (a fast standard Python linter) with a minimal rule
   set, also run in CI. Test/lint tools moved out of the runtime dependencies.
3. **Small safety fixes:**
   - Timeouts on the Discord HTTP calls — a hung call froze the whole site
     because gunicorn runs a single worker.
   - Replace bare `except:` clauses with specific exceptions.
   - Remove the dead "is Discord launched yet" check (hardcoded to 2023).
   - Fix duplicated test names in `models_test.py` that silently disabled
     two tests, and the unstable route naming in `views/goofs.py`.
4. **Split the giant files** (behavior and URLs unchanged, tests added first):
   - `views/strequelistan.py` (1185 lines mixing drink tally, profiles,
     gallery, pokes, API keys, Discord login) → one view module per topic.
   - `models.py` (998 lines, 17 models) → a `models/` package; all existing
     imports keep working.
   - Move the vendored cache-busting helper and the hardcoded test-data
     fixtures out of `factory.py`.

Future (not started, roughly in order of value):

5. **Database schema change scripts.** Today the schema comes from
   `db.create_all()` and past changes were manual surgery on the SQLite file.
   Introduce Flask-Migrate (a wrapper around Alembic, the standard SQLAlchemy
   schema-versioning tool) so schema changes become small, reviewable,
   checked-in scripts. Requires a careful one-time "adopt the existing prod
   database" step — take a backup first.
6. **Dependency upgrades.** The stack is pinned to ~2022 versions (Flask 2.2,
   SQLAlchemy 1.4, WTForms 2, Python <3.11). Upgrading is a coordinated
   effort (some pinned pairs must move together) and should wait until CI has
   been green for a while. Biggest known blockers: `db.create_all(app=app)`
   and `@babel.localeselector` use APIs removed in newer versions.

## Track 2 — Deployment (Docker)

Goal: `git pull && docker compose up --build -d` is the entire deploy, and
the VPS's system packages (Node in particular) stop mattering.

1. **`Dockerfile`** (multi-stage): stage 1 = a pinned Node 22 image that runs
   `npm ci && npm run build` in `songbook-viewer/`; stage 2 = a pinned Python
   3.10 image with the app, dependencies installed with uv, the built
   songbook copied in from stage 1, translations compiled, gunicorn on
   port 8000.
2. **`docker-compose.yml`**: one service, port 8000 bound to localhost only,
   volumes so data survives container rebuilds:
   - `instance/` (SQLite database + local config)
   - `flasquelistan/static/uploads/` (profile pictures etc.)
3. **One-time server migration** (document each step in DEPLOYMENT.md as it
   happens): install Docker; change nginx `proxy_pass` from the unix socket
   to `http://127.0.0.1:8000` (both the `/` and `/socket.io` locations);
   replace the gunicorn systemd unit with one that runs
   `docker compose up`.
4. **Commit the server configs.** The live nginx conf and systemd unit are
   currently only on the server (a snapshot is parked in version-control
   history). Once updated for Docker, commit them under `deploy/` so
   production config has history. Note: the nginx conf contains the
   secure-link salt — decide whether to move it out before committing.
5. **Known wrinkle:** building the songbook needs the private submodule (SSH
   deploy key) and the two out-of-band files (`Flerstämt.pdf`, `songs.json`).
   Simplest: keep `git submodule update` as a pre-build step on the server,
   with the files in place in the checkout, and let Docker build from the
   local directory. Revisit if it annoys.
