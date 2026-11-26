from retest import *
from urllib.request import urlopen,Request
from urllib.parse import quote
import tarfile
folder=LAB/"official-firefox";folder.mkdir(exist_ok=True)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"WayToGo independent acceptance"}),timeout=65) as r:return r.read()
ver=json.loads(fetch("https://product-details.mozilla.org/1.0/firefox_versions.json"))["LATEST_FIREFOX_VERSION"]
assert re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}",ver)
prefix="https://archive.mozilla.org/pub/firefox/releases/"+ver+"/"
name="win64/en-US/Firefox Setup "+ver+".exe"
checks=fetch(prefix+"SHA512SUMS").decode("utf-8")
want=next(line.split()[0] for line in checks.splitlines() if line.strip().endswith(" "+name))
payload=fetch(prefix+quote(name,safe="/"))
got=hashlib.sha512(payload).hexdigest()
assert want==got
write("core/official-firefox-build.json",dict(version=ver,url=prefix+quote(name,safe="/"),sha512=got,bytes=len(payload),official_checksums=prefix+"SHA512SUMS"))
magic=b"7z\xbc\xaf\x27\x1c"
of=payload.index(magic)
z=folder/"firefox.7z";z.write_bytes(payload[of:])
run("core/firefox-unpack",["tar","-xf",z,"-C",folder],R,env,110,check=True)
assert (folder/"core/firefox.exe").exists()
d=cfg()
ev=env|{"WTG_FIREFOX_STAGE":str(folder),"WTG_UI_CONFIG":str(LAB/"pg-ui.json"),"WTG_CORE_ORIGIN":d["origin"]}
sys.exit(run("core/firefox-release",[PY,OUT/"core/firefox-release.py"],R,ev,180))
