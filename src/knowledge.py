"""Load the knowledge base (markdown files in data/knowledge) into passages.

Each `## Heading` in a knowledge file becomes one Passage. Lines of the form
`key: value` directly under the heading are stored as fields, and the rest is
the passage text that the retriever searches.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_FIELD_LINE = re.compile(r"^([a-z_]+):\s*(.+)$")


@dataclass
class Passage:
    """One retrievable section of a knowledge document."""

    doc_id: str  # e.g. "genres.md#indie-pop", used as the citation
    source: str  # file name without extension: "genres", "moods", "song_notes"
    title: str
    text: str
    fields: Dict[str, str] = field(default_factory=dict)

    @property
    def related(self) -> List[str]:
        """Labels listed in the `related:` field, lowercased."""
        return [x.strip().lower() for x in self.fields.get("related", "").split(",") if x.strip()]

    @property
    def typical_energy(self) -> Optional[float]:
        """The `typical_energy:` field as a float, or None if missing or invalid."""
        try:
            value = float(self.fields["typical_energy"])
        except (KeyError, ValueError):
            return None
        return value if 0.0 <= value <= 1.0 else None

    @property
    def song_id(self) -> Optional[int]:
        """The `song_id:` field as an int, or None if missing or invalid."""
        try:
            return int(self.fields["song_id"])
        except (KeyError, ValueError):
            return None


def _slug(title: str) -> str:
    """Turn a heading into a stable anchor ("Indie Pop" -> "indie-pop")."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def parse_knowledge_file(path: str) -> List[Passage]:
    """Split one markdown file into passages, one per `## ` heading."""
    name = os.path.basename(path)
    source = os.path.splitext(name)[0]
    passages: List[Passage] = []
    title: Optional[str] = None
    fields: Dict[str, str] = {}
    body: List[str] = []

    def flush() -> None:
        if title is not None:
            passages.append(Passage(f"{name}#{_slug(title)}", source, title, " ".join(body), dict(fields)))

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("## "):
                flush()
                title, fields, body = line[3:].strip(), {}, []
            elif title is None or not line:
                continue  # file intro before the first heading, or a blank line
            elif not body and _FIELD_LINE.match(line):
                key, value = _FIELD_LINE.match(line).groups()
                fields[key] = value.strip()
            else:
                body.append(line)
    flush()
    return passages


def load_knowledge(directory: str) -> List[Passage]:
    """Load every .md file in a directory, in file name order."""
    passages: List[Passage] = []
    for name in sorted(os.listdir(directory)):
        if name.endswith(".md"):
            passages.extend(parse_knowledge_file(os.path.join(directory, name)))
    return passages
