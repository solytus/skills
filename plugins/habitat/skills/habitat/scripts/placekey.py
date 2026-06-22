"""place_key construction: normalize names + build keys with a 4-decimal geocode."""
from __future__ import annotations

import re


def normalize_name(name):
    """Lowercase slug: runs of non-alphanumerics collapse to a single hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _trunc4(num_str):
    """Truncate (not round) a numeric string's fractional part to 4 digits, zero-padded."""
    num_str = num_str.strip()
    neg = num_str.startswith("-")
    s = num_str.lstrip("+-")
    intp, _, frac = s.partition(".")
    frac = (frac + "0000")[:4]
    out = f"{intp}.{frac}"
    return ("-" + out) if neg else out


def trunc_geocode(geocode):
    """'lat,lon' -> each component truncated to exactly 4 decimals."""
    return ",".join(_trunc4(p) for p in geocode.split(","))


def build_place_key(level, name, geocode):
    """Compose '<level>::<normalized_name>::<lat,lon>' (name normalized, geocode truncated)."""
    return f"{level}::{normalize_name(name)}::{trunc_geocode(geocode)}"


def _main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="Build a Habitat place_key.")
    ap.add_argument("--level", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--geocode", required=True, help='"lat,lon"')
    a = ap.parse_args(argv)
    print(build_place_key(a.level, a.name, a.geocode))


if __name__ == "__main__":
    _main()
