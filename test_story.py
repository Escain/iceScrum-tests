"""/ws/project/$p/story/**  -- list, filters, update and safe nested actions."""
import pytest


def test_index(api, project, story):
    r = api.get(f"/ws/project/{project['pkey']}/story")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_filter_by_backlog(api, project, story):
    # backlog id 1 = the default "all" sandbox backlog convention; must not 500
    r = api.get(f"/ws/project/{project['pkey']}/story/backlog/1")
    assert r.status_code in (200, 404)


def test_filter_by_feature(api, project, story, feature):
    r = api.get(f"/ws/project/{project['pkey']}/story/feature/{feature['id']}")
    assert r.status_code in (200, 404)


def test_update(api, project, story):
    r = api.post(f"/ws/project/{project['pkey']}/story/{story['id']}",
                 {"story": {"description": "updated description"}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"


def test_show(api, project, story):
    r = api.get(f"/ws/project/{project['pkey']}/story/{story['id']}")
    assert r.status_code == 200


@pytest.fixture(scope="module")
def spare_story(api, project):
    r = api.post(f"/ws/project/{project['pkey']}/story",
                 {"story": {"name": "spare story for actions"}})
    assert r.status_code in (200, 201)
    return r.json()


def test_accept_then_return(api, project, spare_story):
    # accept (sandbox -> backlog), then return to sandbox: exercises state machine
    sid = spare_story["id"]
    acc = api.post(f"/ws/project/{project['pkey']}/story/{sid}/accept")
    assert acc.status_code in (200, 201, 400)
    if acc.status_code in (200, 201):
        back = api.post(f"/ws/project/{project['pkey']}/story/{sid}/returnToSandbox")
        assert back.status_code in (200, 201, 400)


def test_delete(api, project):
    r = api.post(f"/ws/project/{project['pkey']}/story", {"story": {"name": "to delete"}})
    sid = r.json()["id"]
    d = api.delete(f"/ws/project/{project['pkey']}/story/{sid}")
    assert d.status_code in (200, 204)
