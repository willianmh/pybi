import logging
import os
import shutil
from pathlib import Path

from ..types import Part

SKIP_NAMES = {"__pycache__", ".git", ".pbi", ".DS_Store"}

logger = logging.getLogger(__name__)


class LocalTransport:
    def read_parts(self, root: str):
        root_path = Path(root)

        if not root_path.is_dir():
            raise FileNotFoundError(f"Root directory does not exist: {root}")

        parts: list[Part] = []

        for dir_path, dir_names, filenames in os.walk(root_path):
            dir_names[:] = [d for d in dir_names if d not in SKIP_NAMES]

            for filename in filenames:
                if filename in SKIP_NAMES:
                    continue

                abs_path = Path(dir_path) / filename
                rel_path = abs_path.relative_to(root_path).as_posix()

                try:
                    payload = abs_path.read_bytes()
                except OSError as e:
                    logger.warning(f"Skipping unreadable file {abs_path}: {e}")
                    continue

                parts.append(Part(path=rel_path, payload=payload))

        return parts

    def write_parts(
        self,
        parts: list[Part],
        root: str,
        clean: bool = False,
    ) -> None:
        """Writes every `Part` as a file under *root*

        Args:
            parts: parts to write
            root: destination directory
            clean: if `True`, remove all existing files under *root* before writing.
                This prevents stale files, for example in the case of format upgrade, from lingering on disk"""
        root_path = Path(root)

        if clean and root_path.is_dir():
            shutil.rmtree(root_path)

        for part in parts:
            dest = root_path / part.path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(part.payload)
