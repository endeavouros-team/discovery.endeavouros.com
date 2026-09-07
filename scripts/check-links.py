#!/usr/bin/env python3
"""Check every internal link in a build actually resolves.

A link to a page that does not exist is invisible in review: the markup looks
right, the build succeeds, and the 404 only appears when someone clicks. This
walks the built HTML, resolves every root-relative href and src against the
output tree, and checks every same-page anchor has a matching id.

External links are skipped on purpose — reachability of someone else's host is
not this repository's to assert.

Exits non-zero if any link is dead, printing every one.
"""

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    dist = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "astro" / "dist"
    if not dist.is_dir():
        print(f"  no build output at {dist} — run make build first", file=sys.stderr)
        return 1

    bad: list[str] = []
    n = 0

    for f in dist.rglob("*.html"):
        html = f.read_text(encoding="utf-8", errors="replace")
        for href in re.findall(r'(?:href|src)="([^"]+)"', html):
            if href.startswith(("http", "mailto:", "data:", "magnet:", "//")):
                continue
            if href.startswith("#"):
                a = href[1:]
                if a and f'id="{a}"' not in html:
                    bad.append(f"{f.relative_to(dist)} -> dead anchor {href}")
                continue
            n += 1
            # An href is a URL and a path is not: a filename with a character
            # that has to be escaped -- the fraction slash in tux-b/w.jpg is
            # the one in this build -- arrives here as %E2%81%84 and would look
            # missing on disk. The browser and nginx both undo this.
            p = urllib.parse.unquote(href.split("#")[0].split("?")[0].lstrip("/"))
            if not p:
                continue
            if p.endswith("/"):
                p += "index.html"
            if not ((dist / p).exists() or (dist / (p + "/index.html")).exists()
                    or (dist / (p + ".html")).exists()):
                bad.append(f"{f.relative_to(dist)} -> missing {href}")

    print(f"  checked {n} internal links")
    if bad:
        print("\n".join("  " + b for b in bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
