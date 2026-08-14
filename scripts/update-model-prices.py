#!/usr/bin/env python3
"""Refresh Runestone's local model-price snapshot from bounded public feeds."""

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

from runestone.config import settings
from runestone.model_costs.pricing import (
    DEFAULT_PRICE_PATH,
    REQUEST_TIMEOUT_SECONDS,
    PriceSnapshotError,
    refresh_prices,
    write_price_snapshot_atomic,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument(
        "--check",
        action="store_true",
        help="Fetch and validate without replacing state/model_prices.json",
    )
    destination.add_argument(
        "--output",
        type=Path,
        help="Write the validated snapshot to an explicit inspection path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:

        async def run_refresh():
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
                return await refresh_prices(settings, client=client)

        snapshot, counts = asyncio.run(run_refresh())
        if not args.check:
            write_price_snapshot_atomic(snapshot, args.output or DEFAULT_PRICE_PATH)
    except (httpx.HTTPError, OSError, PriceSnapshotError, ValueError) as exc:
        print(f"model price refresh failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"models.dev={counts.models_dev} portkey={counts.portkey} "
        f"stale={counts.stale} manual={counts.manual} unknown={counts.unknown}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
