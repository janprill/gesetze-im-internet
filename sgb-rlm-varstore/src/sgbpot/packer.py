from __future__ import annotations

"""Kontextpacker für auditierbare Prompt-Pakete."""

from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from .varstore import SGBMemory


class Packer:
    def __init__(self, memory: "SGBMemory") -> None:
        self.memory = memory

    def _evidence_line(self, evidence: Iterable[str]) -> str:
        vals = [e for e in evidence if e]
        return ", ".join(vals)

    def norms(
        self,
        ids: list[str],
        include_raw: bool = True,
        include_cards: bool = True,
        include_topics: bool = False,
        max_chars: int = 60000,
    ) -> str:
        self.memory._ensure_loaded()
        source_commit = self.memory.source_commit

        lines: list[str] = ["# Kontextpaket", f"source_commit: {source_commit}", ""]

        for norm_id in ids:
            norm_var = self.memory.norm(norm_id)
            lines.append(f"## {norm_id} — {norm_var.heading}")

            if include_raw:
                lines.append("")
                lines.append("### Raw Spans")
                for span in norm_var.spans():
                    lines.append(f"[{span['span_id']}] {span.get('text', '')}")

            card = norm_var.card() if include_cards else None
            if card:
                lines.append("")
                lines.append("### Memory Card")
                lines.append(f"one_sentence: {card.get('one_sentence', '')}")
                for key in ["roles", "actors", "legal_effects", "conditions", "exceptions_or_limits"]:
                    bucket = card.get(key, []) or []
                    lines.append(f"{key}:")
                    for entry in bucket:
                        if isinstance(entry, dict):
                            label = next(
                                (
                                    entry.get(x)
                                    for x in ("role", "text", "actor", "question")
                                    if entry.get(x)
                                ),
                                "",
                            )
                            evidence = self._evidence_line(entry.get("evidence", []))
                            if evidence:
                                lines.append(f"- {label} [Evidence: {evidence}]")
                            elif label:
                                lines.append(f"- {label}")

            if include_topics:
                topic_lines = ["### Topics"]
                for topic in self.memory.topics_by_norm.get(norm_id, []):
                    topic_lines.append(f"- {topic.get('label')} [{', '.join(topic.get('core_norms', []))}]")
                if len(topic_lines) > 1:
                    lines.extend([""] + topic_lines)

            lines.append("")

        output = "\n".join(lines).rstrip()

        if len(output) <= max_chars:
            return output

        # Reduziere zuerst Karteninhalte.
        reduced_lines = lines[:]
        i = 0
        while i < len(reduced_lines):
            if reduced_lines[i] == "### Memory Card":
                j = i + 1
                if j < len(reduced_lines) and reduced_lines[j].startswith("one_sentence:"):
                    j += 1
                    while j < len(reduced_lines) and reduced_lines[j] and not reduced_lines[j].startswith("###") and not reduced_lines[j].startswith("##"):
                        reduced_lines[j] = ""
                        j += 1
                    reduced_lines = [line for line in reduced_lines if line != ""]
                    trimmed = "\n".join(reduced_lines).rstrip()
                    if len(trimmed) <= max_chars:
                        return trimmed
            i += 1

        return "\n".join(reduced_lines).rstrip()


__all__ = ["Packer"]
