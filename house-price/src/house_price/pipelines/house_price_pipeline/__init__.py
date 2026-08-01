"""House price pipeline: generate data -> split -> train -> evaluate."""

from .pipeline import create_pipeline

__all__ = ["create_pipeline"]
