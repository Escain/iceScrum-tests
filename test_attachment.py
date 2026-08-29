"""Attachment upload regression test (iceScrum 7.57).

Guards the three defects that made every UI file upload fail after the
Grails 7 port:

* Attachmentable.getAttachmentableService() was private -> the trait's
  dynamic property lookup missed it (MissingPropertyException).
* AttachmentLink was saved without flush, so the synchronous CREATE event
  listener re-read it in the same transaction and got null on PostgreSQL.
* The servlet multipart limit defaulted to 128000 bytes, so anything above
  ~125KB died with MaxUploadSizeExceededException; hence the 2MB payload.

Upload goes through the session-authenticated UI mapping
(/project/<id>/attachment/<type>/<id>), not /ws/**, because that is the path
the browser actually uses and the one that was broken. The endpoint speaks
flow.js: the chunk metadata (flowFilename, flowChunkSize, ...) is mandatory,
and the upload only completes once every chunk has arrived. These tests send
a single chunk covering the whole file.
"""
import io
import requests

from conftest import BASE_URL, USER

TWO_MB = b"x" * (2 * 1024 * 1024)


def _ui_session():
    """Log in the way the browser does; multipart upload is not a /ws/** route."""
    s = requests.Session()
    s.get(f"{BASE_URL}/login/auth", timeout=30)
    r = s.post(
        f"{BASE_URL}/j_spring_security_check",
        data={"j_username": USER["username"], "j_password": USER["password"]},
        timeout=30,
        allow_redirects=False,
    )
    assert r.status_code in (302, 200), f"login failed: {r.status_code}"
    s.headers["x-icescrum-client"] = "webclient"
    return s


def _upload(s, pid, type_, entity_id, filename, payload):
    """POST the whole payload as a single flow.js chunk."""
    return s.post(
        f"{BASE_URL}/project/{pid}/attachment/{type_}/{entity_id}",
        data={
            "flowChunkNumber": "1",
            "flowTotalChunks": "1",
            "flowChunkSize": str(len(payload)),
            "flowTotalSize": str(len(payload)),
            "flowIdentifier": f"{len(payload)}-{filename}",
            "flowFilename": filename,
            "flowRelativePath": filename,
        },
        files={"file": (filename, io.BytesIO(payload), "application/octet-stream")},
        timeout=120,
    )


def test_story_attachment_upload_2mb(project, story):
    s = _ui_session()
    pid = project["id"]

    r = _upload(s, pid, "story", story["id"], "regression-2mb.txt", TWO_MB)
    assert r.status_code in (200, 201), f"upload failed: {r.status_code} {r.text[:300]}"

    r = s.get(f"{BASE_URL}/project/{pid}/attachment/story/{story['id']}",
              headers={"Accept": "application/json"}, timeout=30)
    assert r.status_code == 200, f"list failed: {r.status_code} {r.text[:300]}"
    names = [a.get("filename", "") or a.get("name", "") for a in r.json()]
    assert any("regression-2mb" in n for n in names), names


def test_task_attachment_upload(project, sprint, api):
    r = api.post(f"/ws/project/{project['pkey']}/task",
                 {"task": {"name": "attachment host", "type": 11, "backlog": sprint["id"]}})
    assert r.status_code in (200, 201), f"task creation failed: {r.status_code} {r.text[:300]}"
    tid = r.json()["id"]

    s = _ui_session()
    r = _upload(s, project["id"], "task", tid, "task-attach.txt", b"hello task")
    assert r.status_code in (200, 201), f"upload failed: {r.status_code} {r.text[:300]}"
