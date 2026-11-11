import os

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from velma_mcp import paths
from velma_mcp.paths import SPEECH_EXTENSIONS, WIDE_EXTENSIONS, resolve_input


def make(tmp_path, name="a.wav", data=b"x"):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_relative_and_absolute_inside(tmp_path):
    p = make(tmp_path)
    assert resolve_input("a.wav", tmp_path, WIDE_EXTENSIONS) == p.resolve()
    assert resolve_input(str(p), tmp_path, WIDE_EXTENSIONS) == p.resolve()


def test_dotdot_escape(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    make(tmp_path, "secret.wav")
    with pytest.raises(ToolError, match="outside"):
        resolve_input("../secret.wav", base, WIDE_EXTENSIONS)


def test_absolute_outside(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    other = make(tmp_path, "secret.wav")
    with pytest.raises(ToolError, match="outside"):
        resolve_input(str(other), base, WIDE_EXTENSIONS)


def test_sibling_prefix_is_not_inside(tmp_path):
    base = tmp_path / "base"
    evil = tmp_path / "base-evil"
    base.mkdir()
    evil.mkdir()
    other = make(evil, "a.wav")
    with pytest.raises(ToolError, match="outside"):
        resolve_input(str(other), base, WIDE_EXTENSIONS)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_symlink_escape_and_inside_link(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    target = make(tmp_path, "secret.wav")
    try:
        (base / "link.wav").symlink_to(target)
    except OSError:
        pytest.skip("creating symlinks needs extra privileges on this OS (for example Windows without developer mode)")
    with pytest.raises(ToolError, match="outside"):
        resolve_input("link.wav", base, WIDE_EXTENSIONS)
    inside = make(base, "real.wav")
    (base / "ok.wav").symlink_to(inside)
    assert resolve_input("ok.wav", base, WIDE_EXTENSIONS) == inside.resolve()


def test_missing_and_directory(tmp_path):
    (tmp_path / "d.wav").mkdir()
    with pytest.raises(ToolError, match="not found"):
        resolve_input("nope.wav", tmp_path, WIDE_EXTENSIONS)
    with pytest.raises(ToolError, match="regular file"):
        resolve_input("d.wav", tmp_path, WIDE_EXTENSIONS)


def test_extension_rules(tmp_path):
    make(tmp_path, "a.txt")
    make(tmp_path, "UPPER.WAV")
    make(tmp_path, "a.m4a")
    with pytest.raises(ToolError, match="extension"):
        resolve_input("a.txt", tmp_path, WIDE_EXTENSIONS)
    assert resolve_input("UPPER.WAV", tmp_path, SPEECH_EXTENSIONS)
    assert resolve_input("a.m4a", tmp_path, WIDE_EXTENSIONS)
    with pytest.raises(ToolError, match="extension"):  # m4a is not allowed for speech endpoints
        resolve_input("a.m4a", tmp_path, SPEECH_EXTENSIONS)


def test_extension_list_sizes():
    assert len(WIDE_EXTENSIONS) == 96
    assert len(SPEECH_EXTENSIONS) == 10


def test_empty_file(tmp_path):
    make(tmp_path, "e.wav", b"")
    with pytest.raises(ToolError, match="empty"):
        resolve_input("e.wav", tmp_path, WIDE_EXTENSIONS)


def test_oversize(tmp_path):
    make(tmp_path, "big.wav", b"x")
    big = tmp_path / "sparse.wav"
    with big.open("wb") as fh:
        fh.truncate(paths.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ToolError, match="100 MB"):
        resolve_input("sparse.wav", tmp_path, WIDE_EXTENSIONS)
    with big.open("wb") as fh:
        fh.truncate(paths.MAX_UPLOAD_BYTES)
    assert resolve_input("sparse.wav", tmp_path, WIDE_EXTENSIONS)


def test_limit_is_100_mib():
    assert paths.MAX_UPLOAD_BYTES == 100 * 1024 * 1024
