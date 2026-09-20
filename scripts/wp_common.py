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
     every multi-line shell snippet collapses onto one line -- and they are not
     only in <pre>: a paragraph's <code> carries them too, where the line break
     is all that separates one command from the next.
  3. Nothing carries a language, so code blocks would render unhighlighted.
     Languages are inferred from the first token.

What differs between the two properties is what an embed, an image and a link
should become -- Starlight wants a <YouTube> component, assets in the wiki's
own tree and cross-references rewritten to the new URLs, the news importer
wants downloaded assets -- so those three are callbacks, not policy baked in
here. A fourth, on_gallery, is opt-in: unset, a gallery stays the run of images
it has always been, which is all a Markdown news post can render anyway.
"""

import html
import json
import re
import textwrap
import urllib.request

# First token -> language. Anything unmatched stays unlabelled rather than
# guessing wrong, since a wrong label highlights misleadingly.
SHELL = {
    "sudo", "pacman", "yay", "paru", "systemctl", "cd", "ls", "cp", "mv", "rm",
    "mkdir", "nano", "vim", "echo", "cat", "grep", "chmod", "chown", "curl",
    "wget", "git", "df", "du", "free", "swapon", "swapoff", "mkswap", "btrfs",
    "lsblk", "mount", "umount", "journalctl", "dmesg", "modprobe", "lspci",
    "lsusb", "reboot", "eos-", "mkinitcpio", "grub-mkconfig", "gpg", "sha512sum",
    "firewall-cmd",
}

# Top-level blocks, kept rather than discarded by the split. Lists are not in
# here on purpose: a non-greedy </ul> closes on the first end tag it meets,
# which inside a nested list is the inner one, so every item after it would
# fall outside every pattern and be dropped without a trace. Lists are cut out
# ahead of the split instead, by top_level_lists().
BLOCKS = re.compile(
    r"(<pre[^>]*>.*?</pre>"
    r"|<figure[^>]*>.*?</figure>"
    r"|<h[1-6][^>]*>.*?</h[1-6]>"
    r"|<p[^>]*>.*?</p>"
    r"|<div[^>]*wp-block-embed[^>]*>.*?</div>"
    r"|<blockquote[^>]*>.*?</blockquote>"
    r"|<hr[^>]*>)",
    re.S | re.I,
)

# A gallery, whole. Grouping cannot be left to the <figure> branch of the
# split: a gallery with nested images is a <figure> of <figure>s and the
# non-greedy pattern closes on the first inner </figure>. The Gutenberg comment
# pair is the only boundary that is actually the gallery's.
GALLERY = re.compile(r"<!--\s*wp:(gallery|jetpack/slideshow)\b.*?<!--\s*/wp:\1\s*-->", re.S)

IMG = re.compile(r"<img\b[^>]*>", re.I)
LIST_TAG = re.compile(r"</?[ou]l\b[^>]*>", re.I)
LI_TAG = re.compile(r"</?li\b[^>]*>", re.I)
CODE_EL = re.compile(r"<code[^>]*>(.*?)</code>", re.S | re.I)
BR = re.compile(r"<br\s*/?>", re.I)
# An anchor with no href: not a link, but a place in the page an author wrote
# to be linked to. The export holds none of these as written -- convert() makes
# them out of the ids authors put on paragraphs -- so this only ever matches
# what was hoisted a few lines earlier.
ANCHOR = re.compile(r'<a\s+(?:id|name)="([^"]+)"\s*>\s*</a>', re.I)

# Emphasis is marked with sentinels while the conversion runs and resolved at
# the end, by close_emphasis(). \x02-\x05 are open and close for strong and em;
# the export contains none of them, as text or as an entity.
SENTINELS = {0x02: None, 0x03: None, 0x04: None, 0x05: None}
PAIRED = ((re.compile("\x02([^\x02-\x05]*)\x03"), "**"),
          (re.compile("\x04([^\x02-\x05]*)\x05"), "*"))
# What may not sit between a marker and the text it emphasises. &nbsp; is in
# here because unescaping has already run by then and it is a space to a reader.
EDGE = " \t\n\r\f\v\xa0"


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


def code_text(fragment: str) -> str:
    """The real text of code markup, whatever it is wrapped in."""
    # <br> is a line break here, not whitespace. This is the whole problem.
    fragment = BR.sub("\n", fragment)
    # </code><code> across a line boundary is also a break.
    fragment = re.sub(r"</code>\s*<code[^>]*>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"</?code[^>]*>", "", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(fragment).strip("\n").rstrip()


def unwrap_pre(block: str) -> str:
    """Recover the real text of a <pre>, whatever shape it arrived in."""
    return code_text(re.sub(r"^<pre[^>]*>|</pre>$", "", block.strip()))


def code_block(inner: str) -> str:
    """The text of a <code> that holds two or more lines, empty for the code
    spans that are one line and belong inline."""
    body = code_text(inner)
    return body if len([x for x in body.split("\n") if x.strip()]) > 1 else ""


def code_span(inner: str, stats: dict | None) -> str:
    """One <code> as a span. A span is one line by definition, so a break
    inside it is lost here rather than rendered: count it. blocks() has
    already lifted out the ones written with <br>, so what reaches this is a
    span whose lines were typed as newlines -- which is indistinguishable
    from a sentence the editor wrapped, and is a caller's decision."""
    if stats is not None and code_block(inner):
        stats["fused"] += 1
    return "`" + re.sub(r"<[^>]+>", "", inner) + "`"


def emphasis(body: str, marker: str) -> str:
    """One strong or em element as Markdown, with the whitespace at its edges
    left outside the markers.

    CommonMark will not open emphasis on a space or close on one, so `**text **`
    is not bold: it renders as the four asterisks, in the reader's face. The
    editor's toolbar puts the space inside the element whenever the author
    selected one along with the word, which happened 59 times across 26 of these
    articles, so this is the rule rather than a repair for one page.
    """
    core = body.strip(EDGE)
    if not core:
        # Emphasised whitespace is whitespace; emphasised nothing is nothing.
        return " " if body else ""
    lead, trail = body[:len(body) - len(body.lstrip(EDGE))], body[len(body.rstrip(EDGE)):]
    return f"{lead}{marker}{core}{marker}{trail}"


def close_emphasis(t: str) -> str:
    """The emphasis sentinels turned into markers, innermost element first.

    Innermost first because an outer element's edge is whatever the inner one
    left there: <strong><em>text </em></strong> has to move the space out
    through both, and only the inner pass can see it. The sentinels survive
    the tag strip and the unescaping on purpose -- an element's real edges
    cannot be read while <sub> or &nbsp; is still standing at them.
    """
    while True:
        done = t
        for pattern, marker in PAIRED:
            done = pattern.sub(lambda m: emphasis(m.group(1), marker), done)
        if done == t:
            # What is left is an element whose partner is in another fragment:
            # pieces() splits a paragraph at every image. Half an element is no
            # emphasis at all.
            return t.translate(SENTINELS)
        t = done


def inline(t: str, on_link=None, stats: dict | None = None) -> str:
    """Inline HTML -> Markdown. Order matters: code first, so its content is
    not then treated as markup."""
    t = CODE_EL.sub(lambda m: code_span(m.group(1), stats), t)
    t = re.sub(
        r"<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
        lambda m: link(m.group(1), m.group(2), on_link),
        t, flags=re.S | re.I,
    )
    t = re.sub(r"<(strong|b)>(.*?)</\1>", "\x02\\2\x03", t, flags=re.S | re.I)
    t = re.sub(r"<(em|i)>(.*?)</\1>", "\x04\\2\x05", t, flags=re.S | re.I)
    t = BR.sub("\x06", t)
    # An href-less anchor is a target, not a link, and the tag strip below
    # would take it out with the markup. It travels as a sentinel, like the
    # break above, and is written back once the collapse has run.
    t = ANCHOR.sub("\x07\\1\x07", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = close_emphasis(html.unescape(t))
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub("\x07([^\x07]*)\x07", lambda m: f'<a id="{m.group(1)}"></a>', t)
    # A hard break is two spaces and a newline, and the collapse above reads
    # those two spaces as ordinary whitespace and eats one. So the break
    # travels through as a sentinel and is written last, taking the whitespace
    # the editor left around it with it.
    return re.sub(r"\s*\x06\s*", "  \n", t).strip()


def link(href: str, label: str, on_link) -> str:
    """One <a> as Markdown. on_link may retarget it, or return None to say the
    destination does not survive the move -- in which case the label stays as
    text, rather than becoming a link to nowhere."""
    label = re.sub(r"\s+", " ", label).strip()
    if on_link is None:
        return f"[{label}]({href})"
    target = on_link(html.unescape(href))
    return f"[{label}]({target})" if target else label


def plain_title(post: dict) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", post["title"]["rendered"]))


def default_embed(block: str, stats: dict) -> str | None:
    """An embed card is pointless once migrated; a plain link is the honest
    equivalent and survives the move."""
    anchor = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S | re.I)
    if anchor:
        href = anchor.group(1)
        label = re.sub(r"<[^>]+>", "", anchor.group(2)).strip()
    else:
        # WordPress resolved an embed to a card at render time, so the export
        # holds most of them as a bare URL in the wrapper div with no <a> at
        # all. Reading only for an <a> drops those silently.
        bare = re.search(r"(https?://[^\s<\"]+)", block)
        if not bare:
            return None
        href = label = html.unescape(bare.group(1))
    stats["xref"] += 1
    return f"[{label or href}]({href})"


def default_image(src: str, alt: str, stats: dict) -> str | None:
    stats["img"] += 1
    return f"![{alt}]({src})"


def top_level_lists(content: str) -> list[tuple[int, int]]:
    """The spans of the outermost <ul>/<ol> elements, by counting depth."""
    spans, depth, start = [], 0, 0
    for m in LIST_TAG.finditer(content):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                spans.append((start, m.end()))
        else:
            if depth == 0:
                start = m.start()
            depth += 1
    return spans


def regions(content: str, galleries: bool) -> list[tuple[int, int, bool]]:
    """The spans the block split must not be handed, in source order.

    Top-level lists always, for the reason BLOCKS gives; galleries too when the
    caller asked for them, each flagged so convert() can tell the two apart. A
    Jetpack slideshow is a <ul> inside its own gallery comments, so its list
    span is dropped in favour of the gallery around it -- kept, the same images
    would be emitted twice.
    """
    spans = [(a, b, False) for a, b in top_level_lists(content)]
    if not galleries:
        return spans
    found = [(m.start(), m.end(), True) for m in GALLERY.finditer(content)]
    return sorted(found + [(a, b, k) for a, b, k in spans
                           if not any(g <= a and b <= h for g, h, _ in found)])


def list_items(block: str) -> list[str]:
    """The immediate <li> children of a list, nested lists left inside them."""
    items, depth, start = [], 0, 0
    for m in LI_TAG.finditer(block):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                items.append(block[start:m.start()])
        else:
            if depth == 0:
                start = m.end()
            depth += 1
    return items


def render_list(block: str, on_image, on_link, stats: dict, indent: int = 0) -> list[str]:
    """A list, its nested lists indented under the item they belong to."""
    ordered = re.match(r"\s*<ol\b", block, re.I) is not None
    lines, n = [], 0
    for item in list_items(block):
        spans = top_level_lists(item)
        nested = [item[a:b] for a, b in spans]
        own = "".join(item[e:s] for (_, e), (s, _) in zip([(0, 0)] + spans, spans + [(len(item), 0)]))
        text = " ".join(pieces(own, on_image, on_link, stats))
        if not text and not nested:
            continue
        n += 1
        marker = f"{n}. " if ordered else "- "
        lines.append(" " * indent + marker + text)
        for sub in nested:
            lines.extend(render_list(sub, on_image, on_link, stats, indent + len(marker)))
    return lines


def pieces(fragment: str, on_image, on_link, stats: dict) -> list[str]:
    """Text and images of one fragment, in source order.

    Images are not only in <figure>. A Markdown block renders them inside a
    <p>, a slideshow puts them in <li>, and inline() strips every tag it does
    not recognise, so without this those images vanish without a trace.
    """
    found, last = [], 0
    for m in IMG.finditer(fragment):
        text = inline(fragment[last:m.start()], on_link, stats)
        if text:
            found.append(text)
        src = re.search(r'\ssrc="([^"]+)"', m.group(0), re.I)
        alt = re.search(r'\salt="([^"]*)"', m.group(0), re.I)
        if src:
            piece = on_image(html.unescape(src.group(1)), html.unescape(alt.group(1)) if alt else "", stats)
            if piece:
                found.append(piece)
        last = m.end()
    text = inline(fragment[last:], on_link, stats)
    if text:
        found.append(text)
    return found


def blocks(fragment: str, on_image, on_link, stats: dict) -> list[str]:
    """One paragraph, with any code element that spans lines lifted out of it
    as a fenced block.

    Gutenberg has no block-level code inside a paragraph, so an author with
    three commands to give typed them into one <code> and separated them with
    <br>. A code span cannot hold a line break, so flattening one of these
    joins the commands into a single line that runs something else -- the
    samba article fused six of them, and a reader copies what is on the page.
    """

    def prose(part: str) -> list[str]:
        # A paragraph opening with a root prompt would be read as a heading.
        # WordPress rendered it as the prose it is.
        return [re.sub(r"\A#", r"\\#", x) for x in pieces(part, on_image, on_link, stats)]

    out, last = [], 0
    for m in CODE_EL.finditer(fragment):
        # <br> only: a newline inside a <code> is as often the editor wrapping
        # a long line as it is the author ending one.
        if not BR.search(m.group(1)):
            continue
        body = code_block(m.group(1))
        if not body:
            continue
        out += prose(fragment[last:m.start()])
        lang = code_language(body)
        stats["code"] += 1
        stats["multiline"] += 1
        if lang:
            stats["lang"] += 1
        out.append(f"```{lang}\n{body}\n```")
        last = m.end()
    return out + prose(fragment[last:])


def markdown_table(block: str, on_link, stats: dict) -> str:
    """<figure class="wp-block-table"> -> a Markdown table.

    Nine articles carry 26 of these and every one was dropped before, because
    a <figure> was only ever read for its first <img>. Fifteen hold a single
    cell of man-page output, which is a code block wearing a table's clothes;
    the rest are real tables, with a header row that WordPress writes as a
    <thead> in some and as a <tr> of <th> in others -- either way it is the
    first row, which is the only place Markdown can put it.
    """
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S | re.I):
        rows.append([cell(c, on_link, stats) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)])
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""

    if len(rows) == 1 and len(rows[0]) == 1:
        one = re.search(r"<t[dh][^>]*>(.*?)</t[dh]>", block, re.S | re.I).group(1)
        one = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", one, flags=re.I)))
        # The editor indented the whole cell; the alignment inside it is the
        # part that carries meaning, so only the shared indent comes off.
        one = textwrap.dedent("\n".join(x.rstrip() for x in one.split("\n"))).strip("\n")
        return f"```\n{one}\n```" if one.strip() else ""

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return "\n".join(
        ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
        + ["| " + " | ".join(r) + " |" for r in rows[1:]]
    )


def cell(text: str, on_link, stats: dict) -> str:
    """One table cell. A line break has to stay HTML -- a newline would end the
    row -- and a pipe has to be escaped or it would start a column."""
    text = BR.sub("\x00", text)
    return inline(text, on_link, stats).replace("|", r"\|").replace("\x00", "<br />")


def unwrap_html_blocks(content: str) -> str:
    """<!-- wp:html --> is whatever the author pasted into it, and in both of
    Discovery's it is a heading followed by loose prose inside a stray <html>
    element. The split would find the heading and drop the prose, which is
    most of the block."""

    def rewrite(m: re.Match) -> str:
        inner = re.sub(r"</?html[^>]*>", "", m.group(1)).strip()
        heads = re.findall(r"<h[1-6][^>]*>.*?</h[1-6]>", inner, re.S | re.I)
        rest = re.sub(r"<h[1-6][^>]*>.*?</h[1-6]>", "", inner, flags=re.S | re.I).strip()
        return "\n".join(heads) + (f"\n<p>{rest}</p>" if rest else "")

    return re.sub(r"<!--\s*wp:html\s*-->(.*?)<!--\s*/wp:html\s*-->", rewrite, content, flags=re.S)


def convert(content: str, on_embed=default_embed, on_image=default_image, on_link=None,
            on_gallery=None) -> tuple[str, dict]:
    stats = {"code": 0, "lang": 0, "embed": 0, "fused": 0, "gallery": 0, "img": 0,
             "multiline": 0, "xref": 0, "table": 0}
    out: list[str] = []

    content = unwrap_html_blocks(content)

    # Articles are inconsistent about where they start: some open at h2, some at
    # h4. The page title is rendered from frontmatter and the TOC is built from
    # what follows, so shift each article so its shallowest heading becomes h2.
    # Without this an article that starts at h4 produces a TOC with no top level.
    levels = [int(m) for m in re.findall(r"<h([1-6])[^>]*>", content, re.I)]
    shift = (min(levels) - 2) if levels else 0

    def emit(region: str) -> None:
        for block in BLOCKS.findall(region):
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
                text = inline(b, on_link, stats)
                if not text:
                    continue          # an empty heading is a Gutenberg spacer
                lvl = int(re.match(r"<h([1-6])", b, re.I).group(1)) - shift
                out.append("#" * max(2, min(lvl, 5)) + " " + text)

            elif "wp-block-embed" in b:
                piece = on_embed(b, stats)
                if piece:
                    out.append(piece)

            elif re.match(r"<figure", b, re.I):
                if "wp-block-table" in b:
                    table = markdown_table(b, on_link, stats)
                    if table:
                        stats["table"] += 1
                        out.append(table)
                else:
                    # A gallery is one <figure> holding several <img>; reading
                    # only the first would drop the rest of the gallery.
                    out.extend(pieces(b, on_image, on_link, stats))

            elif re.match(r"<blockquote", b, re.I):
                out.append("> " + inline(b, on_link, stats))

            elif re.match(r"<hr", b, re.I):
                # Authors used the separator block to divide sections that
                # have no heading of their own. Dropping it runs them together.
                out.append("---")

            else:
                # An id an author put on a paragraph is a place in the page
                # something links to -- the Nvidia table links the RTD3 note
                # under it that way. The <p> itself does not survive the
                # conversion, so the id is hoisted into the text as an anchor
                # of its own and lands at the start of the paragraph. The
                # block- ids are Gutenberg's own uuids, which name nothing.
                opening = re.match(r'<p[^>]*\sid="([^"]+)"[^>]*>', b, re.I)
                if opening and not opening.group(1).startswith("block-"):
                    b = (b[:opening.end()] + f'<a id="{opening.group(1)}"></a>'
                         + b[opening.end():])
                out.extend(blocks(b, on_image, on_link, stats))

    last = 0
    for a, b, gallery in regions(content, on_gallery is not None):
        emit(content[last:a])
        region = content[a:b]
        if gallery:
            # The whole region through pieces(), which is also what recovers a
            # gallery's <figcaption>: it is neither an <img> nor a block the
            # split keeps, so until now it was dropped without a trace.
            stats["gallery"] += 1
            piece = on_gallery(pieces(region, on_image, on_link, stats), stats)
            if piece:
                out.append(piece)
        elif "jetpack-slideshow" in region:
            # A slideshow is a <ul> of slides, each holding an image and
            # nothing else. There is no carousel on the wiki, so it becomes
            # what it always was underneath: a run of images.
            out.extend(pieces(region, on_image, on_link, stats))
        else:
            rendered = render_list(region, on_image, on_link, stats)
            if rendered:
                out.append("\n".join(rendered))
        last = b
    emit(content[last:])

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
