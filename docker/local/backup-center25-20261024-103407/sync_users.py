"""Sync ERP (Global.Afrad) eligible users into Synapse. Runs inside element-messenger-synapse-1.
Usage: python sync_users.py [--deactivate] [--centers 15,16]
Without --deactivate it only lists users that would be deactivated."""
import hashlib, hmac, json, os, re, secrets, sys, urllib.request, urllib.error
import pymssql, yaml

BASE = "http://localhost:8008"
SERVER = "localhost"
LP = re.compile(r"^[a-z0-9._=/-]+$")
args = sys.argv[1:]
do_deactivate = "--deactivate" in args
cfg = yaml.safe_load(open("/data/homeserver.yaml"))
centers = None
if "--centers" in args:
    centers = [int(x) for x in args[args.index("--centers") + 1].split(",")]
else:
    for m in cfg.get("modules") or []:
        if m.get("module") == "erp_auth.ErpAuthProvider":
            centers = [int(c) for c in m.get("config", {}).get("allowed_centers", [15])]
centers = centers or [15]

def req(method, path, body=None, token=None):
    r = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(r) as f:
            return f.status, json.loads(f.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

# ERP eligible users
cn = pymssql.connect(server=os.environ["ERP_DB_SERVER"], user=os.environ["ERP_DB_USER"], password=os.environ["ERP_DB_PASSWORD"],
                     database=os.environ.get("ERP_DB_NAME", "Pakhsh_Data_New"), login_timeout=5, charset="UTF-8")
cur = cn.cursor()
cur.execute("SELECT UserName, FName, LName FROM [Global].[Afrad] WHERE EnableLogin=1 AND ISNULL(UserName,'')<>'' AND ccMarkazPakhshFaal IN (%s)"
            % ",".join(str(c) for c in centers))
erp, invalid = {}, []
for u, fn, ln in cur.fetchall():
    lp = u.strip().lower()
    if LP.match(lp):
        erp[lp] = " ".join(x.strip() for x in (fn, ln) if x and x.strip()) or lp
    else:
        invalid.append(u)
cn.close()

# temporary admin via shared-secret registration
secret = cfg["registration_shared_secret"].encode()
tmp = "erp-sync-" + secrets.token_hex(4)
pw = secrets.token_urlsafe(24)
_, n = req("GET", "/_synapse/admin/v1/register")
mac = hmac.new(secret, digestmod=hashlib.sha1)
mac.update(b"\x00".join([n["nonce"].encode(), tmp.encode(), pw.encode(), b"admin"]))
st, r = req("POST", "/_synapse/admin/v1/register", {"nonce": n["nonce"], "username": tmp, "password": pw, "admin": True, "mac": mac.hexdigest()})
if st != 200:
    sys.exit("temp admin registration failed: %s %s" % (st, r.get("errcode")))
tok, tmp_id = r["access_token"], r["user_id"]

created = skipped = failed = 0
fails = []
try:
    for lp, name in sorted(erp.items()):
        uid = "@%s:%s" % (lp, SERVER)
        st, u = req("GET", "/_synapse/admin/v2/users/" + uid, token=tok)
        if st == 200:
            skipped += 1
            continue
        st, r = req("PUT", "/_synapse/admin/v2/users/" + uid, {"displayname": name}, token=tok)
        if st in (200, 201):
            created += 1
        else:
            failed += 1; fails.append((lp, st, r.get("errcode")))
    # who would be deactivated: existing non-admin local users not eligible
    st, r = req("GET", "/_synapse/admin/v2/users?limit=10000&guests=false&deactivated=false", token=tok)
    stale = [x["name"] for x in r.get("users", []) if not x.get("admin") and x["name"].split(":")[0][1:] not in erp
             and not x["name"].startswith("@erp-sync-")]
    deact = 0
    if do_deactivate:
        for uid in stale:
            st, _ = req("POST", "/_synapse/admin/v1/deactivate/" + uid, {"erase": False}, token=tok)
            deact += st == 200
finally:
    req("POST", "/_synapse/admin/v1/deactivate/" + tmp_id, {"erase": True}, token=tok)

print(json.dumps({"centers": centers, "eligible": len(erp), "invalid_usernames": invalid, "created": created, "skipped_existing": skipped,
                  "failed": fails, "not_eligible_anymore": stale, "deactivated": deact if do_deactivate else "dry-run (use --deactivate)"},
                 ensure_ascii=False, indent=1))
