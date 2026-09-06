#!/usr/bin/env python3
"""Shared WordPress -> Markdown conversion, used by both properties.

This file is a copy of scripts/wp_common.py in the main site's repository,
github.com/endeavouros-team/endeavouros.com. The two are kept identical by
hand, so a Gutenberg fix made in one has to be applied to the other.

Discovery's wiki articles and the main site's news posts come out of the same
Gutenberg editor and share the same three problems, so the block splitting,
the <pre> unwrapping and the inline conversion live here rather than being
written twice:

  1. Code blocks come in three shapes, not one:
         <pre class="wp-block-code"><code>one line</code></pre>
         <pre class="wp-block-preformatted">no code element at all<br></pre>
         <pre><code><code>nested</code><br><code>code elements</code></code></pre>
  2. Multi-line commands are joined with <br>, not newlines. Convert naively and
     every multi-line shell snippet collapses onto one line.
  3. Nothing carries a language, so code blocks would render unhighlighted.
     Languages are inferred from the first token.

What differs between the two properties is what an embed and an image should
become -- Starlight wants a <YouTube> component and a hotlinked image, the news
importer wants downloaded assets -- so those two are callbacks, not policy
baked in here.
"""

import html
import json
import re
import urllib.request

# First token -> language. Anything unmatched stays unlabelled rather than
# guessing wrong, since a wrong label highlights misleadingly.
SHELL = {
    "sudo", "pacman", "yay", "paru", "systemctl", "cd", "ls", "cp", "mv", "rm",
    "mkdir", "nano", "vim", "echo", "cat", "grep", "chmod", "chown", "curl",
    "wget", "git", "df", "du", "free", "swapon", "swapoff", "mkswap", "btrfs",
    "lsblk", "mount", "umount", "journalctl", "dmesg", "modprobe", "lspci",
    "lsusb", "reboot", "eos-", "mkinitcpio", "grub-mkconfig", "gpg", "sha512sum",
}

# Top-level blocks, kept rather than discarded by the split.
BLOCKS = re.compile(
    r"(<pre[^>]*>.*?</pre>"
    r"|<figure[^>]*>.*?</figure>"
    r"|<h[1-6][^>]*>.*?</h[1-6]>"
    r"|<[ou]l[^>]*>.*?</[ou]l>"
    r"|<p[^>]*>.*?</p>"
    r"|<div[^>]*wp-block-embed[^>]*>.*?</div>"
    r"|<blockquote[^>]*>.*?</blockquote>)",
    re.S | re.I,
)


def fetch(api: str, slug: str, fields: str) -> dict:
    """One post by slug from a WordPress REST API."""
    url = f"{api}/posts?slug={slug}&_fields={fields}"
    with urllib.request.urlopen(url, timeout=60) as r:
        posts = json.load(r)
    if not posts:
        raise SystemExit(f"  no post found for slug {slug!r} at {api}")
    return posts[0]


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


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


def plain_title(post: dict) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", post["title"]["rendered"]))


def default_embed(block: str, stats: dict) -> str | None:
    """An embed card is pointless once migrated; a plain link is the honest
    equivalent and survives the move."""
    link = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S | re.I)
    if not link:
        return None
    stats["xref"] += 1
    label = re.sub(r"<[^>]+>", "", link.group(2)).strip()
    return f"[{label or link.group(1)}]({link.group(1)})"


def default_image(src: str, alt: str, stats: dict) -> str | None:
    stats["img"] += 1
    return f"![{alt}]({src})"


def convert(content: str, on_embed=default_embed, on_image=default_image) -> tuple[str, dict]:
    stats = {"code": 0, "lang": 0, "embed": 0, "img": 0, "multiline": 0, "xref": 0}
    out: list[str] = []

    # Articles are inconsistent about where they start: some open at h2, some at
    # h4. The page title is rendered from frontmatter and the TOC is built from
    # what follows, so shift each article so its shallowest heading becomes h2.
    # Without this an article that starts at h4 produces a TOC with no top level.
    levels = [int(m) for m in re.findall(r"<h([1-6])[^>]*>", content, re.I)]
    shift = (min(levels) - 2) if levels else 0

    for block in BLOCKS.findall(content):
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
            piece = on_embed(b, stats)
            if piece:
                out.append(piece)

        elif re.match(r"<figure", b, re.I):
            m = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', b, re.I)
            if m:
                alt = re.search(r'alt="([^"]*)"', b, re.I)
                piece = on_image(m.group(1), alt.group(1) if alt else "", stats)
                if piece:
                    out.append(piece)

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


def strip_repeated_title(body: str, title: str) -> str:
    """The frontmatter title is rendered as the page h1, so an opening heading
    that just repeats it makes the article say its own name twice."""
    norm = lambda x: re.sub(r"[^a-z0-9]+", "", x.lower())
    return re.sub(
        r"\A#{2,5} (.+?)\n+",
        lambda m: "" if norm(m.group(1)) == norm(title) else m.group(0),
        body,
    )


def synth_description(body: str, title: str) -> str:
    """What search engines and link previews show, so it has to read like the
    article, not like a note about the migration. First real sentence of prose,
    trimmed to a sane length."""
    first = ""
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith(("#", "`", "-", ">", "!", "import ", "<", "|")):
            continue
        if re.match(r"^\d+[.)]\s", line):        # ordered list item
            continue
        cand = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)      # unwrap links
        cand = re.sub(r"[*`_]", "", cand).strip()
        # Skip bylines and sentence fragments that introduce a list; neither
        # describes the article to someone reading a search result.
        if re.match(r"(?i)^(by |edited by|written by)", cand):
            continue
        if cand.endswith(":") or len(cand) < 45:
            continue
        first = cand
        break
    if len(first) > 155:
        cut = first[:155].rsplit(" ", 1)[0]
        first = cut.rstrip(",;:") + "..."
    return first.replace('"', "'") or title
