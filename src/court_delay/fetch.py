"""Get DDL raw data: stream the Dropbox zip, save the archives we need, extract one year at a time.

The Dropbox folder downloads as one ~5 GB zip and does not support byte ranges, so we stream it
and write only matching members. The zip holds csv/ and dta/ copies of everything; we keep csv/.
Layout inside csv/: keys/keys.tar.gz, cases/cases.tar.gz (all years, ~1.4 GB), acts_sections...
Every member seen is logged to data/raw/manifest.txt.

Usage:
    python -m court_delay.fetch download cases        # -> data/raw/cases/cases.tar.gz
    python -m court_delay.fetch download keys acts
    python -m court_delay.fetch extract 2010          # cases.tar.gz -> data/raw/cases/cases_2010.csv
"""
import argparse
import re
import tarfile

import httpx

from court_delay import config as C
from court_delay.ingest import parse_years
from court_delay.ziptail import iter_zip

DDL_URL = "https://www.dropbox.com/sh/hkcde3z2l1h9mq1/AADRe-BuBQ92ozAJiG7YERdCa?dl=1"

PATTERNS = {
    "keys": re.compile(r"^csv/keys/[^/]+$", re.I),
    "cases": re.compile(r"^csv/cases/[^/]+$", re.I),
    "acts": re.compile(r"^csv/acts_sections[^/]*(/[^/]+)?$", re.I),
}
TARGET_DIRS = {"keys": C.RAW / "keys", "cases": C.RAW / "cases", "acts": C.RAW}
CASES_ARCHIVE = C.RAW / "cases" / "cases.tar.gz"


def download(what: list[str], url: str = DDL_URL) -> None:
    C.RAW.mkdir(parents=True, exist_ok=True)
    manifest = open(C.RAW / "manifest.txt", "a", encoding="utf-8")
    pending, streamed = set(what), 0

    def chunks(resp):
        nonlocal streamed
        for b in resp.iter_bytes(1 << 20):
            streamed += len(b)
            if streamed % (256 << 20) < len(b):
                print(f"  ...{streamed / 1e9:.2f} GB streamed", flush=True)
            yield b

    with httpx.stream("GET", url, follow_redirects=True, timeout=120,
                      headers={"User-Agent": "Mozilla/5.0"}) as resp:
        resp.raise_for_status()
        for name, member in iter_zip(chunks(resp)):
            kind = next((k for k in what if PATTERNS[k].search(name)), None)
            if kind is None:
                size = sum(len(b) for b in member)  # must drain to advance the stream
                manifest.write(f"{name}\t{size}\n")
                manifest.flush()
                continue
            out = TARGET_DIRS[kind] / name.rsplit("/", 1)[-1]
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "wb") as f:
                for b in member:
                    f.write(b)
            manifest.write(f"{name}\t{out.stat().st_size}\tSAVED\n")
            manifest.flush()
            print(f"saved {name} -> {out.relative_to(C.ROOT)} ({out.stat().st_size / 1e6:.1f} MB)",
                  flush=True)
            # csv/keys and csv/cases are single archives; stop early once each wanted kind is saved.
            pending.discard(kind)
            if not pending and "acts" not in what:
                print("  all requested archives saved; stopping stream")
                break
    manifest.close()


def extract_years(years: list[int], archive=CASES_ARCHIVE) -> None:
    """Pull cases_<year>.csv[.gz] out of the all-years archive in one sequential pass."""
    wanted = {y: re.compile(rf"(^|/)cases_{y}\.csv(\.gz)?$") for y in years}
    out_dir = C.RAW / "cases"
    with tarfile.open(archive, "r|gz") as tar:
        for m in tar:
            year = next((y for y, p in wanted.items() if p.search(m.name)), None)
            if year is None or not m.isfile():
                continue
            out = out_dir / m.name.rsplit("/", 1)[-1]
            with tar.extractfile(m) as src, open(out, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            print(f"extracted {m.name} -> {out.relative_to(C.ROOT)} ({out.stat().st_size / 1e6:.0f} MB)")
            del wanted[year]
            if not wanted:
                break
    if wanted:
        print(f"not found in archive: {sorted(wanted)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download")
    d.add_argument("what", nargs="+", choices=sorted(PATTERNS))
    e = sub.add_parser("extract")
    e.add_argument("years", help="e.g. 2010 or 2010-2012")
    args = ap.parse_args()
    if args.cmd == "download":
        download(args.what)
    else:
        extract_years(parse_years(args.years))


if __name__ == "__main__":
    main()
