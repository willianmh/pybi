"""TMDL folder loader - orchestrates loading TMDL files from a definition folder."""

import logging
from typing import Any

from ....semanticmodel.definition import (
    Culture,
    Expression,
    Model,
    Relationship,
    Table,
)
from .grammar import (
    DEFINITION_FILES,
    DEFINITION_FOLDERS,
)
from .parser import ObjectDeclaration, parse_tmdl
from .transformer import TMDLTransformer

logger = logging.getLogger(__name__)

# ------------------------------------------
# In-memory loader (operates on dict[str, str] instead of filesystem)
# ------------------------------------------


class TMDLPartsLoader:
    """Load a semantic model from in-memory TMDL content.

    Accepts a mapping of ``{relative_path: text_content}`` where paths use
    forward slashes and are relative to the ``definition/`` folder, e.g.::

        {
            "database.tmdl": "database\\n\\tcompatibilityLevel: 1600\\n",
            "model.tmdl": "model Model\\n\\tculture: en-US\\n...",
            "tables/Sales.tmdl": "table Sales\\n...",
            ...
        }
    """

    def __init__(self, files: dict[str, str]) -> None:
        self.files = files
        self.transformer = TMDLTransformer()

    def _parse_content(self, key: str) -> list[ObjectDeclaration]:
        content = self.files.get(key, "")
        if not content.strip():
            return []
        return parse_tmdl(content, key)

    def _load_database(self) -> int:
        nodes = self._parse_content(DEFINITION_FILES["database"])
        for node in nodes:
            if node.object_type == "database":
                return self.transformer.transform_database(node)
        return 1600

    def _load_expressions(self) -> list[Expression]:
        nodes = self._parse_content(DEFINITION_FILES["expressions"])
        return [
            self.transformer.transform_expression(n)
            for n in nodes
            if n.object_type == "expression"
        ]

    def _load_relationships(self) -> list[Relationship]:
        nodes = self._parse_content(DEFINITION_FILES["relationships"])
        return [
            self.transformer.transform_relationship(n)
            for n in nodes
            if n.object_type == "relationship"
        ]

    def _load_cultures(self) -> list[Culture]:
        cultures: list[Culture] = []
        cultures_prefix = f"{DEFINITION_FOLDERS['cultures']}/"
        culture_keys = sorted(
            k
            for k in self.files
            if k.startswith(cultures_prefix) and k.endswith(".tmdl")
        )
        if not culture_keys:
            return [Culture()]
        for key in culture_keys:
            nodes = self._parse_content(key)
            for n in nodes:
                if n.object_type == "cultureInfo":
                    cultures.append(self.transformer.transform_culture(n))
        return cultures if cultures else [Culture()]

    def _load_tables(self) -> list[Table]:
        tables_prefix = f"{DEFINITION_FOLDERS['tables']}/"
        table_keys = sorted(
            k for k in self.files if k.startswith(tables_prefix) and k.endswith(".tmdl")
        )
        tables: list[Table] = []
        for key in table_keys:
            nodes = self._parse_content(key)
            for n in nodes:
                if n.object_type == "table":
                    tables.append(self.transformer.transform_table(n))
        return tables

    def _load_model_config(self) -> ObjectDeclaration | None:
        nodes = self._parse_content(DEFINITION_FILES["model"])
        model_node = None
        top_level_annotations = []
        for node in nodes:
            if node.object_type == "model":
                model_node = node
            elif node.object_type == "annotation":
                top_level_annotations.append(node)
        if model_node and top_level_annotations:
            model_node.children.extend(top_level_annotations)
        return model_node

    def load(self) -> dict[str, Any]:
        """Load the complete semantic model from in-memory TMDL strings.

        Returns the same ``{"compatibilityLevel": int, "model": Model}`` dict
        as ``TMDLFolderLoader.load()``.
        """
        compat_level = self._load_database()
        expressions = self._load_expressions()
        relationships = self._load_relationships()
        cultures = self._load_cultures()
        tables = self._load_tables()
        model_config = self._load_model_config()

        if model_config:
            model = self.transformer.transform_model(
                model_config,
                tables=tables,
                relationships=relationships,
                expressions=expressions,
                cultures=cultures,
            )
        else:
            model = Model(
                tables=tables or None,
                relationships=relationships or None,
                expressions=expressions or None,
                cultures=cultures,
            )

        return {
            "compatibilityLevel": compat_level,
            "model": model,
        }
