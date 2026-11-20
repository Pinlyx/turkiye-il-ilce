"""Command line entry point: ``il-ilce 40.99 29.03``."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, lookup


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="il-ilce",
        description="Find the Turkish province and district of a coordinate, offline.",
    )
    parser.add_argument("lat", type=float, help="latitude in decimal degrees (WGS84)")
    parser.add_argument("lon", type=float, help="longitude in decimal degrees (WGS84)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

    try:
        result = lookup(args.lat, args.lon)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result))  # ASCII-escaped, safe on any console
    elif result is None:
        print("not found (outside Turkiye land boundaries)", file=sys.stderr)
    else:
        text = "%s / %s (%02d, %s)" % (result["il"], result["ilce"], result["plaka"], result["iso"])
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", "replace").decode("ascii"))
    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
