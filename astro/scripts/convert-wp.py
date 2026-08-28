#!/usr/bin/env python3
"""Convert Discovery's WordPress articles to Starlight Markdown.

Discovery's Gutenberg markup does three things that defeat a generic HTML-to-
Markdown converter, which is why this exists rather than a pandoc invocation:

  1. Code blocks come in three shapes, not one:
         <pre class="wp-block-code"><code>one line</code></pre>
         <pre class="wp-block-preformatted">no code element at all<br></pre>
         <pre><code><code>nested</code><br><code>code elements</code></code></pre>
  2. Multi-line commands are joined with <br>, not newlines. Convert naively and
     every multi-line shell snippet collapses onto one line.
  3. Nothing carries a language, so 253 code blocks would render unhighlighted.
     Languages are inferred from the first token.

    scripts/convert-wp.py pacman-basic-commands adding-swap-after-installation
"""

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

API = "https://discovery.endeavouros.com/wp-json/wp/v2"
OUT = Path(__file__).resolve().parent.parent / "src/content/docs"

# First token -> language. Anything unmatched stays unlabelled rather than
# guessing wrong, since a wrong label highlights misleadingly.
SHELL = {
    "sudo", "pacman", "yay", "paru", "systemctl", "cd", "ls", "cp", "mv", "rm",
    "mkdir", "nano", "vim", "echo", "cat", "grep", "chmod", "chown", "curl",
    "wget", "git", "df", "du", "free", "swapon", "swapoff", "mkswap", "btrfs",
    "lsblk", "mount", "umount", "journalctl", "dmesg", "modprobe", "lspci",
    "lsusb", "reboot", "eos-", "mkinitcpio", "grub-mkconfig", "gpg", "sha512sum",
}


def fetch(slug: str) -> dict:
    url = f"{API}/posts?slug={slug}&_fields=slug,title,content,date,modified,categories"
    with urllib.request.urlopen(url, timeout=60) as r:
        posts = json.load(r)
    if not posts:
        raise SystemExit(f"  no article found for slug {slug!r}")
    return posts[0]


def code_language(body: str) -> str:
    first = body.strip().split()
    if not first:
        return ""
    tok = first[0].lstrip("$#").strip()
    if tok in SHELL or any(tok.startswith(p) for p in ("eos-", "./", "/usr/", "/etc/")):
        return "bash"
    if tok.startswith("[") or "=" in tok and " " not in tok:
        return "ini"
    return ""


def unwrap_pre(block: str) -> str:
    """Recover the real text of a <pre>, whatever shape it arrived in."""
    inner = re.sub(r"^<pre[^>]*>|</pre>$", "", block.strip())
    # <br> is a line break here, not whitespace. This is the whole problem.
    inner = re.sub(r"<br\s*/?>", "\n", inner, flags=re.I)
    # </code><code> across a line boundary is also a break.
    inner = re.sub(r"</code>\s*<code[^>]*>", "\n", inner, flags=re.I)
    inner = re.sub(r"</?code[^>]*>", "", inner, flags=re.I)
    inner = re.sub(r"<[^>]+>", "", inner)
    return html.unescape(inner).strip("\n").rstrip()


def inline(t: str) -> str:
    """Inline HTML -> Markdown. Order matters: code first, so its content is
    not then treated as markup."""
    t = re.sub(r"<code[^>]*>(.*?)</code>", lambda m: "`" + re.sub(r"<[^>]+>", "", m.group(1)) + "`", t, flags=re.S | re.I)
    t = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"[\2](\1)", t, flags=re.S | re.I)
    t = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", t, flags=re.S | re.I)
    t = re.sub(r"<(em|i)>(.*?)</\1>", r"*\2*", t, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", "  \n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"[ \t]+", " ", t).strip()


def convert(content: str) -> tuple[str, dict]:
    stats = {"code": 0, "lang": 0, "embed": 0, "img": 0, "multiline": 0, "xref": 0}
    out: list[str] = []

    # Articles are inconsistent about where they start: some open at h2, some at
    # h4. Starlight owns h1 and builds the page TOC from what follows, so shift
    # each article so its shallowest heading becomes h2. Without this an article
    # that starts at h4 produces a TOC with no top level.
    levels = [int(m) for m in re.findall(r"<h([1-6])[^>]*>", content, re.I)]
    shift = (min(levels) - 2) if levels else 0

    # Split on top-level blocks, keeping them.
    pattern = re.compile(
        r"(<pre[^>]*>.*?</pre>"
        r"|<figure[^>]*>.*?</figure>"
        r"|<h[1-6][^>]*>.*?</h[1-6]>"
        r"|<[ou]l[^>]*>.*?</[ou]l>"
        r"|<p[^>]*>.*?</p>"
        r"|<div[^>]*wp-block-embed[^>]*>.*?</div>"
        r"|<blockquote[^>]*>.*?</blockquote>)",
        re.S | re.I,
    )

    for block in pattern.findall(content):
        b = block.strip()

        if re.match(r"<pre", b, re.I):
            body = unwrap_pre(b)
            if not body:
                continue
            lang = code_language(body)
            stats["code"] += 1
            if lang:
                stats["lang"] += 1
            if "\n" in body:
                stats["multiline"] += 1
            out.append(f"```{lang}\n{body}\n```")

        elif re.match(r"<h([1-6])", b, re.I):
            lvl = int(re.match(r"<h([1-6])", b, re.I).group(1)) - shift
            lvl = max(2, min(lvl, 5))
            out.append("#" * lvl + " " + inline(b))

        elif "wp-block-embed" in b:
            yt = re.search(r"(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<\"]+)", b)
            if yt:
                stats["embed"] += 1
                out.append(f'<YouTube url="{yt.group(1)}" />')
            else:
                # An embed of another Discovery article. Rendering WordPress's
                # iframe card is pointless once migrated; a plain link is the
                # honest equivalent and survives the move.
                link = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S | re.I)
                if link:
                    stats["xref"] += 1
                    label = re.sub(r"<[^>]+>", "", link.group(2)).strip()
                    out.append(f"[{label or link.group(1)}]({link.group(1)})")

        elif re.match(r"<figure", b, re.I):
            m = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', b, re.I)
            if m:
                alt = re.search(r'alt="([^"]*)"', b, re.I)
                stats["img"] += 1
                out.append(f"![{alt.group(1) if alt else ''}]({m.group(1)})")

        elif re.match(r"<[ou]l", b, re.I):
            ordered = b.lower().startswith("<ol")
            items = re.findall(r"<li[^>]*>(.*?)</li>", b, re.S | re.I)
            for i, it in enumerate(items, 1):
                out.append(f"{i}. {inline(it)}" if ordered else f"- {inline(it)}")
            out.append("")

        elif re.match(r"<blockquote", b, re.I):
            out.append("> " + inline(b))

        else:
            t = inline(b)
            if t:
                out.append(t)

    md = "\n\n".join(x for x in out if x is not None)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n", stats


def main() -> int:
    slugs = sys.argv[1:]
    if not slugs:
        print(__doc__)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    for slug in slugs:
        post = fetch(slug)
        title = html.unescape(re.sub(r"<[^>]+>", "", post["title"]["rendered"]))
        body, st = convert(post["content"]["rendered"])

        # Starlight renders the frontmatter title as the page h1, so an opening
        # heading that just repeats it makes the article say its own name twice.
        norm = lambda x: re.sub(r"[^a-z0-9]+", "", x.lower())
        body = re.sub(
            r"\A#{2,5} (.+?)\n+",
            lambda m: "" if norm(m.group(1)) == norm(title) else m.group(0),
            body,
        )
        needs_youtube = "<YouTube" in body

        fm = [
            "---",
            f'title: "{title}"',
            f'description: "Migrated from discovery.endeavouros.com/{slug}/"',
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
