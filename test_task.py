"""/ws/project/$p/task/**  -- tasks require a sprint backlog (urgent task) or a
planned story."""
import pytest

TYPE_URGENT = 11


@pytest.fixture(scope="module")
def urgent_task(api, project, sprint):
    r = api.post(f"/ws/project/{project['pkey']}/task",
                 {"task": {"name": "urgent api task", "type": TYPE_URGENT,
                           "backlog": {"id": sprint["id"]}}})
    assert r.status_code in (200, 201), f"task create -> {r.status_code}: {r.text[:200]}"
    return r.json()


def test_create(urgent_task):
    assert urgent_task["id"]


def test_index(api, project, urgent_task):
    r = api.get(f"/ws/project/{project['pkey']}/task")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_show(api, project, urgent_task):
    r = api.get(f"/ws/project/{project['pkey']}/task/{urgent_task['id']}")
    assert r.status_code == 200


def test_filter_by_sprint(api, project, sprint, urgent_task):
    r = api.get(f"/ws/project/{project['pkey']}/task/sprint/{sprint['id']}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_take_then_unassign(api, project, urgent_task):
    tid = urgent_task["id"]
    take = api.post(f"/ws/project/{project['pkey']}/task/{tid}/take")
    assert take.status_code in (200, 201, 400)
    if take.status_code in (200, 201):
        un = api.post(f"/ws/project/{project['pkey']}/task/{tid}/unassign")
        assert un.status_code in (200, 201, 400)


def test_update(api, project, urgent_task):
    r = api.post(f"/ws/project/{project['pkey']}/task/{urgent_task['id']}",
                 {"task": {"description": "updated task"}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"


def test_tags_persist_on_first_save(api, project, urgent_task):
    # Regression (Grails 7): a brand-new tag only stuck after saving twice.
    from conftest import RUN_SUFFIX
    new_tag = f"tasktag{RUN_SUFFIX}"
    url = f"/ws/project/{project['pkey']}/task/{urgent_task['id']}"
    r = api.post(url, {"task": {"tags": [new_tag]}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
    assert new_tag in r.json()["tags"], "update response lost the new tag"
    assert new_tag in api.get(url).json()["tags"], "new tag not persisted after one save"

    r = api.post(url, {"task": {"tags": ""}})
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
    assert new_tag not in api.get(url).json()["tags"], "tag removal not persisted"


def test_task_created_before_planning_then_moved(api, user_id):
    """Regression: a task added to a story while it is still in the sandbox must
    get its backlog set to the sprint when the story is planned, so it stays
    visible and can be moved on the task board. This broke because Project.equals
    was not Hibernate-proxy-safe, silently failing the task's parentProject
    validator during planning (task kept a null sprint -> invisible).

    Uses its own project (a second release would overlap the shared fixture's)."""
    from conftest import RUN_SUFFIX
    pkraw = f"TBM{RUN_SUFFIX}"[:10].upper()
    proj = api.post("/ws/project", {"project": {
        "name": f"TBM {RUN_SUFFIX}", "pkey": pkraw,
        "startDate": "2026-01-01T00:00:00Z", "endDate": "2026-12-31T00:00:00Z",
        "productOwners": [{"id": user_id}],
        "team": {"name": f"TBM team {RUN_SUFFIX}", "scrumMasters": [{"id": user_id}]},
        "preferences": {"hidden": False}}})
    assert proj.status_code in (200, 201), f"project create: {proj.status_code} {proj.text[:150]}"
    pk = proj.json()["pkey"]
    story = api.post(f"/ws/project/{pk}/story", {"story": {"name": "pre-plan story"}}).json()
    rel = api.post(f"/ws/project/{pk}/release", {"release": {"name": "PR", "vision": "v",
            "startDate": "2026-02-01T00:00:00Z", "endDate": "2026-05-30T00:00:00Z"}}).json()
    spr = api.post(f"/ws/project/{pk}/sprint", {"sprint": {"goal": "PS",
            "startDate": "2026-02-01T00:00:00Z", "endDate": "2026-02-14T00:00:00Z",
            "parentRelease": {"id": rel["id"]}}}).json()
    # task created BEFORE the story is planned (backlog legitimately null here)
    task = api.post(f"/ws/project/{pk}/task",
                    {"task": {"name": "pre-plan task", "parentStory": {"id": story["id"]}}}).json()
    api.post(f"/ws/project/{pk}/story/{story['id']}/accept")
    api.post(f"/ws/project/{pk}/story/{story['id']}", {"story": {"effort": 3}})
    api.put(f"/ws/project/{pk}/story/{story['id']}/plan", {"story": {"parentSprint": {"id": spr["id"]}}})
    # after planning, the task must belong to the sprint
    t = api.get(f"/ws/project/{pk}/task/{task['id']}").json()
    assert t.get("backlog"), f"task backlog still null after planning: {t.get('backlog')}"
    api.post(f"/ws/project/{pk}/release/{rel['id']}/activate")
    api.post(f"/ws/project/{pk}/sprint/{spr['id']}/activate")
    # task must be visible in the sprint board and movable to In Progress
    board = api.get(f"/ws/project/{pk}/task/sprint/{spr['id']}").json()
    assert any(x["id"] == task["id"] for x in board), "task invisible in sprint board"
    mv = api.post(f"/ws/project/{pk}/task/{task['id']}", {"task": {"state": 1}})
    assert mv.status_code in (200, 201), f"move failed: {mv.status_code}: {mv.text[:200]}"
