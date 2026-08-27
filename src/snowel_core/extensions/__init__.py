# src/snowel_core/extensions/__init__.py
from . import discovery
from .discovery import PackManifest, discover, parse_manifest

__all__ = ["discovery", "PackManifest", "discover", "parse_manifest"]
