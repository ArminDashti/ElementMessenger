"""Sync ERP personnel photos (Global.Photo) into Synapse user avatars. Runs inside element-messenger-synapse-1.
Same photo source as dev-portal GetDepartmentUsersAsync / GetDirectoryUserPhotoAsync.
Usage: python sync_avatars.py [--dry-run] [--limit N] [--centers 15,25]"""
import hashlib, hmac, json, os, re, secrets, sys, urllib.error, urllib.parse, urllib.request
import pymssql, yaml

BASE = "http://localhost:8008"
SERVER = "localhost"
LP = re.compile(r"^[a-z0-9._=/-]+$")
PHOTO_EXT_PROVIDER = "erp_personnel_photo"

args = sys.argv[1:]
dry_run = "--dry-run" in args
limit = None
if "--limit" in args:
    limit = int(args[args.index("--limit") + 1])

cfg = yaml.safe_load(open("/data/homeserver.yaml"))
centers = None
if "--centers" in args:
    centers = [int(x) for x in args[args.index("--centers") + 1].split(",")]
else:
    for m in cfg.get("modules") or []:
        if m.get("module") == "erp_auth.ErpAuthProvider":
            centers = [int(c) for c in m.get("config", {}).get("allowed_centers", [15])]
centers = centers or [15]


def req(method, path, body=None, token=None, content_type="application/json", raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if raw is None and body is not None:
        headers["Content-Type"] = content_type
    elif raw is not None:
        headers["Content-Type"] = content_type
    r = urllib.request.Request(BASE + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(r) as f:
            return f.status, json.loads(f.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def guess_content_type(file_name):
    ext = os.path.splitext(file_name or "")[1].lower()
    return {
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(ext, "image/jpeg")


def current_photo_id(external_ids):
    for e in external_ids or []:
        if e.get("auth_provider") == PHOTO_EXT_PROVIDER:
            try:
                return int(e.get("external_id"))
            except (TypeError, ValueError):
                return None
    return None


def merge_photo_external_ids(external_ids, photo_id):
    kept = [e for e in (external_ids or []) if e.get("auth_provider") != PHOTO_EXT_PROVIDER]
    kept.append({"auth_provider": PHOTO_EXT_PROVIDER, "external_id": str(photo_id)})
    return kept


def fetch_photo(cur, photo_id):
    cur.execute(
        "SELECT PhotoSmall, Photo, PhotoFileNameSmall, PhotoFileName FROM [Global].[Photo] WITH (NOLOCK) WHERE ccPhoto=%s",
        (photo_id,),
    )
    row = cur.fetchone()
    if not row:
        return None, None
    data = row[0] if row[0] else row[1]
    if not data:
        return None, None
    name = row[2] if row[2] else (row[3] if row[3] else "avatar.jpg")
    return bytes(data), guess_content_type(name)


def upload_avatar(token, body, content_type, filename):
    q = urllib.parse.urlencode({"filename": filename})
    path = "/_matrix/media/v3/upload?" + q
    r = urllib.request.Request(
        BASE + path,
        method="POST",
        data=body,
        headers={"Authorization": "Bearer " + token, "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(r) as f:
            return f.status, json.loads(f.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


cn = pymssql.connect(
    server=os.environ["ERP_DB_SERVER"],
    user=os.environ["ERP_DB_USER"],
    password=os.environ["ERP_DB_PASSWORD"],
    database=os.environ.get("ERP_DB_NAME", "Pakhsh_Data_New"),
    login_timeout=15,
    charset="UTF-8",
)
cur = cn.cursor()
center_sql = ",".join(str(c) for c in centers)
cur.execute(
    """
    SELECT a.UserName, photo.ccPhoto
    FROM [Global].[Afrad] a WITH (NOLOCK)
    INNER JOIN [HumanResource].[Personel] personel WITH (NOLOCK) ON personel.ccAfrad = a.ccAfrad
    OUTER APPLY (
        SELECT TOP (1) pm.ccPhoto
        FROM [HumanResource].[PersonelMadrak] pm WITH (NOLOCK)
        WHERE pm.ccAfrad = a.ccAfrad AND pm.ccNoePhoto = 1
        ORDER BY pm.ccPhoto DESC
    ) photo
    WHERE a.EnableLogin = 1 AND ISNULL(a.UserName, '') <> ''
      AND a.ccMarkazPakhshFaal IN (%s)
      AND personel.TarikhEnfesal IS NULL
      AND photo.ccPhoto IS NOT NULL
    ORDER BY a.UserName
    """
    % center_sql
)
rows = []
for u, pid in cur.fetchall():
    lp = u.strip().lower()
    if LP.match(lp):
        rows.append((lp, int(pid)))

secret = cfg["registration_shared_secret"].encode()
tmp = "erp-avatar-sync-" + secrets.token_hex(4)
pw = secrets.token_urlsafe(24)
_, n = req("GET", "/_synapse/admin/v1/register")
mac = hmac.new(secret, digestmod=hashlib.sha1)
mac.update(b"\x00".join([n["nonce"].encode(), tmp.encode(), pw.encode(), b"admin"]))
st, r = req(
    "POST",
    "/_synapse/admin/v1/register",
    {"nonce": n["nonce"], "username": tmp, "password": pw, "admin": True, "mac": mac.hexdigest()},
)
if st != 200:
    sys.exit("temp admin registration failed: %s %s" % (st, r.get("errcode")))
tok, tmp_id = r["access_token"], r["user_id"]

updated = skipped = missing_user = no_photo = failed = 0
fails = []
processed = 0
try:
    for lp, photo_id in rows:
        if limit is not None and processed >= limit:
            break
        processed += 1
        uid = "@%s:%s" % (lp, SERVER)
        st, u = req("GET", "/_synapse/admin/v2/users/" + uid, token=tok)
        if st != 200:
            missing_user += 1
            continue
        if current_photo_id(u.get("external_ids")) == photo_id and u.get("avatar_url"):
            skipped += 1
            continue
        img, ctype = fetch_photo(cur, photo_id)
        if not img:
            no_photo += 1
            continue
        if dry_run:
            updated += 1
            continue
        ext = os.path.splitext(ctype.split("/")[-1])[0]
        fname = "avatar-%s.%s" % (lp, "png" if ext == "png" else "jpg")
        st, up = upload_avatar(tok, img, ctype, fname)
        if st != 200 or "content_uri" not in up:
            failed += 1
            fails.append((lp, photo_id, "upload", st, up.get("errcode")))
            continue
        body = {
            "avatar_url": up["content_uri"],
            "external_ids": merge_photo_external_ids(u.get("external_ids"), photo_id),
        }
        st, ur = req("PUT", "/_synapse/admin/v2/users/" + uid, body, token=tok)
        if st == 200:
            updated += 1
        else:
            failed += 1
            fails.append((lp, photo_id, "profile", st, ur.get("errcode")))
finally:
    req("POST", "/_synapse/admin/v1/deactivate/" + tmp_id, {"erase": True}, token=tok)
cn.close()

print(
    json.dumps(
        {
            "centers": centers,
            "eligible_with_photo": len(rows),
            "processed": processed,
            "updated": updated,
            "skipped_unchanged": skipped,
            "missing_synapse_user": missing_user,
            "photo_row_missing": no_photo,
            "failed": fails,
            "dry_run": dry_run,
        },
        ensure_ascii=False,
        indent=1,
    )
)
