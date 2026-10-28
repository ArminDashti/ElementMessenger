import base64, hashlib, logging, os, re
import pymssql
from synapse.module_api import ModuleApi

logger = logging.getLogger(__name__)
LOCALPART_RE = re.compile(r"^[a-z0-9._=/-]+$")


class ErpAuthProvider:
    """Verify m.login.password against ERP Global.Afrad (MD5(password+salt) base64).

    If ERP is unreachable, falls back to the local copy in the Synapse DB table
    erp_user_cache (localpart, hash, salt, displayname), filled by erp_user_sync.
    """

    def __init__(self, config, api: ModuleApi):
        self.api = api
        self.centers = [int(c) for c in config.get("allowed_centers", [15])]
        self.require_enabled = bool(config.get("require_enable_login", True))
        self.encoding = config.get("password_encoding", "cp1256")
        self.local_fallback = bool(config.get("local_fallback", True))
        api.register_password_auth_provider_callbacks(
            auth_checkers={("m.login.password", ("password",)): self.check_password}
        )

    @staticmethod
    def parse_config(config):
        return config or {}

    def _connect(self):
        return pymssql.connect(
            server=os.environ["ERP_DB_SERVER"], user=os.environ["ERP_DB_USER"],
            password=os.environ["ERP_DB_PASSWORD"], database=os.environ.get("ERP_DB_NAME", "Pakhsh_Data_New"),
            login_timeout=5, timeout=10, charset="UTF-8")

    def _lookup(self, localpart):
        placeholders = ",".join(["%d"] * len(self.centers))
        sql = ("SELECT UserName, PasswordHash, PasswordSalt, FName, LName FROM [Global].[Afrad] "
               "WHERE LOWER(UserName)=%s AND ccMarkazPakhshFaal IN (" + placeholders + ")"
               + (" AND EnableLogin=1" if self.require_enabled else ""))
        with self._connect() as cn:
            cur = cn.cursor()
            cur.execute(sql, tuple([localpart] + self.centers))
            return cur.fetchall()

    async def _cache_lookup(self, localpart):
        def f(txn):
            txn.execute("SELECT localpart, hash, salt, displayname, '' FROM erp_user_cache WHERE localpart = ?", (localpart,))
            return txn.fetchall()
        return await self.api.run_db_interaction("erp_cache_lookup", f)

    def _hash(self, password, salt):
        try:
            b = (password + (salt or "")).encode(self.encoding)
        except UnicodeEncodeError:
            b = (password + (salt or "")).encode("utf-8")
        return base64.b64encode(hashlib.md5(b).digest()).decode()

    async def check_password(self, username, login_type, login_dict):
        password = login_dict.get("password") or ""
        localpart = username[1:].split(":", 1)[0] if username.startswith("@") else username
        localpart = localpart.strip().lower()
        if not password or not LOCALPART_RE.match(localpart):
            return None
        try:
            rows = await self.api.defer_to_thread(self._lookup, localpart)
        except Exception as e:
            if not self.local_fallback:
                logger.exception("ERP auth: DB lookup failed")
                return None
            logger.warning("ERP auth: ERP unreachable (%s); using local erp_user_cache", type(e).__name__)
            try:
                rows = await self._cache_lookup(localpart)
            except Exception:
                logger.exception("ERP auth: local cache lookup failed")
                return None
        for _u, phash, salt, fn, ln in rows:
            if phash and self._hash(password, salt) == phash:
                user_id = self.api.get_qualified_user_id(localpart)
                if not await self.api.check_user_exists(user_id):
                    name = " ".join(x for x in (fn, ln) if x) or localpart
                    user_id = await self.api.register_user(localpart, displayname=name)
                    logger.info("ERP auth: created %s", user_id)
                return user_id, None
        return None
