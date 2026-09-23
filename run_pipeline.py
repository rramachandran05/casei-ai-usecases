"""CLI entry for the CASEI-GeoFM discovery pipeline. Stages land in later tasks."""

import argparse

STAGES = ["harvest", "discover", "coincide", "assess", "rank", "export", "report"]


def main() -> None:
    parser = argparse.ArgumentParser(description="CASEI-GeoFM discovery pipeline")
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--limit", type=int, default=None, help="run on a slice of N records")
    args = parser.parse_args()
    raise SystemExit(f"stage '{args.stage}' not implemented yet")


if __name__ == "__main__":
    main()
