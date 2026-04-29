from sgbpot.rlm_env import SGB


def main() -> None:
    try:
        hits = SGB.search("Aufhebung Rücknahme Bescheid", k=8)
        print(hits)
    except Exception as exc:
        print(f"Varstore not available: {exc}")


if __name__ == "__main__":
    main()
