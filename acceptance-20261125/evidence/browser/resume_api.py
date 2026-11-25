"""Restart only the API of run_ui.py, preserving its disposable DB and account."""
from pathlib import Path
import hashlib,json,os,secrets,sys,faulthandler
root=Path(__file__).resolve().parents[3]
lab=root/".local/audit-ui-20261125"
data=json.loads((lab/"runtime.json").read_text())
salt=secrets.token_bytes(16)
digest=hashlib.pbkdf2_hmac("sha256",data["password"].encode(),salt,600000).hex()
db=max(lab.glob("ui-*.sqlite"),key=lambda x:x.stat().st_mtime)
os.environ.update(DATABASE_URL="sqlite:///"+db.as_posix(),PUBLIC_ORIGIN=data["origin"],LOCAL_TEST_USERNAME=data["username"],LOCAL_TEST_PASSWORD_HASH=f"pbkdf2_sha256$600000${salt.hex()}${digest}",WIKI_API_URL="",OPEN_METEO_URL="",FRANKFURTER_URL="",GOOGLE_CLIENT_ID="",GOOGLE_CLIENT_SECRET="",PYTHONDONTWRITEBYTECODE="1")
sys.dont_write_bytecode=True
sys.path.insert(0,str(root/"backend"))
import uvicorn
with (lab/"api-stacks.txt").open("w",encoding="utf-8") as stack:
    faulthandler.dump_traceback_later(75,repeat=True,file=stack)
    uvicorn.run("app.main:app",host="127.0.0.1",port=18732,access_log=False)
