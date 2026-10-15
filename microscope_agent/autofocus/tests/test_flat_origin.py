"""dino_autofocus.flat_origin: a flat file's origin header names its body (workplan D-03)."""

import pytest

from dino_autofocus import flat_origin as fo

COMMIT = "0" * 40
BODY = '"""A flat file."""\n\nX = 1\n'
SRC = "microscope_agent/src/thing.py"
TEST = "microscope_agent/tests/test_thing.py"


def _repo(tmp_path, body=BODY, crlf=False):
    text = body.replace("\n", "\r\n") if crlf else body
    for rel in (SRC, TEST):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(text.encode("utf-8"))
    return tmp_path


def test_header_round_trip_and_a_hash_that_ignores_line_endings():
    h = fo.Header(COMMIT, SRC, fo.body_sha256(BODY))
    assert fo.split(h.render() + BODY) == (h, BODY)
    assert fo.body_sha256(BODY.replace("\n", "\r\n")) == h.body_sha256
    assert fo.split(BODY) == (None, BODY)  # no header: the whole text is the body


def test_rewrite_then_check_passes_and_keeps_the_file_s_line_endings(tmp_path):
    repo = _repo(tmp_path, crlf=True)
    assert fo.check(repo) == [f"{SRC}: no origin header", f"{TEST}: no origin header"]
    fo.rewrite(repo, COMMIT)
    assert fo.check(repo) == []
    raw = (repo / SRC).read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    header, _ = fo.split(raw.decode("utf-8"))
    assert (header.commit, header.path) == (COMMIT, SRC)
    before = raw
    fo.rewrite(repo, COMMIT)
    assert (repo / SRC).read_bytes() == before  # idempotent


def test_a_body_edit_without_a_new_header_fails(tmp_path):
    repo = _repo(tmp_path)
    fo.rewrite(repo, COMMIT)
    p = repo / SRC
    p.write_text(p.read_text(encoding="utf-8") + "Y = 2\n", encoding="utf-8")
    [problem] = fo.check(repo)
    assert problem.startswith(f"{SRC}: body changed")


def test_a_moved_file_is_named_wrong(tmp_path):
    repo = _repo(tmp_path)
    fo.rewrite(repo, COMMIT)
    (repo / SRC).rename(repo / "microscope_agent/src/other.py")
    assert fo.check(repo) == [f"microscope_agent/src/other.py: header names {SRC}"]


def test_a_mirror_header_names_soft_matter_agents_and_round_trips():
    h = fo.Header(fo.SMA_MIRROR_COMMIT, "microscope_agent/src/focus_search.py",
                  fo.body_sha256(BODY), origin=fo.SMA)
    text = h.render() + BODY
    assert text.startswith("# origin: soft-matter-agents, ")
    assert "github.com/kyu-softmatter/soft-matter-agents/blob/" in text
    assert fo.split(text) == (h, BODY)


def test_mirror_and_own_headers_are_rewritten_separately(tmp_path):
    mirrored = "microscope_agent/src/focus_search.py"
    repo = _repo(tmp_path)
    (repo / mirrored).write_text(BODY, encoding="utf-8")
    fo.rewrite(repo, COMMIT)  # dino's own files only
    assert fo.split((repo / mirrored).read_text(encoding="utf-8"))[0] is None
    fo.rewrite(repo, fo.SMA_MIRROR_COMMIT, mirror=True)
    assert fo.check(repo) == []
    header, _ = fo.split((repo / mirrored).read_text(encoding="utf-8"))
    assert (header.origin, header.commit) == (fo.SMA, fo.SMA_MIRROR_COMMIT)
    own, _ = fo.split((repo / SRC).read_text(encoding="utf-8"))
    assert (own.origin, own.commit) == (fo.ORIGIN, COMMIT)


def test_a_mirrored_file_with_a_dino_header_is_reported(tmp_path):
    mirrored = "microscope_agent/src/focus_verdict.py"
    repo = _repo(tmp_path)
    (repo / mirrored).write_text(BODY, encoding="utf-8")
    fo.rewrite(repo, COMMIT)
    p = repo / mirrored
    p.write_text(fo.Header(COMMIT, mirrored, fo.body_sha256(BODY)).render() + BODY,
                 encoding="utf-8")
    [problem] = fo.check(repo)
    assert "should name soft-matter-agents" in problem


def test_a_short_commit_is_refused(tmp_path):
    with pytest.raises(ValueError):
        fo.rewrite(_repo(tmp_path), "fa97903")


def test_the_command_line(tmp_path, capsys):
    repo = _repo(tmp_path)
    assert fo.main(["--repo", str(repo), "--check"]) == 1
    assert fo.main(["--repo", str(repo), "--commit", COMMIT]) == 0
    assert fo.main(["--repo", str(repo), "--check"]) == 0
    assert "origin headers: ok" in capsys.readouterr().out
