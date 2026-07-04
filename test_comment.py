"""/ws/$workspaceType/$workspace/comment/**  -- covers CommentController.index
-> commentService.withCommentable -> Story.withStory (the uniqueResult named
query `.list()`->`.get()` fix)."""
import pytest


@pytest.fixture(scope="module")
def comment(api, project, story):
    r = api.post(f"/ws/project/{project['pkey']}/comment",
                 {"comment": {"body": "a comment from api-tests",
                              "commentable": {"id": story["id"], "class": "Story"}}})
    assert r.status_code in (200, 201), f"comment create -> {r.status_code}: {r.text[:200]}"
    return r.json()


def test_save(comment):
    assert comment["id"]


def test_index_by_type(api, project, story, comment):
    r = api.get(f"/ws/project/{project['pkey']}/comment/story")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_index_by_commentable(api, project, story, comment):
    # This is the exact path that returned the Story->List cast error pre-fix.
    r = api.get(f"/ws/project/{project['pkey']}/comment/story/{story['id']}")
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    body = r.json()
    assert isinstance(body, list)
    assert any(c["id"] == comment["id"] for c in body)


def test_show(api, project, comment):
    r = api.get(f"/ws/project/{project['pkey']}/comment/{comment['id']}")
    assert r.status_code == 200


def test_update(api, project, comment):
    r = api.post(f"/ws/project/{project['pkey']}/comment/{comment['id']}",
                 {"comment": {"body": "edited comment"}})
    assert r.status_code in (200, 201)


def test_delete(api, project, story):
    # create a throwaway comment and delete it
    r = api.post(f"/ws/project/{project['pkey']}/comment",
                 {"comment": {"body": "to delete",
                              "commentable": {"id": story["id"], "class": "Story"}}})
    cid = r.json()["id"]
    d = api.delete(f"/ws/project/{project['pkey']}/comment/{cid}")
    assert d.status_code in (200, 204)
