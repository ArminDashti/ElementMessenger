"""Load ERP user export (JSON on stdin: localpart/hash/salt/displayname; no plaintext) into server Synapse.
- upserts table erp_user_cache in the Synapse Postgres DB (used by erp_auth fallback)
- removes cache rows for users no longer exported (disabled/removed in ERP)
- creates missing Synapse users @<localpart>:<server_name> with display name (no local password)
Runs on the Synapse host (needs docker access to elm-postgres and elm-synapse)."""
import json, subprocess, sys, urllib.request, urllib.parse, urllib.error
PG = ["docker", "exec", "-i", "elm-postgres", "psql", "-U", "synapse", "-d", "synapse", "-v", "ON_ERROR_STOP=1", "-At"]
SERVER = "im.dpdc.co"
def psql(sql, stdin=None):
    r = subprocess.run(PG + ["-c", sql] if stdin is None else PG, input=stdin, capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr)
    return r.stdout.strip()
def lit(s): return "'" + str(s).replace("'", "''") + "'"
users = json.load(sys.stdin)
assert users, "empty export - refusing to wipe cache"
stmts = ["BEGIN;", "CREATE TABLE IF NOT EXISTS erp_user_cache (localpart TEXT PRIMARY KEY, hash TEXT NOT NULL, salt TEXT NOT NULL, displayname TEXT, synced_at TIMESTAMPTZ DEFAULT now());",
         "CREATE TEMP TABLE _in (localpart TEXT, hash TEXT, salt TEXT, displayname TEXT);"]
for u in users:
    stmts.append(f"INSERT INTO _in VALUES ({lit(u['localpart'])},{lit(u['hash'])},{lit(u['salt'])},{lit(u['displayname'])});")
stmts += ["INSERT INTO erp_user_cache (localpart,hash,salt,displayname,synced_at) SELECT localpart,hash,salt,displayname,now() FROM _in "
          "ON CONFLICT (localpart) DO UPDATE SET hash=EXCLUDED.hash, salt=EXCLUDED.salt, displayname=EXCLUDED.displayname, synced_at=now();",
          "DELETE FROM erp_user_cache WHERE localpart NOT IN (SELECT localpart FROM _in);", "COMMIT;"]
psql(None, "\n".join(stmts))
print("cache rows:", psql("SELECT count(*) FROM erp_user_cache"))
existing = set(psql("SELECT name FROM users").splitlines())
missing = [u for u in users if f"@{u['localpart']}:{SERVER}" not in existing]
if missing:
    tok = psql("SELECT token FROM access_tokens a JOIN users u ON u.name=a.user_id WHERE u.admin=1 AND a.puppets_user_id IS NULL AND u.name='@admin:" + SERVER + "' ORDER BY a.id DESC LIMIT 1")
    ip = subprocess.run(["docker", "inspect", "elm-synapse", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}"], capture_output=True, text=True).stdout.split()[0]
    ok = 0
    for u in missing:
        uid = f"@{u['localpart']}:{SERVER}"
        req = urllib.request.Request(f"http://{ip}:8008/_synapse/admin/v2/users/" + urllib.parse.quote(uid, safe=""),
                                     json.dumps({"displayname": u["displayname"]}).encode(), {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}, method="PUT")
        try: urllib.request.urlopen(req, timeout=30); ok += 1
        except urllib.error.HTTPError as e: print("create failed", uid, e.code, "(all-numeric localparts are reserved by Synapse)" if u['localpart'].isdigit() else "")
    print("created users:", ok)