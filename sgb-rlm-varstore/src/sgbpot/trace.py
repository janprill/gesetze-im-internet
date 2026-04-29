from __future__ import annotations

"""Trace-Metadaten für Compiler- oder CLI-Läufe."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import uuid


@dataclass(frozen=True)
class TraceEvent:
    run_id: str
    source_commit: str
    command: str
    model: str
    prompt_version: str
    input_hash: str
    output_hash: str
    validation_status: str


def _sha256_of_path(path: Path) -> str:
    h = sha256()
    if not path.exists():
        return ""
    h.update(path.read_bytes())
    return f"sha256:{h.hexdigest()}"


def new_trace(
    varstore_path: str,
    command: str,
    model: str,
    prompt_version: str,
    output_path: str,
    validation_status: str = "unknown",
) -> TraceEvent:
    root = Path(varstore_path)
    source = root / "source.json"
    source_commit = ""
    if source.exists():
        try:
            source_commit = json.loads(source.read_text(encoding="utf-8")).get("source_commit", "")
        except Exception:
            source_commit = ""

    input_hash = _sha256_of_path(source)
    output_hash = _sha256_of_path(Path(output_path)) if output_path else ""
    return TraceEvent(
        run_id=str(uuid.uuid4()),
        source_commit=source_commit,
        command=command,
        model=model,
        prompt_version=prompt_version,
        input_hash=input_hash,
        output_hash=output_hash,
        validation_status=validation_status,
    )


def write_trace(varstore_path: str, event: TraceEvent) -> Path:
    root = Path(varstore_path)
    trace_file = root / "trace.jsonl"
    with trace_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.__dict__, ensure_ascii=False) + "\n")
    return trace_file


def read_traces(varstore_path: str) -> list[TraceEvent]:
    trace_file = Path(varstore_path) / "trace.jsonl"
    if not trace_file.exists():
        return []
    out: list[TraceEvent] = []
    for line in trace_file.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        data = json.loads(line)
        out.append(TraceEvent(**data))
    return out
