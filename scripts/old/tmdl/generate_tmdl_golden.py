"""Generate (or refresh) golden TMDL files for the Contoso model.bim sample.

Serializes ``report/contoso/ContosoSample.SemanticModel`` (model.bim format)
with our TmdlStrategy and writes every ``.tmdl`` part to
``tests/golden/tmdl/contoso/``.

Run manually whenever the serializer is intentionally changed and the new
output should become the new authoritative baseline:

    uv run python scripts/tmdl/generate_tmdl_golden.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so the package can be imported when run
# from an arbitrary working directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from poupytempo.persistence.strategies.model_bim import ModelBimStrategy  # noqa: E402
from poupytempo.persistence.strategies.tmdl import TmdlStrategy  # noqa: E402
from poupytempo.persistence.transports.local import LocalTransport  # noqa: E402

_SM_PATH = str(_REPO_ROOT / "report" / "contoso" / "ContosoSample.SemanticModel")
_GOLDEN_DIR = _REPO_ROOT / "tests" / "golden" / "tmdl" / "contoso"


def main() -> None:
    transport = LocalTransport()
    bim = ModelBimStrategy()
    tmdl = TmdlStrategy()

    print(f"Loading model.bim from: {_SM_PATH}")
    parts = transport.read_parts(_SM_PATH)
    sm = bim.deserialize(parts)

    tmdl_parts = [p for p in tmdl.serialize(sm) if p.path.endswith(".tmdl")]

    written = 0
    for part in tmdl_parts:
        dest = _GOLDEN_DIR / part.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(part.as_text(), encoding="utf-8")
        print(f"  wrote {dest.relative_to(_REPO_ROOT)}")
        written += 1

    print(f"\nDone — {written} golden file(s) written to {_GOLDEN_DIR.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()
