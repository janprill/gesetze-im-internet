from sgbpot.rlm_env import SGB, CARD


def main() -> None:
    try:
        print(SGB.search("Verwaltungsakt", k=5))
        card = CARD("SGB_X:§31")
        print(card.get("one_sentence") if card else "No card for SGB_X:§31")
    except Exception as exc:
        print(f"Varstore not available: {exc}")


if __name__ == "__main__":
    main()
