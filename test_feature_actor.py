"""/ws/project/$p/feature/**  and  /ws/project/$p/actor/**"""


# ---- Feature ----
def test_feature_index(api, project, feature):
    r = api.get(f"/ws/project/{project['pkey']}/feature")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_feature_show(api, project, feature):
    r = api.get(f"/ws/project/{project['pkey']}/feature/{feature['id']}")
    assert r.status_code == 200


def test_feature_update(api, project, feature):
    r = api.post(f"/ws/project/{project['pkey']}/feature/{feature['id']}",
                 {"feature": {"description": "updated feature"}})
    assert r.status_code in (200, 201)


def test_feature_copy(api, project, feature):
    r = api.post(f"/ws/project/{project['pkey']}/feature/{feature['id']}/copy")
    assert r.status_code in (200, 201, 400)


# ---- Actor ----
def test_actor_index(api, project, actor):
    r = api.get(f"/ws/project/{project['pkey']}/actor")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_actor_show(api, project, actor):
    r = api.get(f"/ws/project/{project['pkey']}/actor/{actor['id']}")
    assert r.status_code == 200


def test_actor_update(api, project, actor):
    # update binds the full object as the UI sends it (name is required)
    r = api.post(f"/ws/project/{project['pkey']}/actor/{actor['id']}",
                 {"actor": {"name": actor["name"], "description": "updated actor"}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"


def test_actor_delete(api, project):
    r = api.post(f"/ws/project/{project['pkey']}/actor", {"actor": {"name": "throwaway actor"}})
    aid = r.json()["id"]
    d = api.delete(f"/ws/project/{project['pkey']}/actor/{aid}")
    assert d.status_code in (200, 204)
