"""/ws/project/$p/release/**  and  /ws/project/$p/sprint/**"""


# ---- Release ----
def test_release_index(api, project, release):
    r = api.get(f"/ws/project/{project['pkey']}/release")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_release_show(api, project, release):
    r = api.get(f"/ws/project/{project['pkey']}/release/{release['id']}")
    assert r.status_code == 200


def test_release_update(api, project, release):
    r = api.post(f"/ws/project/{project['pkey']}/release/{release['id']}",
                 {"release": {"vision": "updated vision"}})
    assert r.status_code in (200, 201)


def test_release_activate(api, project, release):
    r = api.post(f"/ws/project/{project['pkey']}/release/{release['id']}/activate")
    assert r.status_code in (200, 201, 400)


# ---- Sprint ----
def test_sprint_index(api, project, sprint):
    r = api.get(f"/ws/project/{project['pkey']}/sprint")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_sprint_show(api, project, sprint):
    r = api.get(f"/ws/project/{project['pkey']}/sprint/{sprint['id']}")
    assert r.status_code == 200


def test_sprint_by_release(api, project, release, sprint):
    r = api.get(f"/ws/project/{project['pkey']}/sprint/release/{release['id']}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_sprint_current_or_next_or_last(api, project, sprint):
    r = api.get(f"/ws/project/{project['pkey']}/sprint/currentOrNextOrLast")
    assert r.status_code in (200, 404)


def test_sprint_update(api, project, sprint):
    r = api.post(f"/ws/project/{project['pkey']}/sprint/{sprint['id']}",
                 {"sprint": {"goal": "updated goal"}})
    assert r.status_code in (200, 201)


def test_sprint_activate(api, project, release, sprint):
    # Sprint activation builds an activation cliche (ClicheService.getPointsByType),
    # which regressed on a Grails 7 config-key type mismatch (null + effort NPE).
    # Release must be in progress before its first sprint can be activated.
    api.post(f"/ws/project/{project['pkey']}/release/{release['id']}/activate")
    r = api.post(f"/ws/project/{project['pkey']}/sprint/{sprint['id']}/activate")
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
