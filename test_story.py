"""/ws/project/$p/story/**  -- list, filters, update and safe nested actions."""
import pytest


def test_index(api, project, story):
    r = api.get(f"/ws/project/{project['pkey']}/story")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_filter_by_backlog(api, project, story):
    # use a real backlog id from the project (ids are DB-dependent, not always 1)
    backlogs = api.get(f"/ws/project/{project['pkey']}/backlog").json()
    assert backlogs, "project should have default backlogs"
    r = api.get(f"/ws/project/{project['pkey']}/story/backlog/{backlogs[0]['id']}")
    assert r.status_code == 200, f"{r.status_code}: {r.text[:150]}"
    assert isinstance(r.json(), list)


def test_filter_by_feature(api, project, story, feature):
    r = api.get(f"/ws/project/{project['pkey']}/story/feature/{feature['id']}")
    assert r.status_code in (200, 404)


def test_update_texts_persist(api, project, story):
    # Regression (Grails 7): name/description/notes live on BacklogElement (outside
    # grails-app/domain); without @DirtyCheck their setters never mark the entity
    # dirty, the flush issues no UPDATE and the response happily echoes the bound
    # in-memory values. So asserting on the update response is NOT enough — re-fetch.
    r = api.post(f"/ws/project/{project['pkey']}/story/{story['id']}",
                 {"story": {"name": "updated story name",
                            "description": "updated description",
                            "notes": "updated notes"}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
    fetched = api.get(f"/ws/project/{project['pkey']}/story/{story['id']}").json()
    assert fetched["name"] == "updated story name"
    assert fetched["description"] == "updated description"
    assert fetched["notes"] == "updated notes"


def test_tags_persist_on_first_save(api, project, story):
    # Regression (Grails 7): a brand-new tag only stuck after saving twice. Use a
    # never-seen tag name so the first save has to create both the Tag and the link.
    from conftest import RUN_SUFFIX
    new_tag = f"storytag{RUN_SUFFIX}"
    url = f"/ws/project/{project['pkey']}/story/{story['id']}"
    r = api.post(url, {"story": {"tags": [new_tag]}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
    assert new_tag in r.json()["tags"], "update response lost the new tag"
    assert new_tag in api.get(url).json()["tags"], "new tag not persisted after one save"

    r = api.post(url, {"story": {"tags": ""}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
    assert new_tag not in api.get(url).json()["tags"], "tag removal not persisted"


def test_print_backlog_pdf(api, project, story):
    # Regression (Grails 7): PDF export threw NoSuchMethodError with itext 2.1.7
    # (JasperReports 6.21.4 needs the OpenPDF fork of com.lowagie.text).
    backlogs = api.get(f"/ws/project/{project['pkey']}/backlog").json()
    sandbox = next(b for b in backlogs if b.get("code") == "sandbox")  # fixture story is suggested
    r = api.get(f"/ws/project/{project['pkey']}/story/backlog/{sandbox['id']}/print/PDF")
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    assert r.headers.get("Content-Type", "").startswith("application/pdf")
    assert r.content.startswith(b"%PDF"), "response is not a PDF document"


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
