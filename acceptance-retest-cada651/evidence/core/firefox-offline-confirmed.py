"""Use stock Firefox's native Marionette driver, a clean profile and the private audit site."""
import base64
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = os.environ.get("WTG_CORE_ORIGIN", "http://127.0.0.1:18731")
SCRATCH = Path(os.environ.get("WTG_FIREFOX_STAGE", str(ROOT/".local/audit-firefox-release-core-20261125")))
FF = SCRATCH/"core/firefox.exe"
PROFILE = SCRATCH / ("profile-" + secrets.token_hex(4))


class Driver:
    def __init__(self, connection):
        self.socket = connection
        self.input = connection.makefile("rb")
        self.idx = 0
        greeting = self.receive()
        assert greeting["applicationType"] == "gecko", greeting

    def receive(self):
        length = b""
        while True:
            byte = self.input.read(1)
            if byte == b":":
                break
            if not byte:
                raise RuntimeError("Unexpected driver EOF")
            length += byte
        return json.loads(self.input.read(int(length)))

    def call(self, name, params):
        self.idx += 1
        payload = json.dumps([0,self.idx,name,params],ensure_ascii=False).encode()
        self.socket.sendall(str(len(payload)).encode()+b":"+payload)
        msg = self.receive()
        if msg[2]:
            raise RuntimeError(name+" "+str(msg[2].get("message",""))[:500])
        return msg[3] or {}

    def element(self, using, value, scope=None, seconds=12):
        start = time.monotonic()
        while True:
            try:
                result = self.call("WebDriver:FindElement",{"using":using,"value":value,**({"element":scope} if scope else {})})
                return next(iter(result.get("value",result).values()))
            except RuntimeError:
                if time.monotonic() - start > seconds:
                    raise RuntimeError(f"Element timeout: {value}")
                time.sleep(.15)

    def click(self, label, dialog=False):
        prefix = "//*[self::dialog or @role='dialog']" if dialog else ""
        return self.call("WebDriver:ElementClick",{"id":self.element("xpath",prefix+"//button[normalize-space()='"+label+"']")})

    def type(self, css, value):
        elm = self.element("css selector",css)
        self.call("WebDriver:ElementSendKeys",{"id":elm,"text":value,"value":list(value)})

    def read(self, script):
        return self.call("WebDriver:ExecuteScript",{"script":script,"args":[],"newSandbox":True,"sandbox":None})["value"]

    def wait_text(self, text):
        return self.element("xpath","//*[self::h1 or self::h2 or self::h3 or self::h4 or self::b][normalize-space()='"+text+"']")


def run():
    credentials=json.loads(Path(os.environ.get("WTG_UI_CONFIG",str(ROOT/".local/audit-ui-20261125/runtime.json"))).read_text(encoding="utf-8-sig"))
    PROFILE.mkdir()
    with socket.socket() as available:
        available.bind(("127.0.0.1",0))
        port=available.getsockname()[1]
    prefs={"marionette.port":port,"marionette.enabled":True,"browser.shell.checkDefaultBrowser":False,
           "app.update.auto":False,"app.update.enabled":False,"browser.startup.homepage":"about:blank",
           "datareporting.policy.dataSubmissionEnabled":False,"toolkit.telemetry.enabled":False,
           "browser.startup.firstrunSkipsHomepage":True}
    (PROFILE/"user.js").write_text("\n".join("user_pref("+json.dumps(k)+", "+json.dumps(v)+");" for k,v in prefs.items()))
    process=subprocess.Popen([str(FF),"-no-remote","-headless","-profile",str(PROFILE),"--marionette","about:blank"],
              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    driver=None
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Firefox exited before Marionette: "+str(process.returncode))
            try:
                sock=socket.create_connection(("127.0.0.1",port),timeout=.3)
                sock.settimeout(20)
                driver=Driver(sock)
                break
            except OSError: time.sleep(.15)
        if driver is None: raise RuntimeError("Firefox Marionette did not open")
        caps=driver.call("WebDriver:NewSession",{"capabilities":{"alwaysMatch":{"acceptInsecureCerts":False}}})
        details=caps.get("capabilities",caps.get("value",{}).get("capabilities",{}))
        print("MARIONETTE",json.dumps({k:details.get(k) for k in ("browserName","browserVersion","platformName","moz:headless")}),flush=True)
        for attempt in range(12):
            try:
                handles=driver.call("WebDriver:GetWindowHandles",{})
                if isinstance(handles,dict): handles=handles.get("value",[])
                if handles:
                    driver.call("WebDriver:SwitchToWindow",{"handle":handles[-1]})
                driver.call("WebDriver:Navigate",{"url":BASE+"/"})
                break
            except RuntimeError:
                if attempt == 11: raise
                time.sleep(.5)
        driver.wait_text("旅程總覽")
        driver.click("建立旅程")
        driver.type("form[aria-label='本機測試帳號登入'] input:not([type=password])",credentials["username"])
        driver.type("form[aria-label='本機測試帳號登入'] input[type=password]",credentials["password"])
        driver.click("使用測試帳號登入")
        title="Firefox 正式版 "+str(int(time.time()))
        driver.type("[role=dialog] input[name=title]",title)
        driver.click("建立旅程",dialog=True)
        driver.wait_text(title)
        print("CREATE_WITH_TITLE PASS",flush=True)
        driver.call("WebDriver:Refresh",{})
        driver.wait_text(title)
        print("SESSION_RELOAD PASS",flush=True)
        driver.click("新增活動")
        driver.type("dialog input[name=title]","正式版實際活動")
        driver.click("儲存活動",dialog=True)
        driver.wait_text("正式版實際活動")
        driver.call("WebDriver:Refresh",{})
        driver.wait_text("正式版實際活動")
        print("CREATE_ITINERARY_RELOAD PASS",flush=True)
        import httpx
        from urllib.parse import urlsplit,parse_qs
        tripid=parse_qs(urlsplit(driver.read("return location.href")).query)["trip"][0]
        with httpx.Client(base_url=BASE,headers={"Origin":BASE},trust_env=False) as h:
            h.post("/api/v1/auth/local-test",json={"username":credentials["username"],"password":credentials["password"]}).raise_for_status()
            base="/api/v1/trips/"+tripid
            place=h.post(base+"/places",json={"name":"府城展館","address":"遊學路十號"}).json()
            day=h.get(base+"/days").json()[0]
            h.post("/api/v1/days/"+day["id"]+"/items",json={"title":"展館集合","place_id":place["id"],"start_time":"10:30","timezone":"Asia/Taipei"}).raise_for_status()
        driver.call("WebDriver:Refresh",{})
        driver.wait_text("展館集合")
        driver.call("WebDriver:ElementClick",{"id":driver.element("css selector","details.offline-trip summary")})
        driver.click("儲存離線旅程")
        driver.element("xpath","//button[normalize-space()='更新離線旅程']")
        limit=time.monotonic()+12
        while time.monotonic()<limit and not driver.read("return !!navigator.serviceWorker.controller"):time.sleep(.2)
        controlled=driver.read("return !!navigator.serviceWorker.controller")
        url=driver.read("return location.href")
        original=driver.call("WebDriver:GetWindowHandle",{})["value"]
        newtab=driver.call("WebDriver:NewWindow",{"type":"tab"})
        newhandle=newtab.get("handle") or newtab.get("value",{}).get("handle")
        driver.call("WebDriver:SwitchToWindow",{"handle":original})
        driver.call("WebDriver:CloseWindow",{})
        driver.call("WebDriver:SwitchToWindow",{"handle":newhandle})
        import urllib.request
        from urllib.parse import urlsplit
        stage=ROOT/".local/acceptance-retest-cada651"
        settings=json.loads((stage/"runtime.json").read_text(encoding="utf-8"))
        assert BASE==settings["sqliteorigin"] and url.startswith(BASE+"/")
        (stage/os.environ.get("WTG_STOP_MARKER","stop-v2")).write_text("controlled loss of this isolated origin",encoding="utf-8")
        address=urlsplit(BASE)
        for _ in range(100):
            try:
                with socket.create_connection((address.hostname,address.port),timeout=.3):pass
            except OSError:break
            time.sleep(.15)
        else:raise RuntimeError("isolated origin remained reachable")
        print("Fresh Firefox tab, previous tab closed, saved via UI, controller=",controlled,"TCP unreachable",flush=True)
        try:
            driver.call("WebDriver:Navigate",{"url":url})
        except Exception as exc:print("navigation",str(exc)[:420],flush=True)
        for _ in range(35):
            body=driver.read("return document.body ? document.body.innerText : ''")
            if "離線唯讀" in body and "正式版實際活動" in body:break
            time.sleep(.25)
        print("offline_readonly=", "離線唯讀" in body, "activity=", "正式版實際活動" in body,"excerpt=",body[:220],flush=True)
        pic=driver.call("WebDriver:TakeScreenshot",{"full":False,"highlights":[]})["value"]
        (HERE/"firefox-offline-confirmed.png").write_bytes(base64.b64decode(pic))
        facts={"controller_before_close":controlled,"offline":"離線唯讀" in body,"saved_activity":"正式版實際活動" in body,"address_seen":"遊學路十號" in body,"local_time_seen":"10:30" in body,"edit_buttons":driver.read("return document.querySelectorAll('button').length"),"origin_tcp_reachable":False}
        (HERE/"firefox-offline-confirmed.json").write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding="utf-8")
        print(facts)
        assert facts["offline"] and facts["saved_activity"] and facts["address_seen"] and facts["local_time_seen"] and facts["edit_buttons"]==0

    finally:
        if driver:
            try: driver.call("Marionette:Quit",{"flags":["eForceQuit"]})
            except (OSError,RuntimeError): pass
            driver.input.close()
            driver.socket.close()
        try: process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True)
            process.wait(timeout=10)


if __name__=="__main__": run()
