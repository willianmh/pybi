"""Unit tests for semantic model format detection."""

import pytest

from pybi.serialization.detect import detect_semantic_model_format
from pybi.semanticmodel.types import SemanticModelFormat


class TestDetectFromDisk:
    def test_detects_tmdl_format(self, tmp_path):
        defn = tmp_path / "definition"
        defn.mkdir()
        (defn / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n")

        assert detect_semantic_model_format(str(tmp_path)) is SemanticModelFormat.TMDL

    def test_detects_legacy_format(self, tmp_path):
        (tmp_path / "model.bim").write_text("{}")

        assert detect_semantic_model_format(str(tmp_path)) is SemanticModelFormat.LEGACY

    def test_tmdl_takes_precedence(self, tmp_path):
        defn = tmp_path / "definition"
        defn.mkdir()
        (defn / "database.tmdl").write_text("database\n")
        (tmp_path / "model.bim").write_text("{}")

        assert detect_semantic_model_format(str(tmp_path)) is SemanticModelFormat.TMDL

    def test_raises_on_unknown(self, tmp_path):
        with pytest.raises(ValueError, match="Cannot detect"):
            detect_semantic_model_format(str(tmp_path))

    def test_definition_dir_without_tmdl_falls_to_legacy(self, tmp_path):
        defn = tmp_path / "definition"
        defn.mkdir()
        (defn / "readme.txt").write_text("not tmdl")
        (tmp_path / "model.bim").write_text("{}")

        assert detect_semantic_model_format(str(tmp_path)) is SemanticModelFormat.LEGACY
