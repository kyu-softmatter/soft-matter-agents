from __future__ import annotations


def test_without_build_shows_how_to_build(engine, make_client):
    r = make_client(engine).get("/")
    assert r.status_code == 200
    assert "npm --prefix web run build" in r.text


def test_serves_build_with_spa_fallback(tmp_path, engine, make_client):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>shell</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    c = make_client(engine, web_dist=dist)
    assert c.get("/").text == "<html>shell</html>"
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/map/flag/3").text == "<html>shell</html>"  # client-side route
    assert c.get("/api/health").json()["status"] == "ok"  # API wins over the mount
    assert c.get("/api/nothing-here").status_code == 404
