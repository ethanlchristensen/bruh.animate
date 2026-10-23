"""Build Sphinx HTML strictly, without external inventory requests by default."""

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from sphinx.application import Sphinx

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online-inventories", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    app = Sphinx(
        str(root / "docs/source"),
        str(root / "docs/source"),
        str(root / "docs/build/html"),
        str(root / "docs/build/doctrees"),
        "html",
        confoverrides={} if args.online_inventories else {"intersphinx_mapping": {}},
        freshenv=True,
        warningiserror=True,
    )
    app.build(force_all=True)
    return app.statuscode


if __name__ == "__main__":
    raise SystemExit(main())
