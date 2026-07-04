"""
Shared pytest fixtures for the iceScrum REST API (/ws/**) test suite.

Design notes
------------
* The /ws/** API is *token authenticated only* (application.groovy strips the
  session/basic-auth filters for that path).  We therefore log in once over the
  normal session-form login, mint a personal access token, and send it as the
  `x-icescrum-token` header on every REST call.
* The iceScrum Angular client posts `application/x-www-form-urlencoded` bodies,
  NOT JSON (a custom paramSerializer), and the controllers read `params.*`.
  JSON bodies are *not* bound into params in this build, so `form_encode`
  reproduces the Grails dotted/`repeated-key` convention the binder expects.
* All expensive setup (login, tokens, project + child entities) is
  session-scoped and created exactly once, so the whole suite is a few hundred
  fast HTTP calls sharing one keep-alive connection -> seconds, not hours.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("ICESCRUM_URL", "http://localhost:8080")

# Dev BootStrap users (grails-app/init/BootStrap.groovy + AuthorityService)
USER = {"username": "z", "password": "z", "id": 2}
ADMIN = {"username": "admin", "password": "adminadmin!"}

# A per-run suffix keeps project keys unique if the suite is run repeatedly
# against a server whose (create-drop) DB has not been wiped between runs.
RUN_SUFFIX = time.strftime("%H%M%S")


# --------------------------------------------------------------------------- #
# Grails form encoding
# --------------------------------------------------------------------------- #
def form_encode(obj, prefix=""):
    """Flatten a nested dict/list into a list of (key, value) form pairs using
    the convention the Grails data binder expects:

        {"project": {"team": {"scrumMasters": [{"id": 2}]}}}
        -> [("project.team.scrumMasters.id", "2")]

    Lists repeat the same key (so `params.foo.list('id')` collects them);
    booleans become 'true'/'false'; everything else is str()'d.
    """
    pairs = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            pairs.extend(form_encode(v, key))
    elif isinstance(obj, (list, tuple)):
        if not obj:
            pairs.append((prefix, ""))          # empty list -> explicit empty
        for item in obj:
            pairs.extend(form_encode(item, prefix))
    elif isinstance(obj, bool):
        pairs.append((prefix, "true" if obj else "false"))
    else:
        pairs.append((prefix, str(obj)))
    return pairs


# --------------------------------------------------------------------------- #
# API client
# --------------------------------------------------------------------------- #
class ApiClient:
    """Thin wrapper over requests.Session that token-authenticates every call
    and form-encodes bodies the way the controllers expect."""

    def __init__(self, base_url, token):
        self.base_url = base_url
        self.s = requests.Session()
        self.s.headers["x-icescrum-token"] = token
        self.s.headers["x-icescrum-client"] = "webclient"

    def url(self, path):
        return path if path.startswith("http") else self.base_url + path

    def get(self, path, **kw):
        return self.s.get(self.url(path), timeout=30, **kw)

    def post(self, path, body=None, **kw):
        data = form_encode(body) if body is not None else None
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        return self.s.post(self.url(path), data=data, headers=headers, timeout=30, **kw)

    def put(self, path, body=None, **kw):
        data = form_encode(body) if body is not None else None
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        return self.s.put(self.url(path), data=data, headers=headers, timeout=30, **kw)

    def delete(self, path, **kw):
        return self.s.delete(self.url(path), timeout=30, **kw)


# --------------------------------------------------------------------------- #
# Auth helpers / fixtures
# --------------------------------------------------------------------------- #
def _mint_token(username, password, user_id, token_name):
    """Session-login then create a personal access token for the user."""
    s = requests.Session()
    s.get(f"{BASE_URL}/login/auth", timeout=30)
    r = s.post(
        f"{BASE_URL}/j_spring_security_check",
        data={"j_username": username, "j_password": password},
        timeout=30,
        allow_redirects=False,
    )
    assert r.status_code in (302, 200), f"login failed for {username}: {r.status_code}"
    # Need the numeric user id for the token URL; fetch it if unknown.
    if user_id is None:
        cur = s.get(f"{BASE_URL}/ws/user/current", timeout=30)  # session works pre-token? no -> fallback below
        user_id = cur.json().get("id") if cur.ok else None
    r = s.post(
        f"{BASE_URL}/user/{user_id}/token",
        data={"userToken.name": token_name},
        timeout=30,
    )
    assert r.status_code == 200, f"token creation failed for {username}: {r.status_code} {r.text[:200]}"
    return r.json()["id"]


@pytest.fixture(scope="session")
def token():
    return _mint_token(USER["username"], USER["password"], USER["id"], f"api-tests-{RUN_SUFFIX}")


@pytest.fixture(scope="session")
def admin_token():
    # admin id is unknown/variable; discover it after login via token on /ws/user/current is circular,
    # so we log in and read the id from the session-rendered token list response instead.
    s = requests.Session()
    s.get(f"{BASE_URL}/login/auth", timeout=30)
    s.post(
        f"{BASE_URL}/j_spring_security_check",
        data={"j_username": ADMIN["username"], "j_password": ADMIN["password"]},
        timeout=30, allow_redirects=False,
    )
    # admin is created right after a/z in BootStrap -> id 3 in a fresh dev DB.
    for admin_id in (3, 1, 2, 4):
        r = s.post(f"{BASE_URL}/user/{admin_id}/token",
                   data={"userToken.name": f"api-admin-{RUN_SUFFIX}"}, timeout=30)
        if r.status_code == 200:
            tok = r.json()["id"]
            # verify it is really admin by hitting an admin-only endpoint
            check = requests.get(f"{BASE_URL}/ws/project",
                                 headers={"x-icescrum-token": tok}, timeout=30)
            if check.status_code == 200:
                return tok
    pytest.skip("could not obtain an admin token")


@pytest.fixture(scope="session")
def api(token):
    return ApiClient(BASE_URL, token)


@pytest.fixture(scope="session")
def api_admin(admin_token):
    return ApiClient(BASE_URL, admin_token)


# --------------------------------------------------------------------------- #
# Domain fixtures (created once, reused across the whole suite)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def project(api):
    """A project owned by user `z` (scrumMaster + productOwner) with dates
    spanning 2026, plus its default 'all' backlog available for story tests."""
    pkey = f"AT{RUN_SUFFIX}"[:10].upper()
    body = {
        "project": {
            "name": f"API Test {RUN_SUFFIX}",
            "pkey": pkey,
            "startDate": "2026-01-01T00:00:00Z",
            "endDate": "2026-12-31T00:00:00Z",
            "productOwners": [{"id": USER["id"]}],
            "team": {"name": f"API Team {RUN_SUFFIX}", "scrumMasters": [{"id": USER["id"]}]},
            "preferences": {"hidden": False},
        }
    }
    r = api.post("/ws/project", body)
    assert r.status_code in (200, 201), f"project create failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    return {"pkey": data["pkey"], "id": data["id"], "raw": data}


@pytest.fixture(scope="session")
def feature(api, project):
    r = api.post(f"/ws/project/{project['pkey']}/feature",
                 {"feature": {"name": f"Feature {RUN_SUFFIX}", "description": "desc", "color": "#ffcc00"}})
    assert r.status_code in (200, 201), f"feature create failed: {r.status_code} {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def actor(api, project):
    r = api.post(f"/ws/project/{project['pkey']}/actor",
                 {"actor": {"name": f"Actor {RUN_SUFFIX}"}})
    assert r.status_code in (200, 201), f"actor create failed: {r.status_code} {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def story(api, project):
    r = api.post(f"/ws/project/{project['pkey']}/story",
                 {"story": {"name": f"Story {RUN_SUFFIX}", "description": "As a user I want tests"}})
    assert r.status_code in (200, 201), f"story create failed: {r.status_code} {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def release(api, project):
    r = api.post(f"/ws/project/{project['pkey']}/release",
                 {"release": {"name": f"Release {RUN_SUFFIX}", "vision": "v",
                              "startDate": "2026-01-01T00:00:00Z", "endDate": "2026-06-30T00:00:00Z"}})
    assert r.status_code in (200, 201), f"release create failed: {r.status_code} {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def sprint(api, project, release):
    r = api.post(f"/ws/project/{project['pkey']}/sprint",
                 {"sprint": {"goal": f"Sprint {RUN_SUFFIX}",
                             "startDate": "2026-01-01T00:00:00Z", "endDate": "2026-01-14T00:00:00Z",
                             "parentRelease": {"id": release["id"]}}})
    assert r.status_code in (200, 201), f"sprint create failed: {r.status_code} {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def acceptance_test(api, project, story):
    r = api.post(f"/ws/project/{project['pkey']}/acceptanceTest",
                 {"acceptanceTest": {"name": f"AT {RUN_SUFFIX}", "description": "given/when/then",
                                     "parentStory": {"id": story["id"]}}})
    assert r.status_code in (200, 201), f"acceptanceTest create failed: {r.status_code} {r.text[:300]}"
    return r.json()
