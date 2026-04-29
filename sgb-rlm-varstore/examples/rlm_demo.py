"""RLM-Demo: GKV-Fall „Kostenerstattung bei abgelehnter Krankenhausbehandlung"

Läuft gegen den SGB V Varstore unter /tmp/sgbpot-poc-sgb-v.
"""

from sgbpot.rlm_env import SGB, PACK


def demo():
    print("=" * 72)
    print('RLM-DEMO: GKV-Fall "Kostenerstattung bei abgelehnter Behandlung"')
    print("=" * 72)

    # Schritt 1: Bücher anzeigen
    print("\n▶ Schritt 1: Verfügbare Bücher")
    print(f"   SGB V books:  {SGB.books()}")

    # Schritt 2: Relevante Normen suchen
    print('\n▶ Schritt 2: Suche "Kostenerstattung selbstbeschaffte Leistung"')
    hits = SGB.search("Kostenerstattung selbstbeschaffte Leistung", k=10)
    gefunden = {h["norm_id"] for h in hits}
    print(f"   {len(gefunden)} relevante Normen gefunden")
    for h in hits[:6]:
        print(f"   [{h['norm_id']}] {h['text'][:80]}...")

    # Schritt 3: Norm-Detail abrufen
    print("\n▶ Schritt 3: Norm-Detail §13 SGB V (Kostenerstattung)")
    n = SGB.norm("SGB_V:§13")
    print(f"   Heading:  {n.heading}")
    print(f"   Absätze:  {len(n.spans())} Spans")
    spans = [s for s in n.spans() if s["unit_type"] == "paragraph"]
    for s in spans[:2]:
        print(f"   [{s['span_id']}] {s['text'][:120]}...")

    # Schritt 4: Beweiskette prüfen
    print("\n▶ Schritt 4: Beweiskette §13 → Card → Evidence")
    card = n.card()
    if card:
        print(f"   one_sentence: {card['one_sentence']}")
        for role in card.get("roles", []):
            for ev in role.get("evidence", []):
                existiert = any(ev == s["span_id"] for s in n.spans())
                print(f"   Role: {role['role']} [Evidence: {ev}] → existiert: {existiert}")

    # Schritt 5: Kontextpaket schnüren
    print("\n▶ Schritt 5: Kontextpaket für LLM-Subcall")
    packed = PACK.norms(
        ["SGB_V:§13"], include_raw=True, include_cards=True, max_chars=2000
    )
    for line in packed.split("\n")[:20]:
        print(f"   {line}")
    print("   ...")


if __name__ == "__main__":
    demo()
