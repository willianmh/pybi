"""SemanticQuery models package.

This package provides Pydantic V2 models for Power BI semantic query structures,
including the hand-crafted QueryExpressionContainer that handles ~47 expression types.
"""

# Export the hand-crafted expression container (always available)
from .expressions import *  # noqa: F401, F403

# Export generated models
from .v1_4_0.model import *  # noqa: F401, F403
