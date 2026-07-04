"""Generic list/show/uid coverage for the project-scoped resources exposed via
the uniform  /ws/project/$project/$controller[/$id]  REST mappings.

These read paths exercise the domain query methods (`getInProject`, `withXxx`,
`getAllInStory` ...) that broke during the Grails 7 migration, so a green run
here is the core regression net.
"""
import pytest


# resource name -> fixture name providing an instance with an "id" (and "uid")
RESOURCES = [
    ("story", "story", True),
    ("feature", "feature", True),
    ("actor", "actor", True),
    ("release", "release", False),
    ("sprint", "sprint", False),
    ("acceptanceTest", "acceptance_test", True),
]


@pytest.mark.parametrize("resource,fixture,_", RESOURCES)
def test_index(api, project, request, resource, fixture, _):
    request.getfixturevalue(fixture)  # ensure at least one exists
    r = api.get(f"/ws/project/{project['pkey']}/{resource}")
    assert r.status_code == 200, f"{resource} index -> {r.status_code}: {r.text[:200]}"
    assert isinstance(r.json(), list)


@pytest.mark.parametrize("resource,fixture,_", RESOURCES)
def test_show(api, project, request, resource, fixture, _):
    obj = request.getfixturevalue(fixture)
    r = api.get(f"/ws/project/{project['pkey']}/{resource}/{obj['id']}")
    assert r.status_code == 200, f"{resource} show -> {r.status_code}: {r.text[:200]}"
    assert r.json()["id"] == obj["id"]


@pytest.mark.parametrize("resource,fixture,has_uid", RESOURCES)
def test_uid(api, project, request, resource, fixture, has_uid):
    if not has_uid:
        pytest.skip(f"{resource} has no uid endpoint")
    obj = request.getfixturevalue(fixture)
    uid = obj.get("uid")
    if uid is None:
        pytest.skip(f"{resource} instance has no uid field")
    r = api.get(f"/ws/project/{project['pkey']}/{resource}/uid/{uid}")
    assert r.status_code == 200, f"{resource} uid -> {r.status_code}: {r.text[:200]}"
