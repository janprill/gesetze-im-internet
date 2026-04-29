from __future__ import annotations

"""Kommandozeilen-Schnittstelle für den Proof-Varstore."""

import argparse
import json
from pathlib import Path

from .build_index import build_index
from .compile_cards_spark import compile_cards
from .compile_topics_spark import compile_topics
from .ingest_xml import ingest_from_data_branch, ingest_from_fixture
from .validate import run_validate


def _print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))




def _parse_books(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    if len(values) == 1 and "," in values[0]:
        return [item for item in values[0].split(",") if item]
    return values


def _cmd_ingest(args: argparse.Namespace) -> int:
    repo = args.repo if args.repo is not None else args._repo
    books = _parse_books(args.books)

    if args.fixture:
        paths = [args.fixture]
        for path in paths:
            if not Path(path).exists():
                raise SystemExit(f"fixture path not found: {path}")
        result = ingest_from_fixture(args.fixture, args.out, config_path=args.config, repo=repo, books=books)
    else:
        if not args.data_ref:
            raise SystemExit("--data-ref is required with repo mode")
        result = ingest_from_data_branch(repo, args.data_ref, args.out, config_path=args.config, books=books)
    _print_json({k: str(v) for k, v in result.items()})
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    path = Path(args.varstore)
    if not path.exists():
        raise SystemExit(f"varstore not found: {args.varstore}")
    db = build_index(args.varstore)
    print(str(db))
    return 0


def _cmd_compile_cards(args: argparse.Namespace) -> int:
    books = args.books if args.books else None
    if books and len(books) == 1 and "," in books[0]:
        books = [item for item in books[0].split(",") if item]
    if args.all_books:
        books = None  # None = alle Bücher
    try:
        result = compile_cards(args.varstore, books=books, dry_run=args.dry_run, model=args.model)
    except RuntimeError as exc:
        raise SystemExit(str(exc))
    print(f"written: {result.count} cards")
    print(str(result.output_path))
    return 0


def _cmd_compile_topics(args: argparse.Namespace) -> int:
    try:
        compile_topics(args.varstore, dry_run=args.dry_run, model=args.model)
    except RuntimeError as exc:
        raise SystemExit(str(exc))
    print("written topics.jsonl")
    return 0

def _cmd_validate(args: argparse.Namespace) -> int:
    return run_validate(args.varstore)


def _cmd_search(args: argparse.Namespace) -> int:
    from .varstore import MissingVarstoreError, SGBMemory

    mem = SGBMemory(args.varstore)
    try:
        hits = mem.search(args.query, k=args.k)
    except MissingVarstoreError as exc:
        raise SystemExit(str(exc))
    _print_json(hits)
    return 0

def _cmd_inspect(args: argparse.Namespace) -> int:
    from .varstore import MissingVarstoreError, SGBMemory

    mem = SGBMemory(args.varstore)
    try:
        n = mem.norm(args.norm)
    except KeyError as exc:
        raise SystemExit(str(exc))
    except MissingVarstoreError as exc:
        raise SystemExit(str(exc))

    out = {
        "norm_id": args.norm,
        "text": n.text(),
        "spans": n.spans(),
        "card": n.card(),
        "neighbors": n.neighbors(),
    }
    _print_json(out)
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sgbpot.cli")
    parser.add_argument("--repo", dest="_repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--fixture")
    ingest.add_argument("--repo", default=None)
    ingest.add_argument("--data-ref", default="data")
    ingest.add_argument("--books", nargs="*", default=None)
    ingest.add_argument("--out", default="varstore")
    ingest.add_argument("--config", default="config/sgb_books.yaml")
    ingest.set_defaults(func=_cmd_ingest)

    index = sub.add_parser("index")
    index.add_argument("--varstore", required=True)
    index.set_defaults(func=_cmd_index)

    compile_cards_cmd = sub.add_parser("compile-cards")
    compile_cards_cmd.add_argument("--varstore", required=True)
    compile_books_group = compile_cards_cmd.add_mutually_exclusive_group()
    compile_books_group.add_argument("--books", nargs="*", default=None)
    compile_books_group.add_argument("--all-books", action="store_true", default=False,
                                      help="Alle Bücher ohne Filterung kompilieren")
    compile_cards_cmd.add_argument("--dry-run", action="store_true", default=False)
    compile_cards_cmd.add_argument("--model", default="dry-run")
    compile_cards_cmd.add_argument("--prompt-version", default="norm-card-v0.1")
    compile_cards_cmd.set_defaults(func=_cmd_compile_cards)

    compile_topics_cmd = sub.add_parser("compile-topics")
    compile_topics_cmd.add_argument("--varstore", required=True)
    compile_topics_cmd.add_argument("--dry-run", action="store_true", default=False)
    compile_topics_cmd.add_argument("--model", default="dry-run")
    compile_topics_cmd.set_defaults(func=_cmd_compile_topics)

    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--varstore", required=True)
    validate_cmd.set_defaults(func=_cmd_validate)

    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("--varstore", required=True)
    inspect_cmd.add_argument("--norm", required=True)
    inspect_cmd.set_defaults(func=_cmd_inspect)

    search_cmd = sub.add_parser("search")
    search_cmd.add_argument("--varstore", required=True)
    search_cmd.add_argument("--query", required=True)
    search_cmd.add_argument("--k", type=int, default=20)
    search_cmd.set_defaults(func=_cmd_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
