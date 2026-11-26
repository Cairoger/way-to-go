"""Run directly using the project venv. Only newly-created temporary SQLite files are used."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.mark.parametrize("creator_role", ["Owner", "Member"])
def test_delete_own_comment_preserves_reply(creator_role, trip, owner, guest):
    creator, other = (owner, guest) if creator_role == "Owner" else (guest, owner)
    base = f"/api/v1/trips/{trip['id']}/comments"
    identity = creator.get("/api/v1/auth/me").json()["id"]
    parent = creator.post(base, json={"content": "集合時間？"})
    assert parent.status_code == 201
    parent_id = parent.json()["id"]
    assert parent.json()["author_id"] == identity
    reply = other.post(base, json={"content": "十點集合", "parent_id": parent_id})
    assert reply.status_code == 201
    reply_id = reply.json()["id"]
    assert reply.json()["author_id"] != identity
    deleted = creator.request("DELETE", f"/api/v1/comments/{parent_id}",
                              json={"version": parent.json()["version"]})
    assert deleted.status_code == 200
    for viewer in (creator, other):
        listing = viewer.get(base)
        assert listing.status_code == 200
        rows = {c["id"]: c for c in listing.json()}
        assert rows[parent_id]["deleted"] and rows[parent_id]["content"] == ""
        assert rows[parent_id]["author_id"] == identity
        assert rows[parent_id]["version"] == parent.json()["version"] + 1
        assert rows[reply_id]["parent_id"] == parent_id
        assert not rows[reply_id]["deleted"] and rows[reply_id]["content"] == "十點集合"
    print(f"{creator_role} created own parent=201, peer reply=201, DELETE by author=200, "
          "both GET=200; tombstone=true, parent content empty, version 1->2, "
          "original author retained, peer reply preserved with same parent ID")


if __name__ == "__main__":
    path = Path(__file__).resolve()
    repo = path.parents[3]
    sys.path[:0] = [str(repo / "backend"), str(repo / "backend/tests")]
    os.environ.pop("TEST_DATABASE_URL", None)
    sys.dont_write_bytecode = True
    with TemporaryDirectory(prefix="wtg-own-comments-") as temporary:
        code = pytest.main(["-p", "no:cacheprovider", "-p", "conftest",
                            "--basetemp", str(Path(temporary) / "cases"),
                            "-vv", "-s", "--tb=short", str(path)])
    print("Removed temporary SQLite cases:", not Path(temporary).exists())
    sys.exit(code)
