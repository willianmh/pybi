"""Integration tests for SemanticModel.read() against real sample files."""

from pathlib import Path

import pytest

from pybi.semanticmodel.semanticmodel import SemanticModel

# ---------------------------------------------------------------------------
# Sample paths (relative to project root)
# ---------------------------------------------------------------------------

_PBIR_ROOT = Path("../pbi-samples/pbi/pbir/11.25")
_LEGACY_ROOT = Path("../pbi-samples/pbi/legacy/11.25")

_AI_PBIR = _PBIR_ROOT / "ai" / "Artificial Intelligence Sample.SemanticModel"
_AI_LEGACY = _LEGACY_ROOT / "ai" / "Artificial Intelligence Sample.SemanticModel"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def all_pbir_roots():
    roots = sorted(_PBIR_ROOT.glob("*/*.SemanticModel"))
    assert len(roots) > 0, "No PBIR sample directories found"
    return roots


@pytest.fixture(scope="session")
def all_legacy_roots():
    roots = sorted(_LEGACY_ROOT.glob("*/*.SemanticModel"))
    assert len(roots) > 0, "No legacy sample directories found"
    return roots


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_table(sm: SemanticModel, name: str):
    for t in sm.definition.model.tables or []:
        if t.name == name:
            return t
    return None


# ---------------------------------------------------------------------------
# TMDL reading
# ---------------------------------------------------------------------------


class TestReadTmdl:
    def test_read_smoke(self, all_pbir_roots):
        for root in all_pbir_roots:
            sm = SemanticModel.read(str(root))
            assert sm.definition.model is not None
            assert sm.definition.model.tables is not None
            assert len(sm.definition.model.tables) > 0

    def test_compatibility_level(self):
        sm = SemanticModel.read(str(_AI_PBIR))
        assert sm.definition.compatibilityLevel == 1567

    def test_table_count(self):
        sm = SemanticModel.read(str(_AI_PBIR))
        assert len(sm.definition.model.tables) == 18

    def test_accounts_table(self):
        sm = SemanticModel.read(str(_AI_PBIR))
        accounts = _find_table(sm, "Accounts")
        assert accounts is not None
        assert accounts.columns is not None
        assert len(accounts.columns) > 0
        assert len(accounts.partitions) > 0


# ---------------------------------------------------------------------------
# Legacy (model.bim) reading
# ---------------------------------------------------------------------------


class TestReadLegacy:
    def test_read_smoke(self, all_legacy_roots):
        for root in all_legacy_roots:
            sm = SemanticModel.read(str(root))
            assert sm.definition.model is not None
            assert sm.definition.model.tables is not None
            assert len(sm.definition.model.tables) > 0

    def test_compatibility_level(self):
        sm = SemanticModel.read(str(_AI_LEGACY))
        assert sm.definition.compatibilityLevel == 1567

    def test_table_count(self):
        sm = SemanticModel.read(str(_AI_LEGACY))
        assert len(sm.definition.model.tables) == 18

    def test_accounts_table(self):
        sm = SemanticModel.read(str(_AI_LEGACY))
        accounts = _find_table(sm, "Accounts")
        assert accounts is not None
        assert accounts.columns is not None
        assert len(accounts.columns) > 0


# ---------------------------------------------------------------------------
# Cross-format consistency
# ---------------------------------------------------------------------------


class TestReadConsistency:
    def test_table_names_match(self):
        pbir = SemanticModel.read(str(_AI_PBIR))
        legacy = SemanticModel.read(str(_AI_LEGACY))
        pbir_names = {t.name for t in pbir.definition.model.tables}
        legacy_names = {t.name for t in legacy.definition.model.tables}
        assert pbir_names == legacy_names

    def test_compatibility_level_matches(self):
        pbir = SemanticModel.read(str(_AI_PBIR))
        legacy = SemanticModel.read(str(_AI_LEGACY))
        assert (
            pbir.definition.compatibilityLevel == legacy.definition.compatibilityLevel
        )
