# iceScrum REST API test suite

Black-box tests for the iceScrum `/ws/**` REST API, driven with `pytest` +
`requests` against a running server. Built during the Grails 2 → 7 migration to
turn ad-hoc manual browser testing into a fast, repeatable regression net.

## What it covers

Every endpoint in `RestUrlMappings.groovy` reachable with a normal (non-admin)
project owner, plus admin-only listings: version / textile / user / team /
project (+ charts, export, activities) / story / feature / actor / release /
sprint / task / acceptanceTest / comment / meeting / activity / hook /
timeBoxNotesTemplate, across list · show · uid · create · update · delete ·
nested actions.

The read paths deliberately exercise the domain query methods
(`getInProject`, `withXxx`, `getAllInStory`, …) that repeatedly broke during the
migration, so a green run is the core regression signal.

## Setup

Create the virtualenv (git-ignored) and install the two dependencies:

```bash
python3 -m venv venv
./venv/bin/pip install pytest requests
```

## Running

The iceScrum dev server must be running on `http://localhost:8080`
(override with `ICESCRUM_URL`). The suite mints its own access tokens from the
dev BootStrap users `z`/`z` and `admin`/`adminadmin!`.

```bash
./venv/bin/python -m pytest            # full suite (~5 s)
./venv/bin/python -m pytest -v         # verbose
./venv/bin/python -m pytest test_comment.py
```

## Design (see `conftest.py`)

* **Auth** — `/ws/**` is token-only, so we session-login, POST a personal
  access token, and send it as `x-icescrum-token`.
* **Encoding** — the Angular client (and therefore the controllers) expect
  `application/x-www-form-urlencoded` with dotted / repeated-key nesting, *not*
  JSON. `form_encode()` reproduces that convention.
* **Efficiency** — login, tokens and the whole project→story→sprint→… fixture
  graph are **session-scoped** (built once) over one keep-alive connection, so
  ~100 endpoint checks run in seconds, not minutes.

## Known failures

Three tests are marked `xfail` — they document real migration bugs the suite
found that are not yet fixed. See `BUGS.md`. When a bug is fixed the xfail flips
to `xpass`, which is visible in the summary.
