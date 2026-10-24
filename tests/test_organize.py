"""Mediathek organisieren: Favoriten, Sammlungen, Umbenennen, Rechte. Start: python tests/test_organize.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS["download_dir"] = str(d)
    server.LIBRARY_FILE, server.USERS_FILE, server.THUMB_DIR = d / "library.json", d / "users.json", d / "thumbs"
    server.USERS.clear(); server.LIB.clear()
    a = server.new_user("Mama", role="admin", folder="")
    k = server.new_user("Kind")
    server.thumb_file = lambda e: None

    def entry(eid, owner, shared=False):
        p = d / f"{eid}.mp4"; p.write_bytes(b"x")
        server.LIB[eid] = {"id": eid, "path": str(p), "name": p.name, "title": eid, "owner": owner, "shared": shared,
                           "added": 1, "size": 1, "kind": "video"}
    entry("own", k["id"]); entry("fam", a["id"], shared=True); entry("priv", a["id"])
    c = server.app.test_client()
    kid = {"X-Token": k["token"]}

    # Favoriten: eigene + geteilte ja, fremde private nein
    r = c.post("/api/library/favs", json={"add": ["own", "fam", "priv", "nix"]}, headers=kid).get_json()
    assert r["favs"] == ["own", "fam"], r
    assert {e["id"] for e in c.get("/api/library?scope=favs", headers=kid).get_json()["items"]} == {"own", "fam"}
    assert c.post("/api/library/favs", json={"remove": ["own"]}, headers=kid).get_json()["favs"] == ["fam"]

    # Sammlungen
    col = c.post("/api/collections", json={"name": " Lieder "}, headers=kid).get_json()
    assert col["name"] == "Lieder" and c.post("/api/collections", json={"name": ""}, headers=kid).status_code == 400
    r = c.post(f"/api/collections/{col['id']}", json={"add": ["own", "fam", "priv", "own"]}, headers=kid).get_json()
    assert r["items"] == ["own", "fam"], r
    lst = c.get(f"/api/library?scope=coll:{col['id']}", headers=kid).get_json()
    assert {e["id"] for e in lst["items"]} == {"own", "fam"} and lst["collections"][0]["name"] == "Lieder"
    assert c.post(f"/api/collections/{col['id']}", json={"name": "Musik", "remove": ["fam"]}, headers=kid).get_json() \
        == {"id": col["id"], "name": "Musik", "items": ["own"]}
    assert c.post(f"/api/collections/{col['id']}", json={}, headers={"X-Token": a["token"]}).status_code == 404  # fremde Sammlung
    assert c.delete(f"/api/collections/{col['id']}", headers=kid).status_code == 200
    assert c.get("/api/library", headers=kid).get_json()["collections"] == [] and Path(server.LIB["own"]["path"]).exists()

    # Umbenennen: Titel, optional Datei; fremde Einträge nicht
    r = c.post("/api/library/own/rename", json={"title": "Mein: Video"}, headers=kid).get_json()
    assert r["title"] == "Mein: Video" and r["name"] == "own.mp4"
    r = c.post("/api/library/own/rename", json={"title": "Mein: Video", "file": True}, headers=kid).get_json()
    assert r["name"] == "Mein_ Video.mp4" and (d / "Mein_ Video.mp4").exists() and not (d / "own.mp4").exists()
    assert c.post("/api/library/fam/rename", json={"title": "x"}, headers=kid).status_code == 403
    assert c.post("/api/library/own/rename", json={"title": "  "}, headers=kid).status_code == 400
    print("organize ok")
