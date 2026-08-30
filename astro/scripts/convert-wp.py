#!/usr/bin/env python3
"""Convert Discovery's WordPress articles to Starlight Markdown.

The Gutenberg handling this needs -- the three <pre> shapes, <br>-joined
commands, language inference, heading shifting -- is shared with the main
site's news importer and lives in scripts/wp_common.py. What stays here is
what is Starlight's alone: .mdx output, the <YouTube> component, and flattening
cross-article embeds to plain links.

    scripts/convert-wp.py pacman-basic-commands adding-swap-after-installation
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import wp_common as wp  # noqa: E402

API = "https://discovery.endeavouros.com/wp-json/wp/v2"
FIELDS = "slug,title,content,date,modified,categories"
OUT = Path(__file__).resolve().parent.parent / "src/content/docs"


def on_embed(block: str, stats: dict) -> str | None:
    yt = re.search(r"(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<\"]+)", block)
    if yt:
        stats["embed"] += 1
        return f'<YouTube url="{yt.group(1)}" />'
    # An embed of another Discovery article. Rendering WordPress's iframe card
    # is pointless once migrated; a plain link is the honest equivalent.
    return wp.default_embed(block, stats)


def main() -> int:
    slugs = sys.argv[1:]
    if not slugs:
        print(__doc__)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    for slug in slugs:
        post = wp.fetch(API, slug, FIELDS)
        title = wp.plain_title(post)
        body, st = wp.convert(post["content"]["rendered"], on_embed=on_embed)

        body = wp.strip_repeated_title(body, title)
        needs_youtube = "<YouTube" in body
        desc = wp.synth_description(body, title)

        fm = [
            "---",
            f'title: "{title}"',
            f'description: "{desc}"',
            "---",
        ]
        if needs_youtube:
            fm.append("")
            fm.append('import YouTube from "../../components/YouTube.astro";')

        (OUT / f"{slug}.mdx").write_text("\n".join(fm) + "\n\n" + body)
        print(
            f"  {slug}.mdx  {st['code']} code blocks "
            f"({st['lang']} typed, {st['multiline']} multi-line), "
            f"{st['embed']} video embeds, {st['xref']} cross-refs, {st['img']} images"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
