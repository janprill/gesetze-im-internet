from sgbpot.varstore import SGBMemory


def main() -> None:
    sgb = SGBMemory("varstore")
    try:
        print(sgb.search("Mitwirkungspflichten", k=5))
    except Exception as exc:
        print(f"Varstore not available: {exc}")


if __name__ == "__main__":
    main()
