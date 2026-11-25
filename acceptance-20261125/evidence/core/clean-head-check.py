"""Read-only Git comparison, then disposable SQLite runs of the checked-in and working code."""
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "TEST_DATABASE_URL": ""}


def inspect(backend, sqlite_file):
    sys.path.insert(0, str(backend))
    os.chdir(backend)
    from alembic.config import Config
    from alembic import command
    from fastapi.testclient import TestClient
    from sqlalchemy import inspect as inspect_db, text
    from app.main import app
    from app.core import get_engine
    origin = "http://127.0.0.1:19861"
    name, password, salt = "snapshot-test", secrets.token_urlsafe(24), secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256",password.encode(),salt,600000)
    os.environ.update(DATABASE_URL="sqlite:///"+sqlite_file.as_posix(),PUBLIC_ORIGIN=origin,
        LOCAL_TEST_USERNAME=name,LOCAL_TEST_PASSWORD_HASH=f"pbkdf2_sha256$600000${salt.hex()}${key.hex()}",
        OPEN_METEO_URL="",WIKI_API_URL="",GOOGLE_CLIENT_ID="",GOOGLE_CLIENT_SECRET="")
    command.upgrade(Config("alembic.ini"), "head")
    with TestClient(app,base_url=origin,headers={"Origin":origin}) as c:
        spec=c.get("/openapi.json").json()
        methods=sorted(f"{method.upper()} {route}" for route,operations in spec["paths"].items()
                       for method in operations if method in ["get","post","put","patch","delete"])
        def content(method,route,status,body=None):
            response=c.request(method,route,json=body)
            assert response.status_code==status,(route,response.status_code,response.text[:120])
            return response.json()
        actor=content("POST","/api/v1/auth/local-test",200,{"username":name,"password":password})
        trip=content("POST","/api/v1/trips",201,{"title":"independent head check"})
        base="/api/v1/trips/"+trip["id"]
        day=content("GET",base+"/days",200)[0]
        urls={"places":base+"/places","days":base+"/days","polls":base+"/polls",
              "comments":base+"/comments","availability":base+"/availability",
              "finance":base+"/finance","tasks":base+"/tasks","bookings":base+"/bookings",
              "notifications":"/api/v1/notifications","weather":"/api/v1/days/"+day["id"]+"/weather",
              "planner-history":base+"/planner-history","files":base+"/files"}
        status={k:c.get(v).status_code for k,v in urls.items()}
        status["copy (POST)"]=c.post(base+"/copy",json={}).status_code
        poll={"kind":"place","mode":"rating","title":"Pick one","options":[{"text":"A"},{"text":"B"}]}
        score=c.post(base+"/polls",json=poll)
        status["rating poll (POST)"]=score.status_code
        with get_engine().connect() as conn:
            ver=conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            tables=sorted(inspect_db(conn).get_table_names())
    pins={}
    for req in (backend/"requirements.txt").read_text().splitlines():
        if "==" in req:
            distribution,version=req.split("==")
            installed=importlib.metadata.version(distribution.split("[")[0])
            pins[distribution]={"required":version,"installed":installed}
    return {"alembic":ver,"tables":tables,"operations":methods,"http":status,
            "validated_credential_type":actor["account_type"],"versions":pins}


def command(args,cwd=ROOT):
    return subprocess.run(args,cwd=cwd,env=ENV,capture_output=True,text=True,encoding="utf-8",errors="replace")


def lines(*args):
    result=command(["git",*args])
    result.check_returncode()
    return result.stdout.splitlines()


def main():
    sha=lines("rev-parse","HEAD")[0]
    source_files=lines("ls-tree","-r","--name-only",sha)
    modified=lines("diff","--name-only","HEAD","--",".",":(exclude)acceptance-20261125")
    untracked=lines("ls-files","--others","--exclude-standard","--","backend","frontend","deploy",".github")
    with tempfile.TemporaryDirectory(dir=ROOT/".local",prefix="audit-core-head-") as temp:
        stage=Path(temp).resolve()
        assert stage.parent==(ROOT/".local").resolve() and stage.name.startswith("audit-core-head-")
        clean=stage/"clean"
        archive=subprocess.check_output(["git","archive","--format=zip",sha],cwd=ROOT)
        with zipfile.ZipFile(io.BytesIO(archive)) as snapshot:
            snapshot.extractall(clean)
        result=command([sys.executable,"-m","pytest","-p","no:cacheprovider","--basetemp",str(stage/"pytest"),"-v","--tb=line","tests"],cwd=clean/"backend")
        (HERE/"clean-head-pytest.log").write_text(result.stdout+result.stderr,encoding="utf-8")
        data={"sha":sha,"git_files_in_commit":source_files,"modified_worktree_files":modified,
              "untracked_product_files":untracked,"head_pytest_exit":result.returncode,
              "head_test_summary":result.stdout.splitlines()[-1],"head_backend":None,"worktree_backend":None}
        for key,src in [("head",clean),("worktree",ROOT)]:
            child=command([sys.executable,str(Path(__file__).resolve()),"--inspect",str(src/"backend"),str(stage/(key+".sqlite"))])
            if child.returncode: raise RuntimeError(child.stderr)
            data[key+"_backend"]=json.loads(child.stdout)
        before=data["head_backend"]["operations"]
        after=data["worktree_backend"]["operations"]
        data["new_operations"]=sorted(set(after)-set(before))
        data["removed_operations"]=sorted(set(before)-set(after))
        (HERE/"clean-head.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({k:len(v["operations"]) for k,v in data.items() if k.endswith("_backend")}))
        print(data["head_test_summary"])
        print(data["head_backend"]["http"])
        print(data["worktree_backend"]["http"])


if __name__=="__main__":
    if len(sys.argv)>1:
        print(json.dumps(inspect(Path(sys.argv[2]),Path(sys.argv[3]))))
    else:
        main()
