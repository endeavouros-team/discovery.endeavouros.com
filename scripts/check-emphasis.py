#!/usr/bin/env python3
"""Check no literal ** reached the rendered prose.

WordPress writes bold as <strong>, and often with a space inside it, which
CommonMark refuses to open or close emphasis on: `**text **` is not bold, it is
four asterisks a reader can see. That is invisible in the .mdx -- the source
looks like emphasis -- and invisible to the build, which renders it happily. It
shows up only on the page, which is why this reads the build rather than the
Markdown.

Code is exempt: `**` is a shell glob and a C pointer, and a fence is meant to
show what was typed.

Exits non-zero, naming every page and the text around the asterisks.
"""

import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Two articles print ** in their prose and are right to. pacman-actions-explained
# types it as text, about pacman's own output; automatic-update-of-the-pacman-
# database names the path /var/local/**pakbak, which Markdown cannot spell any
# other way.
ALLOW = {"pacman-actions-explained", "automatic-update-of-the-pacman-database"}

SKIP = {"code", "pre", "script", "style"}


class Prose(HTMLParser):
    """The text of a page, minus what is quoted rather than said."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.text.append(data)


def main() -> int:
    dist = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "astro" / "dist"
    if not dist.is_dir():
        print(f"  no build output at {dist} — run make build first", file=sys.stderr)
        return 1

    bad: list[str] = []
    pages = 0

    for f in sorted(dist.rglob("*.html")):
        page = f.relative_to(dist).parts[0].removesuffix(".html")
        if page in ALLOW:
            continue
        pages += 1
        p = Prose()
        p.feed(f.read_text(encoding="utf-8", errors="replace"))
        text = "".join(p.text)
        start = 0
        while (i := text.find("**", start)) >= 0:
            bad.append(f"{f.relative_to(dist)}: ...{text[max(0, i - 40):i + 40].strip()}...")
            start = i + 2

    print(f"  checked {pages} pages for literal ** in the prose")
    if bad:
        print("\n".join("  " + b for b in bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
