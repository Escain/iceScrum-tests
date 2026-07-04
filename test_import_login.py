"""Importing a project from a legacy/foreign iceScrum brings in users whose
stored password hash has no Spring Security 6 {id} prefix. Before the fix,
logging in as such a user threw HTTP 500 (DelegatingPasswordEncoder: "no
password encoding prefix"). UserService.unMarshall now wraps bare/{salt} hashes
with {SHA-256} so the imported user can authenticate.
"""
import time
import re
import requests
from conftest import BASE_URL, USER
from test_import_export import _session, _flow_upload


def test_imported_legacy_user_can_login(api, project, story):
    # z is a member of the fixture project and its password is "z"; export it.
    xml = api.get(f"/ws/project/{project['pkey']}/export/xml").text

    # Simulate a legacy/foreign export:
    #  * strip the {SHA-256} delegating prefix from the stored password ({salt}hash), and
    #  * rename the user (new uid/username/email) so import creates it fresh
    #    instead of matching the existing local `z`.
    stamp = str(int(time.time()))[-6:]
    new_uid = "uid" + stamp + "abcdef0123456789"[:16]
    new_user = "zclone" + stamp
    old_uid = re.search(r"<user uid='([^']+)'", xml).group(1)

    xml = xml.replace("{SHA-256}", "")                 # -> legacy {salt}hash / bare
    xml = xml.replace(old_uid, new_uid)                # user def + team references
    xml = xml.replace("<username>z</username>", f"<username>{new_user}</username>")
    xml = xml.replace("<email>z@gmail.com</email>", f"<email>{new_user}@x.io</email>")
    npk = ("IL" + stamp).upper()[:10]
    xml = re.sub(r"<pkey>[^<]+</pkey>", f"<pkey>{npk}</pkey>", xml, count=1)
    # rename the (also-imported) team so it doesn't collide with the fixture's team
    teams_section = xml[xml.find("<teams"):]
    team_name = re.search(r"<name><!\[CDATA\[(.*?)\]\]></name>", teams_section).group(1)
    xml = xml.replace(f"<name><![CDATA[{team_name}]]></name>",
                      f"<name><![CDATA[Team {stamp}]]></name>", 1)

    s = _session()
    r = _flow_upload(s, "/project/import", xml.encode())
    assert r.status_code == 200, f"import failed: {r.status_code} {r.text[:250]}"

    # The imported user must authenticate with the original password ("z"),
    # and crucially must NOT get a 500 from the password encoder.
    login = requests.Session()
    login.get(f"{BASE_URL}/login/auth", timeout=30)
    resp = login.post(f"{BASE_URL}/j_spring_security_check",
                      data={"j_username": new_user, "j_password": "z"},
                      timeout=30, allow_redirects=False)
    assert resp.status_code != 500, f"login crashed (unprefixed password): {resp.status_code}"
    # A successful form login redirects (302) to the app; a failed one redirects
    # to the auth/fail page. Either way it must be a clean 302, never a 500.
    assert resp.status_code == 302, f"unexpected login status: {resp.status_code}"
    # Confirm it actually authenticated (not bounced to the login/fail page).
    assert "/login" not in (resp.headers.get("Location") or ""), \
        f"login was rejected: {resp.headers.get('Location')}"
