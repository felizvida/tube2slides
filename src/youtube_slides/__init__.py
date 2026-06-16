"""Extract distinct presentation slides from talk videos."""

from .pipeline import ExtractConfig, ExtractionResult, extract_slides

__all__ = ["ExtractConfig", "ExtractionResult", "extract_slides"]

__version__ = "0.1.0"
