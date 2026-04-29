# Prompt: Norm Card (Thin)

Nutze ausschließlich bereitgestellte Spans.
Erfinde keine Normen, Absätze oder Span-IDs.
Jede Rolle, Voraussetzung, Rechtsfolge, Ausnahme und Frage braucht Evidence.
Wenn der Text etwas nicht trägt, lass es weg.
Keine Rechtsberatung.
Keine finale Auslegung.
Nur valides JSON nach Schema ausgeben.

Ausgabeformat: JSON mit Feldern `card_id`, `card_type`, `norm_id`, `book_id`, `heading`,
`one_sentence`, `roles`, `actors`, `legal_effects`, `conditions`,
`exceptions_or_limits`, `topic_tags`, `likely_questions`, `xref_candidates`,
`compiler`.

Evidenzangaben immer als vorhandene `span_id` in `evidence`.
