"""Repeat the repo's restore contract on two fresh databases inside this audit's private Compose project."""
from retest import *
import textwrap
cli, ev = dc()
assert cfg()["project"].startswith("wtgrerun") and SRC.is_relative_to(R/".local")
prefix = "grants_" + secrets.token_hex(4)
prepared, restored = prefix + "_seed", prefix + "_restored"
def call(args, data=None):
    return sp.run([*map(str, cli), "exec", "-T", "db", *args], cwd=SRC, env=ev, input=data, stdout=sp.PIPE, stderr=sp.PIPE, check=True).stdout
def sql(db, data):
    return call(["psql", "-XqAt", "-v", "ON_ERROR_STOP=1", "-U", "waytogo", "-d", db], data)
for db in (prepared, restored):
    call(["createdb","-U","waytogo","-T","template0",db])
prior_dump=max((SRC/"backups").glob("*.dump"),key=lambda p:p.stat().st_mtime)
call(["pg_restore","--exit-on-error","-U","waytogo","-d",prepared],prior_dump.read_bytes())
sql(prepared,(SRC/"deploy/verify-restore-seed.sql").read_bytes())
manifest=(SRC/"deploy/verify-restore-manifest.sql").read_bytes()
before=sql(prepared,manifest)
dump=call(["pg_dump","-Fc","-U","waytogo",prepared])
call(["pg_restore","--exit-on-error","--single-transaction","-U","waytogo","-d",restored],dump)
after=sql(restored,manifest)
counts=sql(restored,b"select count(*) from files; select count(*) from file_permissions; select count(*) from files where removed_at is not null;").decode().splitlines()
workflow=(SRC/".github/workflows/ci.yml").read_text(encoding="utf-8")
snippet=workflow.split("Verify restored file content, links, permissions and recycle state through the API",1)[1].split("python - <<'PY'\n",1)[1].split("\n          PY",1)[0]
in_db="import os\nfrom sqlalchemy.engine import make_url\nos.environ['DATABASE_URL']=make_url(os.environ['DATABASE_URL']).set(database="+repr(restored)+").render_as_string(hide_password=False)\n"
run("system/grants-restored-api",cli+["exec","-T","api","python","-"],SRC,ev,stdin=(in_db+textwrap.dedent(snippet)).encode(),check=True)
receipt={"tables":len(before.splitlines()),"manifests_match":before==after,"file_rows":int(counts[0]),"explicit_permission_rows":int(counts[1]),"recycled_file_rows":int(counts[2]),"sha256_of_dump":hashlib.sha256(dump).hexdigest(),"workflow_step":"Verify restored file content, links, permissions and recycle state through the API","restored_reader_acl_and_recycle_checks":"passed"}
write("system/restore-grants.json",receipt)
assert receipt["tables"]==42 and before==after and int(counts[1])>=2 and int(counts[2])>=1

