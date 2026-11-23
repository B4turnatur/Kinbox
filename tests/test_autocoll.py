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

    # ---- Task 3: alte Einträge nachladen (yt-dlp nachgebaut)
    import json, subprocess
    calls = []

    def fake_run(cmd, timeout, **kw):
        calls.append(cmd[-1])
        if cmd[-1] == "https://a.example/v":
            out = json.dumps({"tags": ["GTA"], "categories": None, "description": "Los Santos #stunt"}).encode()
            return subprocess.CompletedProcess(cmd, 0, out, b"")
        return subprocess.CompletedProcess(cmd, 1, b"", b"ERROR: Video unavailable")
    server.run_tool = fake_run
    server.REFRESH_WAIT = 0
    server.LIB.clear(); server._PATH_INDEX.clear()
    entry("am4", k["id"], url="https://a.example/v")
    entry("amp3", k["id"], url="https://a.example/v")
    entry("bad", k["id"], url="https://b.example/v")
    entry("alb", k["id"], url="https://a.example/p", album="j1")
    entry("nourl", k["id"])
    kc = c.post("/api/collections", json={"name": "Auto", "words": "gta"}, headers=kid).get_json()
    assert kc["items"] == []
    assert c.get("/api/library/refresh-meta", headers=adm).get_json()["todo"] == 3
    server.refresh_meta_all()
    assert sorted(calls) == ["https://a.example/v", "https://b.example/v"], calls      # ein Aufruf pro Link
    for eid in ("am4", "amp3"):
        assert server.LIB[eid]["tags"] == ["gta", "stunt"] and server.LIB[eid]["meta_ok"] == 1, server.LIB[eid]
        assert server.LIB[eid]["desc"] == "Los Santos #stunt"
    assert server.LIB["bad"]["meta_ok"] == -1 and "meta_ok" not in server.LIB["alb"]
    kcoll = next(x for x in server.USERS[k["id"]]["collections"] if x["id"] == kc["id"])
    assert set(kcoll["items"]) == {"am4", "amp3"}, kcoll
    st = c.get("/api/library/refresh-meta", headers=adm).get_json()   # gezählt wird pro Link
    assert st["todo"] == 0 and st["total"] == 2 and st["done"] == 2 and st["failed"] == 1 and not st["running"], st
    calls.clear(); server.refresh_meta_all()
    assert calls == [] and server.REFRESH["running"] is False
    for m in ("get", "post", "delete"):
        assert getattr(c, m)("/api/library/refresh-meta", headers=kid).status_code == 403
    print("task3 ok")

    # ---- Abschlussprüfung
    # I1: neue Downloads mit yt-dlp-Infos zählen nicht als „ohne Hashtags“; Bearbeiten-Ergebnis ohne Infos schon
    p = d / "neu322.mp4"; p.write_bytes(b"x")
    ne = server.lib_add(str(p), {"title": "t", "tags": [], "categories": None, "description": ""}, server.Job({"url": "https://n.example/v"}, owner=k["id"]))
    assert ne["meta_ok"] == 1, ne
    p = d / "edit.mp4"; p.write_bytes(b"x")
    ed = server.lib_add(str(p), {"title": "t (Zuschnitt)", "webpage_url": "https://n.example/w"}, server.Job({"url": ""}, owner=k["id"]))
    assert "meta_ok" not in ed

    # I2: nur Einzelvideos abfragen – mit -I 1; Sound-/Profil-Links, Bilder und Links mit verschiedenen Videos nicht
    server.LIB.clear(); server._PATH_INDEX.clear(); calls.clear()
    cmds = []
    real_fake = fake_run
    server.run_tool = lambda cmd, timeout, **kw: (cmds.append(cmd), real_fake(cmd, timeout))[1]
    entry("snd", k["id"], url="https://www.tiktok.com/music/Original-Sound-7123456789012345678")
    entry("prof", k["id"], url="https://www.tiktok.com/@nasa")
    entry("ig", k["id"], url="https://www.instagram.com/nasa/")
    entry("pic", k["id"], url="https://a.example/v", kind="image")
    entry("pl1", k["id"], url="https://pl.example/list", vid="aaa")
    entry("pl2", k["id"], url="https://pl.example/list", vid="bbb")
    entry("ok1", k["id"], url="https://a.example/v", vid="x1")
    server.refresh_meta_all()
    assert calls == ["https://a.example/v"], calls
    i = cmds[0].index("-I"); assert cmds[0][i + 1] == "1", cmds[0]
    for eid in ("snd", "prof", "ig", "pic", "pl1", "pl2"):
        assert "meta_ok" not in server.LIB[eid], eid

    # I3: vorübergehende Fehler → nicht endgültig, Lauf stoppt bei Sperre bzw. nach 3 Fehlern am Stück
    server.LIB.clear(); server._PATH_INDEX.clear(); calls.clear()
    errs = {"https://r.example/1": "ERROR: HTTP Error 429: Too Many Requests"}

    def fake2(cmd, timeout, **kw):
        calls.append(cmd[-1])
        return subprocess.CompletedProcess(cmd, 1, b"", errs.get(cmd[-1], "ERROR: Connection reset by peer").encode())
    server.run_tool = fake2
    entry("r1", k["id"], url="https://r.example/1"); entry("r2", k["id"], url="https://r.example/2")
    server.refresh_meta_all()
    assert calls == ["https://r.example/1"] and "meta_ok" not in server.LIB["r1"] and "meta_ok" not in server.LIB["r2"], calls
    assert server.REFRESH["error"], server.REFRESH
    server.LIB.clear(); server._PATH_INDEX.clear(); calls.clear(); errs.clear()
    for n in range(5):
        entry(f"n{n}", k["id"], url=f"https://net.example/{n}")
    server.refresh_meta_all()
    assert len(calls) == 3 and all("meta_ok" not in e for e in server.LIB.values()), calls
    errs["https://g.example/1"] = "ERROR: [youtube] abc: Video unavailable. This video has been removed"
    server.LIB.clear(); server._PATH_INDEX.clear(); calls.clear()
    entry("g1", k["id"], url="https://g.example/1")
    server.refresh_meta_all()
    assert server.LIB["g1"]["meta_ok"] == -1 and not server.REFRESH["error"]

    # I4: „remove“ mit fremden/unbekannten ids lässt skip nicht wachsen; skip nur mit noch vorhandenen Einträgen
    server.LIB.clear(); server._PATH_INDEX.clear()
    entry("s1", k["id"], tags=["gta"])
    sc = c.post("/api/collections", json={"name": "S", "words": "gta"}, headers=kid).get_json()
    r = c.post(f"/api/collections/{sc['id']}", json={"remove": ["s1"] + [f"junk{i}" for i in range(1000)]}, headers=kid).get_json()
    assert r["skip"] == ["s1"], len(r["skip"])
    del server.LIB["s1"]
    r = c.post(f"/api/collections/{sc['id']}", json={"words": "gta"}, headers=kid).get_json()
    assert r["skip"] == [], r
    print("final ok")

    print("autocoll ok")
