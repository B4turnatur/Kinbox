"""Automatische Sammlungen: Hashtags speichern, Stichwort-Sammlungen, Nachladen. Start: python tests/test_autocoll.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS["download_dir"] = str(d)
    server.LIBRARY_FILE, server.USERS_FILE, server.THUMB_DIR = d / "library.json", d / "users.json", d / "thumbs"
    server.USERS.clear(); server.LIB.clear(); server._PATH_INDEX.clear()
    a = server.new_user("Mama", role="admin", folder="")
    k = server.new_user("Kind")
    server.thumb_file = lambda e: None

    # ---- Task 1: Hashtags, Kategorie, Beschreibung
    assert server.meta_tags({"tags": ["GTA 5", "gta 5"], "categories": ["Gaming"],
                             "description": "Stunt #GTA5 #LosSantos\n#gta5"}) == ["gta 5", "gaming", "gta5", "lossantos"]
    assert len(server.meta_tags({"tags": [f"t{i}" for i in range(80)]})) == 50
    assert server.meta_tags({"tags": ["x" * 100]}) == ["x" * 60]
    assert server.meta_tags({"tags": None, "categories": "kaputt", "description": None}) == []

    job = server.Job({"url": "https://example.com/v/1"}, owner=k["id"])
    p = d / "v1.mp4"; p.write_bytes(b"x")
    e = server.lib_add(str(p), {"title": "x", "tags": ["a"], "description": "y" * 5000}, job)
    assert e["tags"] == ["a"] and len(e["desc"]) == 2000, e
    pub = server.lib_public(e)
    assert pub["tags"] == ["a"] and len(pub["desc"]) == 300, pub
    e2 = server.lib_add(str(p), {"description": ""}, job)       # neu laden ohne Infos → alte bleiben
    assert e2 is e and e["tags"] == ["a"] and len(e["desc"]) == 2000
    e3 = server.lib_add(str(p), {"tags": ["b"], "description": "neu 😀\nZeile"}, job)
    assert e3["tags"] == ["b"] and e3["desc"] == "neu 😀\nZeile"

    args = server.build_args({"url": "https://example.com/v/1", "mode": "video"}, d)
    tmpl = next(x for x in args if x.startswith("before_dl:@@I"))
    assert "tags" in tmpl and "categories" in tmpl and "description" in tmpl, tmpl

    pm = server._photo_meta({"desc": "Foto #GTA", "tags": ["urlaub"]})
    assert pm["description"] == "Foto #GTA" and pm["tags"] == ["urlaub"], pm
    print("task1 ok")

    # ---- Task 2: Sammlungen mit Stichwörtern
    assert server.coll_words(" GTA, #gta5 ,x, gta\nLos Santos") == ["gta", "gta5", "los santos"]
    assert len(server.coll_words([f"w{i:02d}" for i in range(30)])) == 20
    assert server.coll_words(None) == [] and server.coll_words(["a" * 50]) == ["a" * 40]
    assert server.coll_match({"title": "Stunt", "tags": ["gta5"]}, ["gta"])
    assert not server.coll_match({"title": "agta"}, ["gta"])
    assert server.coll_match({"title": "x", "desc": "in Los Santos"}, ["los santos"])
    assert server.coll_match({"title": "GTA V"}, ["gta"])
    assert not server.coll_match({"title": "Minecraft"}, ["gta"])

    server.LIB.clear(); server._PATH_INDEX.clear()

    def entry(eid, owner, shared=False, **kw):
        p = d / f"{eid}.mp4"; p.write_bytes(b"x")
        server.LIB[eid] = {"id": eid, "path": str(p), "name": p.name, "title": eid, "owner": owner, "shared": shared,
                           "added": 1, "size": 1, "kind": "video", **kw}
        server._PATH_INDEX[server._pkey(str(p))] = eid
    entry("kgta", k["id"], tags=["gta5"])
    entry("kmc", k["id"], tags=["minecraft"])
    entry("afam", a["id"], shared=True, desc="#GTA online")
    entry("apriv", a["id"], title="GTA privat")
    c = server.app.test_client()
    kid, adm = {"X-Token": k["token"]}, {"X-Token": a["token"]}

    col = c.post("/api/collections", json={"name": "GTA", "words": "gta"}, headers=kid).get_json()
    assert set(col["items"]) == {"kgta", "afam"} and col["words"] == ["gta"], col
    acol = c.post("/api/collections", json={"name": "GTA", "words": ["gta"]}, headers=adm).get_json()
    assert set(acol["items"]) == {"afam", "apriv"}, acol       # privates Kind-Video nicht beim Admin
    entry("kneu", k["id"], tags=["gta"])                       # Kind teilt es später
    assert c.post("/api/library/kneu/share", json={"shared": True}, headers=kid).status_code == 200
    acoll = next(x for x in server.USERS[a["id"]]["collections"] if x["id"] == acol["id"])
    assert "kneu" in acoll["items"], acoll

    # manuell entfernt → bleibt draußen
    r = c.post(f"/api/collections/{col['id']}", json={"remove": ["kgta"]}, headers=kid).get_json()
    assert "kgta" not in r["items"] and r["skip"] == ["kgta"], r
    server.lib_add(server.LIB["kgta"]["path"], {"tags": ["gta5"]}, server.Job({"url": "u"}, owner=k["id"]))
    r = c.post(f"/api/collections/{col['id']}", json={"words": "gta, gta5"}, headers=kid).get_json()
    assert "kgta" not in r["items"] and r["words"] == ["gta", "gta5"], r
    r = c.post(f"/api/collections/{col['id']}", json={"add": ["kgta"]}, headers=kid).get_json()
    assert "kgta" in r["items"] and r["skip"] == [], r

    # neuer Download mit passendem Tag → sofort drin
    p = d / "frisch.mp4"; p.write_bytes(b"x")
    ne = server.lib_add(str(p), {"title": "Neu", "tags": ["GTA"]}, server.Job({"url": "u2"}, owner=k["id"]))
    kcoll = next(x for x in server.USERS[k["id"]]["collections"] if x["id"] == col["id"])
    assert ne["id"] in kcoll["items"]

    # Automatik aus: words + skip weg, items bleiben
    r = c.post(f"/api/collections/{col['id']}", json={"words": ""}, headers=kid).get_json()
    assert "words" not in r and "skip" not in r and "kgta" in r["items"], r
    # Sammlung ohne words: Antwort genau wie bisher
    plain = c.post("/api/collections", json={"name": "Normal"}, headers=kid).get_json()
    assert set(plain) == {"id", "name", "items"}, plain
    assert set(c.post(f"/api/collections/{plain['id']}", json={"add": ["kmc"]}, headers=kid).get_json()) == {"id", "name", "items"}
    print("task2 ok")

    print("autocoll ok")
