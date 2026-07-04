"""/ws/user/** endpoints."""


def test_current(api):
    r = api.get("/ws/user/current")
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "z"


def test_show_self(api, user_id):
    r = api.get(f"/ws/user/{user_id}")
    assert r.status_code == 200
    assert r.json()["id"] == user_id


def test_activities(api, user_id):
    r = api.get(f"/ws/user/{user_id}/activities")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_roles_for_project(api, project):
    r = api.get(f"/ws/user/roles/project/{project['pkey']}")
    assert r.status_code == 200


def test_index_requires_admin(api):
    # plain user must not list all users
    r = api.get("/ws/user")
    assert r.status_code in (403, 401)


def test_index_as_admin(api_admin):
    r = api_admin.get("/ws/user")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_admin_update_user_without_username_preserved(api_admin):
    """Regression: an admin update that omits username must not null it (which
    then blew up User.hashCode with an NPE / 500)."""
    import time
    st = str(int(time.time()))[-7:]
    uname = "upd" + st
    c = api_admin.post("/ws/user", {"user": {
        "username": uname, "email": f"{uname}@x.io",
        "password": "pw12345X", "confirmPassword": "pw12345X",
        "firstName": "F", "lastName": "L"}})
    assert c.status_code in (200, 201), f"create: {c.status_code} {c.text[:150]}"
    uid = c.json()["id"]
    # update WITHOUT resending username -> must keep it, and must not 500
    r = api_admin.post(f"/ws/user/{uid}",
                       {"user": {"firstName": "Changed", "email": f"{uname}@x.io"}})
    assert r.status_code in (200, 201), f"update: {r.status_code} {r.text[:150]}"
    assert r.json()["username"] == uname
