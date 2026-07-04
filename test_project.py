"""/ws/project/** endpoints (excluding create, which is the `project` fixture)."""
import pytest


def test_show(api, project):
    r = api.get(f"/ws/project/{project['pkey']}")
    assert r.status_code == 200
    assert r.json()["pkey"] == project["pkey"]


def test_activities(api, project):
    r = api.get(f"/ws/project/{project['pkey']}/activities")
    assert r.status_code == 200


def test_list_by_user(api):
    r = api.get("/ws/project/user/2")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_by_user_and_role(api):
    r = api.get("/ws/project/user/2/inProject")
    assert r.status_code == 200


@pytest.mark.parametrize("chart", ["velocity", "burndown", "burnup", "parkingLot",
                                   "flowCumulative", "velocityCapacity"])
def test_charts(api, project, chart):
    r = api.get(f"/ws/project/{project['pkey']}/{chart}")
    # some charts need sprints/data but must never 500
    assert r.status_code in (200, 400, 404), f"{chart} -> {r.status_code}"


def test_update(api, project):
    # NB: the update action reads params.projectd (not project, which is the pkey
    # in the URL) and re-parses startDate, so both must be supplied.
    r = api.post(f"/ws/project/{project['pkey']}",
                 {"projectd": {"description": "updated by api-tests",
                               "startDate": "2026-01-01T00:00:00Z"}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"


def test_export_xml(api, project):
    r = api.get(f"/ws/project/{project['pkey']}/export/xml")
    assert r.status_code in (200, 400, 404)


def test_index_requires_admin(api):
    assert api.get("/ws/project").status_code in (401, 403)


def test_index_as_admin(api_admin):
    r = api_admin.get("/ws/project")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
