import logging
from unittest.mock import patch

import pytest

from pybi.serialization.transport.local import LocalTransport
from pybi.serialization.types import Part


@pytest.fixture
def transport():
    return LocalTransport()


# ---------------------------------------------------------------------------
# read_parts
# ---------------------------------------------------------------------------


class TestReadParts:
    def test_reads_flat_directory(self, transport, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"hello")
        (tmp_path / "b.bin").write_bytes(b"\x00\x01\x02")

        parts = transport.read_parts(str(tmp_path))
        by_path = {p.path: p.payload for p in parts}

        assert by_path == {"a.txt": b"hello", "b.bin": b"\x00\x01\x02"}

    def test_reads_nested_subdirectories(self, transport, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_bytes(b"nested")

        parts = transport.read_parts(str(tmp_path))

        assert len(parts) == 1
        assert parts[0].path == "sub/nested.txt"
        assert parts[0].payload == b"nested"

    def test_returns_empty_list_for_empty_directory(self, transport, tmp_path):
        assert transport.read_parts(str(tmp_path)) == []

    def test_raises_for_nonexistent_root(self, transport, tmp_path):
        with pytest.raises(FileNotFoundError):
            transport.read_parts(str(tmp_path / "does_not_exist"))

    def test_raises_when_root_is_a_file(self, transport, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"x")
        with pytest.raises(FileNotFoundError):
            transport.read_parts(str(f))

    def test_skips_skip_name_directories(self, transport, tmp_path):
        for skip_dir in ("__pycache__", ".git", ".pbi", ".DS_Store"):
            d = tmp_path / skip_dir
            d.mkdir()
            (d / "secret.txt").write_bytes(b"should be skipped")

        (tmp_path / "visible.txt").write_bytes(b"visible")

        parts = transport.read_parts(str(tmp_path))
        paths = {p.path for p in parts}

        assert paths == {"visible.txt"}

    def test_skips_skip_name_files(self, transport, tmp_path):
        (tmp_path / ".DS_Store").write_bytes(b"mac junk")
        (tmp_path / "real.txt").write_bytes(b"real")

        parts = transport.read_parts(str(tmp_path))
        paths = {p.path for p in parts}

        assert paths == {"real.txt"}

    def test_warns_and_skips_unreadable_file(self, transport, tmp_path, caplog):
        (tmp_path / "bad.txt").write_bytes(b"unreadable")
        (tmp_path / "good.txt").write_bytes(b"good")

        import pathlib

        original = pathlib.Path.read_bytes

        def patched(self):
            if self.name == "bad.txt":
                raise OSError("permission denied")
            return original(self)

        with patch.object(pathlib.Path, "read_bytes", patched):
            with caplog.at_level(logging.WARNING, logger="pybi.serialization.transport.local"):
                parts = transport.read_parts(str(tmp_path))

        assert len(parts) == 1
        assert parts[0].path == "good.txt"
        assert any("bad.txt" in r.message for r in caplog.records)

    def test_returns_parts_with_correct_types(self, transport, tmp_path):
        (tmp_path / "f.txt").write_bytes(b"data")
        parts = transport.read_parts(str(tmp_path))
        assert all(isinstance(p, Part) for p in parts)


# ---------------------------------------------------------------------------
# write_parts
# ---------------------------------------------------------------------------


class TestWriteParts:
    def test_writes_files_with_correct_content(self, transport, tmp_path):
        parts = [
            Part(path="a.txt", payload=b"hello"),
            Part(path="b.bin", payload=b"\xff\xfe"),
        ]
        transport.write_parts(parts, str(tmp_path))

        assert (tmp_path / "a.txt").read_bytes() == b"hello"
        assert (tmp_path / "b.bin").read_bytes() == b"\xff\xfe"

    def test_creates_nested_parent_directories(self, transport, tmp_path):
        parts = [Part(path="deep/nested/file.txt", payload=b"nested")]
        transport.write_parts(parts, str(tmp_path))

        assert (tmp_path / "deep" / "nested" / "file.txt").read_bytes() == b"nested"

    def test_clean_false_preserves_existing_files(self, transport, tmp_path):
        (tmp_path / "existing.txt").write_bytes(b"keep me")
        parts = [Part(path="new.txt", payload=b"new")]

        transport.write_parts(parts, str(tmp_path), clean=False)

        assert (tmp_path / "existing.txt").read_bytes() == b"keep me"
        assert (tmp_path / "new.txt").read_bytes() == b"new"

    def test_clean_true_removes_existing_files(self, transport, tmp_path):
        (tmp_path / "stale.txt").write_bytes(b"stale")
        parts = [Part(path="fresh.txt", payload=b"fresh")]

        transport.write_parts(parts, str(tmp_path), clean=True)

        assert not (tmp_path / "stale.txt").exists()
        assert (tmp_path / "fresh.txt").read_bytes() == b"fresh"

    def test_clean_true_with_nonexistent_root(self, transport, tmp_path):
        dest = tmp_path / "new_dir"
        parts = [Part(path="file.txt", payload=b"content")]

        transport.write_parts(parts, str(dest), clean=True)

        assert (dest / "file.txt").read_bytes() == b"content"

    def test_empty_parts_list_writes_nothing(self, transport, tmp_path):
        transport.write_parts([], str(tmp_path))
        assert list(tmp_path.iterdir()) == []

    def test_overwrites_existing_file(self, transport, tmp_path):
        (tmp_path / "f.txt").write_bytes(b"old")
        transport.write_parts([Part(path="f.txt", payload=b"new")], str(tmp_path))
        assert (tmp_path / "f.txt").read_bytes() == b"new"
