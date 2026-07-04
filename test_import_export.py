"""Project export (/ws/project/$p/export/xml) and import (/project/import).

Both broke in the Grails 7 migration:
 * export/import crashed with a divide-by-zero because the icescrum.export/import
   plugin registry init loop was dropped (config.size() == 0);
 * import then failed validation because the Project<->ProjectPreferences inverse
   was not set before the import's explicit validation.

Import is not under /ws (token auth) -- it is a session-form endpoint that takes
a flow.js chunked upload, so these tests log in with a session and post a single
chunk.
"""
import time
import re
import requests
import pytest
from conftest import BASE_URL, USER


def _session():
    s = requests.Session()
    s.get(f"{BASE_URL}/login/auth", timeout=30)
    r = s.post(f"{BASE_URL}/j_spring_security_check",
               data={"j_username": USER["username"], "j_password": USER["password"]},
               timeout=30, allow_redirects=False)
    assert r.status_code in (302, 200)
    return s


def _flow_upload(session, path, xml_bytes, filename="import.xml"):
    """Post `xml_bytes` as a single flow.js chunk to a session-form endpoint."""
    data = {
        "flowChunkNumber": "1",
        "flowChunkSize": str(max(len(xml_bytes), 1048576)),
        "flowCurrentChunkSize": str(len(xml_bytes)),
        "flowTotalSize": str(len(xml_bytes)),
        "flowTotalChunks": "1",
        "flowIdentifier": f"imp-{int(time.time()*1000)}",
        "flowFilename": filename,
        "flowRelativePath": filename,
    }
    files = {"file": (filename, xml_bytes, "text/xml")}
    return session.post(f"{BASE_URL}{path}", data=data, files=files, timeout=60)


@pytest.fixture(scope="module")
def exported_xml(api, project, story):
    """Export the shared fixture project (which has at least one story) as XML."""
    r = api.get(f"/ws/project/{project['pkey']}/export/xml")
    assert r.status_code == 200, f"export failed: {r.status_code} {r.text[:150]}"
    assert r.text.lstrip().startswith("<?xml"), "export is not XML"
    return {"pkey": project["pkey"], "name": project["raw"]["name"], "xml": r.text}


def test_export_xml_is_valid(exported_xml):
    assert "<export" in exported_xml["xml"]
    assert f"<pkey>{exported_xml['pkey']}</pkey>" in exported_xml["xml"]


def test_import_roundtrip_creates_project(exported_xml):
    """Export -> rewrite key/name -> import -> a new project is created."""
    npk = ("IMP" + str(int(time.time()))[-6:]).upper()[:10]
    xml = (exported_xml["xml"]
           .replace(f"<pkey>{exported_xml['pkey']}</pkey>", f"<pkey>{npk}</pkey>")
           .replace(exported_xml["name"], f"Imported {npk}"))
    s = _session()
    r = _flow_upload(s, "/project/import", xml.encode())
    assert r.status_code == 200, f"import failed: {r.status_code} {r.text[:250]}"
    body = r.json()
    assert body.get("class") == "Project", f"unexpected import response: {r.text[:250]}"
    assert body["pkey"] == npk
    assert body["preferences"]["class"] == "ProjectPreferences"


def test_import_reuses_existing_user_by_email(api, project, story):
    """Merge on import: a project whose member has an email that already exists
    locally (e.g. the importer themselves, but with a different uid from another
    instance) must import fine by reusing the existing account, not fail on the
    unique-email constraint."""
    xml = api.get(f"/ws/project/{project['pkey']}/export/xml").text
    stamp = str(int(time.time()))[-6:]
    # foreign instance: same username/email (z / z@gmail.com already exist) but a different uid
    old_uid = re.search(r"<user uid='([^']+)'", xml).group(1)
    xml = xml.replace(old_uid, "foreign" + stamp + "0000000000")
    # make only the USER collide: give the project + team fresh identifiers
    npk = ("MRG" + stamp).upper()[:10]
    xml = re.sub(r"<pkey>[^<]+</pkey>", f"<pkey>{npk}</pkey>", xml, count=1)
    tn = re.search(r"<name><!\[CDATA\[(.*?)\]\]></name>", xml[xml.find("<teams"):]).group(1)
    xml = xml.replace(f"<name><![CDATA[{tn}]]></name>", f"<name><![CDATA[MTeam {stamp}]]></name>", 1)
    s = _session()
    r = _flow_upload(s, "/project/import", xml.encode())
    assert r.status_code == 200, f"import with existing-email member failed: {r.status_code} {r.text[:250]}"
    assert r.json().get("class") == "Project"


def test_import_conflicting_key_is_clean_error_not_crash(exported_xml):
    """Importing an export whose key still collides must return a clean, specific
    validation error -- not the generic 'unexpected error' the divide-by-zero
    crash produced."""
    s = _session()
    r = _flow_upload(s, "/project/import", exported_xml["xml"].encode())
    assert r.status_code in (200, 400), f"{r.status_code}: {r.text[:200]}"
    assert "unexpected error" not in r.text.lower(), f"import crashed: {r.text[:200]}"
    assert "already exists" in r.text.lower(), f"expected a duplicate-key message: {r.text[:200]}"
