"""Offline policy unit tests and read-only local Git inspection. No requests sent to a target."""
import json, os, re, subprocess, sys
from pathlib import Path
from run_system import repo,out,git
sys.path.insert(0,str(repo/"backend"))
from app.main import rate_limited,attempts
from starlette.requests import Request
hits={}
for path,method,count in [("/api/v1/trips/trip/invitations","POST",46),("/api/v1/auth/google","POST",31),("/api/v1/auth/local-test","POST",16),("/api/v1/trips/trip/place-search","GET",31)]:
    attempts.clear()
    req=Request({"type":"http","method":method,"path":path,"scheme":"http","server":("testserver",80),"headers":[],"client":("testclient",100),"query_string":b""})
    answers=[rate_limited(req) for _ in range(count)]
    hits[path]={"first_limited_at":answers.index(True)+1,"earlier_accepted":not any(answers[:-1])}
# Delimit search to local Git blobs; do not emit matched strings or credentials.
rules={"private-key":r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----","google-oauth-secret":r"GOCSPX-[a-zA-Z0-9_-]{15,}","aws-access-id":r"AKIA[A-Z0-9]{16}","github-token":r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{30,}"}
patterns={k:[] for k in rules}
for sha in git("rev-list","--all"):
    for k,pattern in rules.items():
        proc=subprocess.run(["git","grep","-IlE",pattern.replace("(?:","("),sha,"--",":!*.png",":!*.webp"],cwd=repo,capture_output=True) if not pattern.startswith("-") else subprocess.run(["git","grep","-IlE","-e",pattern.replace("(?:","("),sha,"--"],cwd=repo,capture_output=True)
        if proc.returncode not in (0,1):raise RuntimeError(k)
        patterns[k]+=proc.stdout.decode("utf8").splitlines()
result={"limiter_unit":hits,"known_secret_pattern_files":patterns,"git_commits_checked":git("rev-list","--all"),"secret_audit_limit":"Read-only inventory and four recognizable key formats. Cannot attest to all possible arbitrary strings."}
(out/"policies.json").write_text(json.dumps(result,indent=2),encoding="utf8")
print("Saved",out/"policies.json")
