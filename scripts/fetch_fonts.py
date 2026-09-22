"""Download the three OFL UI fonts as latin-subset variable woff2 files.

One-off provenance script: the woff2 files are committed, so this only needs to run
again if a font is updated. Uses the Google Fonts CSS API with a modern browser
User-Agent (that is what makes it return woff2), and takes the block marked `latin`.

Usage: python scripts/fetch_fonts.py
"""

import pathlib
import re
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
OUT = pathlib.Path(__file__).parent.parent / "src" / "web" / "static" / "fonts"
FONTS = {
    "bricolage-grotesque.woff2": "Bricolage+Grotesque:opsz,wght@12..96,400..800",
    "figtree.woff2": "Figtree:wght@400..700",
    "jetbrains-mono.woff2": "JetBrains+Mono:wght@500..600",
}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return resp.read()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, family in FONTS.items():
        css = _get(f"https://fonts.googleapis.com/css2?family={family}&display=swap").decode()
        match = re.search(r"/\* latin \*/\s*@font-face\s*{[^}]*?url\((https://[^)]+\.woff2)\)", css)
        if match is None:
            raise SystemExit(f"no latin woff2 block found for {family}")
        data = _get(match.group(1))
        if data[:4] != b"wOF2":
            raise SystemExit(f"{family}: not a woff2 file")
        (OUT / filename).write_bytes(data)
        print(f"{filename}: {len(data):,} bytes")


if __name__ == "__main__":
    main()
