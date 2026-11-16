"""Read or bump the version in the release manifest source."""

import argparse
from pathlib import Path
import re


VERSION = Path(__file__).resolve().parents[1] / "VERSION"
BUMP_INDEX = {"major": 0, "minor": 1, "patch": 2}


def next_version(version, bump):
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("VERSION must contain a major.minor.patch version")
    if bump == "none":
        return version
    parts = [int(part) for part in version.split(".")]
    index = BUMP_INDEX[bump]
    parts[index] += 1
    parts[index + 1:] = [0] * (2 - index)
    return ".".join(map(str, parts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bump", choices=("none", *BUMP_INDEX))
    args = parser.parse_args()
    try:
        version = next_version(VERSION.read_text(encoding="ascii").strip(), args.bump)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    if args.bump != "none":
        VERSION.write_bytes((version + "\n").encode("ascii"))
    print(version)


if __name__ == "__main__":
    main()
