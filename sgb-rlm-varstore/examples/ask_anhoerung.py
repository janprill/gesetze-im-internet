from sgbpot.varstore import SGBMemory


def main() -> None:
    sgb = SGBMemory("varstore")
    try:
        hits = sgb.search("Anhörung Verwaltungsakt", k=5)
    except Exception as exc:
        print(f"Varstore not available: {exc}")
        return

    print(hits)
    try:
        print(sgb.packer.norms(["SGB_X:§24"], include_cards=True))
    except Exception as exc:
        print(f"Pack failed: {exc}")


if __name__ == "__main__":
    main()
