"""Export ERP users (hash+salt only, no plaintext) for the Synapse erp_user_cache. Run inside a container that has pymssql and reaches ERP."""
import os, sys, json, pymssql
CENTERS = [int(c) for c in os.environ.get("ERP_CENTERS", "15,25").split(",")]
REQUIRE_ENABLED = os.environ.get("ERP_REQUIRE_ENABLE_LOGIN", "1") == "1"
sql = ("SELECT UserName, PasswordHash, PasswordSalt, FName, LName FROM [Global].[Afrad] WHERE ccMarkazPakhshFaal IN ("
       + ",".join(["%d"] * len(CENTERS)) + ")" + (" AND EnableLogin=1" if REQUIRE_ENABLED else ""))
with pymssql.connect(server=os.environ["ERP_DB_SERVER"], user=os.environ["ERP_DB_USER"], password=os.environ["ERP_DB_PASSWORD"],
                     database=os.environ.get("ERP_DB_NAME", "Pakhsh_Data_New"), login_timeout=10, timeout=60, charset="UTF-8") as cn:
    cur = cn.cursor(); cur.execute(sql, tuple(CENTERS)); rows = cur.fetchall()
out = []
for u, h, s, fn, ln in rows:
    lp = (u or "").strip().lower()
    if lp and h:
        out.append({"localpart": lp, "hash": h, "salt": s or "", "displayname": " ".join(x.strip() for x in (fn, ln) if x and x.strip()) or lp})
json.dump(out, sys.stdout, ensure_ascii=False)