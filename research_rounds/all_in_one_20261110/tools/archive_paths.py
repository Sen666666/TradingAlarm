"""Portable archive paths. Historical source strings are identifiers, never fallbacks."""
import json
import os
from pathlib import Path


def validate_map(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Source map must contain a non-empty roots list")
    sources, destinations = set(), []
    for row in rows:
        source = Path(row["source"])
        dest = Path(row["destination"])
        if not source.is_absolute() or ".." in source.parts:
            raise ValueError("Source identifiers must be absolute normalized paths")
        if dest.is_absolute() or not dest.parts or ".." in dest.parts:
            raise ValueError("Destination must be a non-empty archive-relative path")
        if row["kind"] not in ("file", "directory"):
            raise ValueError("Unsupported mapping kind")
        if str(source) in sources:
            raise ValueError("Duplicate source mapping")
        if any(dest == d or dest.is_relative_to(d) or d.is_relative_to(dest) for d in destinations):
            raise ValueError("Overlapping archive destinations")
        sources.add(str(source)); destinations.append(dest)
    return rows


class ArchivePaths:
    def __init__(self, root=None, source_map="manifest/SOURCE_MAP.json"):
        self.root = Path(root or os.environ.get("RESEARCH_ARCHIVE_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
        self.map_path = self.inside(source_map)
        self.mappings = validate_map(json.loads(self.map_path.read_text())["roots"])

    def inside(self, path):
        path = Path(path)
        candidate = path if path.is_absolute() else self.root / path
        if not candidate.resolve().is_relative_to(self.root):
            raise ValueError("Path escapes archive: " + str(path))
        return candidate

    def resolve(self, old):
        old = Path(old)
        if ".." in old.parts:
            raise ValueError("Parent traversal is not allowed")
        if not old.is_absolute():
            return self.inside(old)
        for item in sorted(self.mappings, key=lambda x: len(Path(x["source"]).parts), reverse=True):
            source = Path(item["source"])
            if old == source:
                return self.inside(item["destination"])
            if item["kind"] == "directory" and old.is_relative_to(source):
                return self.inside(Path(item["destination"]) / old.relative_to(source))
        if old.is_relative_to(self.root):
            return self.inside(old)
        raise ValueError("No archived mapping: " + str(old))
