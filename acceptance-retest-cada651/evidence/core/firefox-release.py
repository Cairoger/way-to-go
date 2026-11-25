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
        driver.click("旅伴")
        driver.click("產生邀請")
        driver.element("css selector","img[alt='旅程邀請 QR Code']")
        assert driver.read("return !!document.querySelector('input[aria-label=\"邀請連結\"]').value.match(/invite=[A-Z2-9]+/)")
        print("INVITE_HREF_AND_QR PASS",flush=True)
        driver.click("每日行程")
        driver.wait_text("正式版實際活動")
        encoded=driver.call("WebDriver:TakeScreenshot",{"full":False,"highlights":[]})["value"]
        (HERE/"firefox-release.png").write_bytes(base64.b64decode(encoded))
        print("SCREENSHOT firefox-release.png",flush=True)
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
