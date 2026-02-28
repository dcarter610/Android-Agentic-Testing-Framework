from __future__ import annotations

from pathlib import Path
from typing import Any

from .interfaces import ArtifactStore
from .models import write_json


class FilesystemArtifactStore(ArtifactStore):
    def __init__(self, out_root: str = "out") -> None:
        self.out_root = Path(out_root)

    def scenario_dir(self, run_id: str, scenario_id: str) -> Path:
        d = self.out_root / run_id / scenario_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_json(self, run_id: str, scenario_id: str, name: str, payload: Any) -> Path:
        path = self.scenario_dir(run_id, scenario_id) / name
        write_json(path, payload)
        return path

    def write_text(self, run_id: str, scenario_id: str, name: str, text: str) -> Path:
        path = self.scenario_dir(run_id, scenario_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path
