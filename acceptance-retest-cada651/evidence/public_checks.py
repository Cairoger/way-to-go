from retest import *
import urllib.request, urllib.error
def qq(url):
    u=urllib.request.Request(url,headers={"User-Agent":"WayToGo-local-acceptance/1.0","Accept":"application/vnd.github+json"})
    try:
        with urllib.request.urlopen(u,timeout=12) as res:return json.load(res)
    except Exception as exc:return {"error":str(exc)}
if __name__=="__main__":
    e=env|{"PYTHONPATH":os.pathsep.join(map(str,[API,API/"tests"])),"INVITATION_SIGNING_KEY":secrets.token_hex(32)}
    run("modules/providers-live",[PY,OUT/"modules/provider_probe.py"],SRC,e,100)
    run("core/wiki-live",[PY,"-m","pytest","-p","no:cacheprovider","-p","conftest","-v","-s","--basetemp",str(LAB/"wiki-retry-pytest"),"--tb=short",str(OUT/"core/test_acceptance_core.py")+"::test_core_live_wikipedia"],API,e,100)
    api="https://api.github.com/repos/Cairoger/way-to-go"
    repo=qq(api);pr=qq(api+"/pulls/1")
    sha=capture(["git","rev-parse","HEAD"])
    runs=qq(api+"/actions/runs?head_sha="+sha+"&per_page=20")
    jobs=[]
    for a in runs.get("workflow_runs",[])[:5]:
        ob=qq(api+"/actions/runs/"+str(a["id"])+"/jobs")
        jobs.extend([{"name":j["name"],"conclusion":j["conclusion"],"html_url":j["html_url"],"steps":[[s["name"],s["conclusion"]] for s in j["steps"]]} for j in ob.get("jobs",[])])
    write("system/public-release.json",dict(utc=datetime.now(timezone.utc).isoformat(),repo={k:repo.get(k) for k in ["full_name","default_branch","private","error"]},pr={k:pr.get(k) for k in ["number","state","draft","merged","html_url","error"]}|{"base":pr.get("base",{}).get("sha"),"head":pr.get("head",{}).get("sha")},runs=[{k:t[k] for k in ["name","event","head_sha","conclusion","html_url","created_at"]} for t in runs.get("workflow_runs",[])],workflow_error=runs.get("error"),jobs=jobs,git_ls_remote=capture(["git","ls-remote","--symref","origin","HEAD","refs/heads/main","refs/heads/codex/acceptance-fixes-20261125"])))

