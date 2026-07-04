"""/ws/project/$p/acceptanceTest/**  -- covers AcceptanceTest.getAllInStory,
the structural-GString HQL that broke in the Grails 7 migration."""


def test_index(api, project, acceptance_test):
    r = api.get(f"/ws/project/{project['pkey']}/acceptanceTest")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_filter_by_story(api, project, story, acceptance_test):
    # This is the exact path that raised QuerySyntaxException (:p0) pre-fix.
    r = api.get(f"/ws/project/{project['pkey']}/acceptanceTest/story/{story['id']}")
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    body = r.json()
    assert isinstance(body, list)
    assert any(at["id"] == acceptance_test["id"] for at in body)


def test_show(api, project, acceptance_test):
    r = api.get(f"/ws/project/{project['pkey']}/acceptanceTest/{acceptance_test['id']}")
    assert r.status_code == 200


def test_update(api, project, acceptance_test):
    r = api.post(f"/ws/project/{project['pkey']}/acceptanceTest/{acceptance_test['id']}",
                 {"acceptanceTest": {"description": "updated"}})
    assert r.status_code in (200, 201)
