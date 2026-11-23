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

    print("autocoll ok")
