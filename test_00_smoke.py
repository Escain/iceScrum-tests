"""Smoke tests: auth, meta endpoints, and that every domain fixture builds.
Run these first -- if a fixture is broken the whole suite depends on it."""


def test_version(api):
    r = api.get("/ws/version")
    assert r.status_code == 200
    assert "7.5" in r.text  # 7.5x line


def test_version_verbose(api):
    r = api.get("/ws/version?verbose=true")
    assert r.status_code == 200


def test_user_current(api):
    r = api.get("/ws/user/current")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["username"] == "z"


def test_textile(api):
    r = api.post("/ws/textile", {"data": "*bold*"})
    assert r.status_code in (200, 201)


def test_no_token_is_rejected():
    import requests
    from conftest import BASE_URL
    r = requests.get(f"{BASE_URL}/ws/user/current", timeout=30)
    assert r.status_code in (401, 403)


def test_fixture_project(project):
    assert project["pkey"]
    assert isinstance(project["id"], int)


def test_fixture_feature(feature):
    assert feature["id"]


def test_fixture_actor(actor):
    assert actor["id"]


def test_fixture_story(story):
    assert story["id"]


def test_fixture_release(release):
    assert release["id"]


def test_fixture_sprint(sprint):
    assert sprint["id"]


def test_fixture_acceptance_test(acceptance_test):
    assert acceptance_test["id"]
