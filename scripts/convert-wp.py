#!/usr/bin/env python3
"""Convert Discovery's WordPress articles to Starlight Markdown.

The source is the WordPress export (WXR) plus the uploads backup, not the live
site: discovery.endeavouros.com has been a 503 since before the export was
taken. The REST path is kept because it is one branch, not because it works.

    scripts/convert-wp.py --wxr ~/Documents/code/discovery-export/posts-discovery.WordPress.2026-09-06.xml \
        --uploads ~/Documents/code/discovery-export/backup_2026-09-06-1841_Discovery_66fa0c6f4f7d-uploads.zip

Every published post is converted; naming slugs converts only those. Drafts and
private posts are read but never written -- they still have to be parsed,
because a published article may link to one and that link cannot survive.

The export stays outside every repository: it carries drafts, private posts and
author email addresses. Only the images this script pulls out of the uploads
backup are committed, under astro/src/assets/articles/<slug>/.

The Gutenberg handling -- the three <pre> shapes, <br>-joined commands, language
inference, heading shifting, lists, tables -- lives in the sibling
scripts/wp_common.py, a hand-kept copy of the main site's file of the same name.
What stays here is what is Discovery's alone: .mdx output, the <YouTube>
component, resolving every image to a file in this repository, and rewriting the
links and anchors that used to point at WordPress.

astro/sidebar.json is hand-authored and this script never writes it. A run
checks it instead, and says so in the warning list: an article nobody filed, a
slug filed twice, a slug whose article is gone.
"""

import argparse
import html
import json
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import wp_common as wp

API = "https://discovery.endeavouros.com/wp-json/wp/v2"
FIELDS = "slug,title,content,date,modified,categories"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "astro/src/content/docs"
ASSETS = ROOT / "astro/src/assets/articles"
SIDEBAR = ROOT / "astro/sidebar.json"

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

# The Gutenberg block delimiters, for CUT: an opener, a closer, or a
# self-closing block, told apart by the two groups.
BLOCK_COMMENT = re.compile(r"<!--\s*(/?)wp:(.*?)-->", re.S)
BLOCK_CLOSE = re.compile(r"<!--\s*/wp:.*?-->", re.S)

HOST = "discovery.endeavouros.com"
# The `id_` suffix asks the Wayback Machine for the file as archived, without
# its own banner and rewritten links.
WAYBACK = "https://web.archive.org/web/2026id_/"
UA = {"User-Agent": "eos-wiki-import"}

# The Font Awesome plugin rendered these; the export keeps the shortcode. A
# glyph says the same thing without a plugin, an icon font or a web request.
ICONS = {
    "check": "✓",
    "exclamation": "⚠",
    "exclamation-triangle": "⚠",
    "caret-square-down": "▾",
    "cog": "⚙",
    "book": "\U0001f4d6",
    "book-open": "\U0001f4d6",
    "book-reader": "\U0001f4d6",
    "info": "ℹ",
    "lightbulb": "\U0001f4a1",
    "mouse": "\U0001f5b1",
    "flag": "⚑",
    "share": "↗",
    "plus": "+",
    "times": "×",
    # Escaped: the one of these sits at the start of the RTD3 note in
    # nvidia-intro, where a bare asterisk and a space is a list marker and
    # renders the note as a one-item bullet list it was never meant to be.
    "asterisk": "\\*",
}

# Published in the export, but not on the wiki. The export is a snapshot of a
# WordPress install nobody is tending any more, so `publish` is not always the
# intent -- and the fix cannot be to delete the .mdx, which the next run would
# write straight back.
SKIP = {
    "firewall": "ufw, superseded by firewalld; Joe meant to make it private",
    # The Video Tutorials group: eight pages of embedded videos, most of them
    # years out of date. Bryanpwo asked whether they should come across at all
    # and joekamprad agreed they should not, forum 2026-09-08. The nine other
    # articles that embed a video inline keep it, so <YouTube> stays.
    "back-up": "video tutorials retired, forum decision 2026-09-08",
    "fix-arch-linux-boot-with-arch-chroot": "video tutorials retired, forum decision 2026-09-08",
    "general-linux-tutorials": "video tutorials retired, forum decision 2026-09-08",
    "gui-applications": "video tutorials retired, forum decision 2026-09-08",
    "install-endeavouros": "video tutorials retired, forum decision 2026-09-08",
    "joekamprad-video-tutorials": "video tutorials retired, forum decision 2026-09-08",
    "maintenance": "video tutorials retired, forum decision 2026-09-08",
    "pacman-aur-tutorials": "video tutorials retired, forum decision 2026-09-08",
}

# Text an article kept about something that is not on the wiki. Two verbatim
# substrings of the source bracket the removal; the span grows outward to the
# Gutenberg block comments around them, because half a block is not something
# the split can read. It is source surgery for the same reason SKIP is not a
# deleted file: the next run would write the removed text straight back.
CUT = {
    "nvidia-optimus-notebooks-hybrid-graphics": [
        ("the EnvyControl entry -- that article is private and stays so, forum 2026-09-08",
         "<strong>EnvyControl is a CLI tool", ">Envy-Control</a>"),
    ],
    "new-nvidia-driver-installer-nvidia-inst": [
        ("the Bumblebee section -- that article is private and stays so, forum 2026-09-08",
         '<h4 class="wp-block-heading">Bumblebee (for very old machines)</h4>',
         "<p><code>nvidia-inst -b</code></p>"),
    ],
    "arch-chroot": [
        ("the video tutorial bullet -- its link text is the dead URL itself, so "
         "dissolving the link would leave the URL standing there as prose",
         "<li>Video tutorial about arch-chroot:",
         "fix-arch-linux-boot-with-arch-chroot/2021/12/</a></li>"),
    ],
}

# Markup an author left broken, repaired in the source before anything reads
# it. Unlike CUT, which removes text about a page that is not here, this is for
# a link or a tag that never worked on WordPress either -- so the repair is what
# the author meant, not an editorial change. Verbatim substrings, replaced once.
PATCH = {
    "nvidia-intro": [
        ("the N of \"No RTD3\" was a second link of its own, to an anchor that "
         "has never existed, so the phrase read \"o RTD3\" with the N dangling "
         "outside it -- dalto on the forum, 2026-09-20",
         '<a href="#no_RTD3_issue">N</a><a href="#no_rtd3" data-type="internal" data-id="#no_rtd3">o RTD3',
         '<a href="#no_rtd3" data-type="internal" data-id="#no_rtd3">No RTD3'),
    ],
}

# Articles the export escaped twice. The editor stores a <pre> escaped once,
# and these went through that a second time, so `&&` sits in the XML as
# `&amp;amp;&amp;amp;` and the converter's single, correct unescape leaves
# `&amp;&amp;` standing in the fence. A reader copying that script runs nothing.
# Per article rather than site-wide: one unescape too many on an article that
# was only escaped once would eat text the author typed.
DOUBLE_ESCAPED = {
    "steam-lutris-wine": "the two bash scripts, which carry &amp;amp; for && and &amp;gt; for >",
}

# The entities the export uses, as a lookahead for the extra escape in front of
# one and as the class gate on what comes out.
ENTITIES = r"(?:amp|lt|gt|quot|apos|nbsp|#\d+|#x[0-9a-fA-F]+);"
ENTITY = re.compile("&" + ENTITIES)
DOUBLED = re.compile("&amp;(?=" + ENTITIES + ")")

# Articles that keep their text but lose their featured image. The picture is
# the problem, not the article, so this is separate from SKIP.
NO_COVER = {
    "pacman-basic-commands": "watermarked stock image",
}

# Images that are still published, at a different address. A prefix rewrite
# rather than a per-URL map, because what moved was a directory: the Welcome
# app left the PKGBUILDS monorepo for its own repository and took its
# wiki-pictures with it. manuel named the new home on the forum, 2026-09-08.
MOVED = {
    "https://raw.githubusercontent.com/endeavouros-team/PKGBUILDS/master/welcome/wiki-pictures/":
        "https://raw.githubusercontent.com/endeavouros-team/welcome/main/wiki-pictures/",
}

# The width <Image> is asked to render, not the width of the file: store()
# commits the original bytes whatever their size. Twice the 720px content
# column, for a 2x display. A cover narrower than this is asked for its own
# width instead, because asking for more makes Astro write attributes for an
# upscale it does not perform.
COVER_MAX = 1440

posts: dict[str, dict] = {}       # slug -> record, whatever its status
old_slugs: dict[str, dict] = {}   # a slug WordPress renamed -> the post that carries it now
by_id: dict[str, dict] = {}
attachments: dict[str, str] = {}  # attachment slug -> file URL
att_urls: dict[str, str] = {}     # attachment post id -> file URL, for _thumbnail_id
uploads: zipfile.ZipFile | None = None
assets: dict[tuple[str, str], str] = {}
gallery_imports: list[tuple[str, str]] = []   # name, path: one article's gallery images
here = ""                         # the article being converted, for warnings
warnings: list[str] = []


def warn(kind: str, detail: str) -> None:
    warnings.append(f"{kind:10s} {here or '-':52s} {detail}")


# --- the export -------------------------------------------------------------


def meta(item: ET.Element, key: str) -> str:
    """One <wp:postmeta> value, by key."""
    for m in item.findall("wp:postmeta", namespaces=NS):
        if m.findtext("wp:meta_key", namespaces=NS) == key:
            return m.findtext("wp:meta_value", namespaces=NS) or ""
    return ""


def block_depth(span: str) -> int:
    """Gutenberg blocks opened in a span, less the ones closed in it. A
    self-closing block -- `<!-- wp:spacer {…} /-->` -- opens nothing."""
    depth = 0
    for m in BLOCK_COMMENT.finditer(span):
        if m.group(1):
            depth -= 1
        elif not m.group(2).rstrip().endswith("/"):
            depth += 1
    return depth


def cut(slug: str, body: str) -> str:
    """The CUT spans, taken out of the source before anything else reads it.

    Every failure here is fatal rather than a warning. An anchor that stops
    matching means the export moved under the dict, and the article would then
    quietly go back to carrying the text the dict exists to remove.
    """
    for reason, first, last in CUT.get(slug, []):
        for anchor in (first, last):
            if body.count(anchor) != 1:
                raise SystemExit(
                    f"  {slug}: {body.count(anchor)} matches for the cut anchor "
                    f"{anchor!r} -- {reason}")
        opens, closes = body.index(first), body.index(last)
        if closes < opens:
            # Left to run backwards, the span is an empty slice, which balances
            # like any other; the removal would then write the text between the
            # two anchors into the article a second time.
            raise SystemExit(f"  {slug}: the cut anchors are the wrong way round -- {reason}")
        start = body.rfind("<!-- wp:", 0, opens)
        end = BLOCK_CLOSE.search(body, closes + len(last))
        if start < 0 or not end:
            raise SystemExit(f"  {slug}: the cut span reaches past the post -- {reason}")
        if block_depth(body[start:end.end()]):
            raise SystemExit(f"  {slug}: the cut span would leave a block open -- {reason}")
        body = body[:start] + body[end.end():]
    return body


def patch(slug: str, body: str) -> str:
    """The PATCH replacements, made in the source before anything reads it.

    Fatal when an entry stops matching, for the reason cut() is fatal: an
    anchor that no longer occurs means the export moved under the dict, and
    the article would quietly go back to carrying the markup being repaired.
    Unique rather than first-match, so a second occurrence is a question for a
    person rather than a silent half-repair.
    """
    for reason, old, new in PATCH.get(slug, []):
        if body.count(old) != 1:
            raise SystemExit(
                f"  {slug}: {body.count(old)} matches for the patch anchor "
                f"{old!r} -- {reason}")
        body = body.replace(old, new)
    return body


def unescape_twice(slug: str, body: str) -> str:
    """The extra escape taken off a DOUBLE_ESCAPED article's <pre> blocks.

    Only inside a <pre>: everywhere else the export is escaped once, and prose
    that reads `&amp;` means an ampersand. Fatal when it changes nothing, for
    the reason CUT is fatal -- an entry that has stopped matching would let the
    article go quietly back to shipping a script nobody can run.
    """
    if slug not in DOUBLE_ESCAPED:
        return body
    fixed = re.sub(r"<pre[^>]*>.*?</pre>", lambda m: DOUBLED.sub("&", m.group(0)),
                   body, flags=re.S | re.I)
    if fixed == body:
        raise SystemExit(
            f"  {slug}: nothing in its code blocks is escaped twice -- {DOUBLE_ESCAPED[slug]}")
    return fixed


def check_entities(body: str) -> None:
    """An entity left in a fenced block is escaping that reached the page.

    The converter unescapes once, which is right for an export escaped once, so
    anything still spelled `&gt;` in a code block came in escaped twice and is
    a DOUBLE_ESCAPED entry waiting to be written. One warning per block: the
    two scripts in steam-lutris-wine held six between them.
    """
    for fence in re.findall(r"```.*?```", body, re.S):
        hit = ENTITY.search(fence)
        if hit:
            warn("entity", f"{hit.group(0)} in a code block -- escaped twice in the export?")


def read_wxr(path: Path) -> None:
    """Every post in the export, published or not."""
    for item in ET.parse(path).getroot().find("channel").findall("item"):
        kind = item.findtext("wp:post_type", namespaces=NS)
        if kind == "attachment":
            url = item.findtext("wp:attachment_url", namespaces=NS) or ""
            attachments[item.findtext("wp:post_name", namespaces=NS)] = url
            att_urls[item.findtext("wp:post_id", namespaces=NS)] = url
            continue
        if kind != "post":
            continue
        slug = item.findtext("wp:post_name", namespaces=NS)
        # Before the anchors are read off it: a cut heading that still had an
        # entry in the anchor map would go on answering cross-page links, and
        # check-links cannot see an anchor that resolves to a heading nobody
        # writes any more.
        body = unescape_twice(
            slug, patch(slug, cut(slug, item.findtext("content:encoded", namespaces=NS) or "")))
        rec = {
            "slug": slug,
            "id": item.findtext("wp:post_id", namespaces=NS),
            "title": html.unescape(item.findtext("title") or ""),
            # The honest age signal. post_date is when it was first published,
            # which for a wiki says nothing: Timeshift is dated 2019 and was
            # last edited in 2022.
            "modified": (item.findtext("wp:post_modified_gmt", namespaces=NS) or "")[:10],
            # The featured image, by attachment id. WordPress's theme showed it
            # above the title and the export keeps only the pointer.
            "thumb": meta(item, "_thumbnail_id"),
            "status": item.findtext("wp:status", namespaces=NS),
            "body": body,
            "anchors": anchor_map(body),
        }
        posts[rec["slug"]] = rec
        by_id[rec["id"]] = rec
        # Every slug this article has been filed under before. WordPress writes
        # one `_wp_old_slug` row per rename and went on serving the old
        # permalink with a redirect of its own, so a link naming one reached
        # this article for as long as the wiki was up. meta() would read the
        # first row only.
        for m in item.findall("wp:postmeta", namespaces=NS):
            if m.findtext("wp:meta_key", namespaces=NS) == "_wp_old_slug":
                old_slugs[m.findtext("wp:meta_value", namespaces=NS) or ""] = rec

    # A renamed slug that another post has since taken as its own would make a
    # link naming it ambiguous, and WordPress would have answered it with the
    # live post. Fatal rather than guessed at: the export has none of these.
    for old, rec in old_slugs.items():
        if old in posts and posts[old] is not rec:
            raise SystemExit(
                f"  {old!r} is both {rec['slug']}'s old slug and {posts[old]['slug']}'s "
                "live one, so a link naming it could mean either")


def read_media(path: Path) -> None:
    """The media export, for attachment pages linked by name.

    No published article links one -- /home/attachment/<name>/ appears in this
    export only as an attachment's own <link> -- so this resolves a shape
    WordPress has rather than one Discovery used.
    """
    for item in ET.parse(path).getroot().find("channel").findall("item"):
        if item.findtext("wp:post_type", namespaces=NS) == "attachment":
            url = item.findtext("wp:attachment_url", namespaces=NS) or ""
            attachments[item.findtext("wp:post_name", namespaces=NS)] = url
            att_urls[item.findtext("wp:post_id", namespaces=NS)] = url


# --- anchors ----------------------------------------------------------------


def slugify(text: str) -> str:
    """Starlight's heading ids, which come from github-slugger: the text,
    lowercased, stripped of punctuation, spaces turned into hyphens."""
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ").strip().lower()
    return re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", text, flags=re.U))


def anchor_map(body: str) -> tuple[dict[str, str], set[str]]:
    """WordPress id -> the id Starlight renders, and every id it renders.

    No old anchor survives untouched: WordPress ids were authored by hand, or
    prefixed with `heading--` by a plugin at render time, while Starlight
    derives them from the heading text. `#heading--requirements` and
    `#--sample-rate` are both dead links after the move.

    An id on a paragraph is the exception, and maps to itself: the converter
    hoists it into the text as an <a id>, which reaches the page as written,
    so nothing regenerates it the way Starlight regenerates a heading's.
    """
    ids: dict[str, str] = {}
    slugs: set[str] = set()
    used: dict[str, int] = {}
    for m in re.finditer(r"<h[1-6]([^>]*)>(.*?)</h[1-6]>", body, re.S | re.I):
        base = slugify(m.group(2))
        n = used.get(base, 0)
        used[base] = n + 1
        slug = base if not n else f"{base}-{n}"
        slugs.add(slug)
        # The id is on the heading in some articles and on an <a> inside it in
        # others; either way it is what the old links point at.
        for raw in re.findall(r'id="([^"]+)"', m.group(1) + m.group(2)):
            ids.setdefault(raw, slug)
    # The authored paragraph ids, verbatim. `block-<uuid>` is Gutenberg's own
    # and names nothing a link could have meant.
    for raw in re.findall(r'<p[^>]*\sid="([^"]+)"', body, re.I):
        if not raw.startswith("block-"):
            ids.setdefault(raw, raw)
    return ids, slugs


def anchor(rec: dict, frag: str) -> str | None:
    ids, slugs = rec["anchors"]
    stripped = frag[len("heading--"):] if frag.startswith("heading--") else None
    for cand in (frag, stripped, "heading--" + frag):
        if cand and cand in ids:
            return ids[cand]
    # An article whose anchors were never given ids at all still often names
    # the heading it means, in one spelling or another.
    for cand in (slugify(frag), slugify(frag.replace("_", " ").replace("-", " "))):
        if cand in slugs:
            return cand
    return None


# --- links ------------------------------------------------------------------


def target(href: str) -> str | None:
    """Where a WordPress link points now, or None if nowhere it can.

    None makes wp_common keep the label as plain text. A link into a site that
    is gone is worse than no link, and the reader can still see what the author
    was pointing at.
    """
    href = href.replace("&amp;", "&")
    u = urllib.parse.urlsplit(href)

    if not u.netloc:
        if not href.startswith("#") or here not in posts:
            return href
        found = anchor(posts[here], href[1:])
        if not found:
            warn("anchor", f"{href}  (no heading of that name)")
            return None
        return "#" + found

    if u.netloc != HOST:
        return href

    if u.query.startswith("s="):
        # Search was a WordPress page. Starlight's is a client-side widget with
        # no URL to send anyone to.
        warn("search", href)
        return None

    if "/wp-admin/" in u.path:
        # An edit URL published inside article text. The post id is the target
        # when the post still exists; when it does not -- one was deleted after
        # the link was written -- the fragment still names exactly one article,
        # because these anchors were unique across the wiki.
        rec = by_id.get(urllib.parse.parse_qs(u.query).get("post", [""])[0])
        if not rec and u.fragment:
            named = [r for r in posts.values() if anchor(r, u.fragment)]
            rec = named[0] if len(named) == 1 else None
        if not rec:
            warn("wp-admin", href)
            return None
        return internal(rec, u.fragment, href)

    if u.path.startswith("/home/attachment/"):
        name = u.path.strip("/").split("/")[-1]
        if name not in attachments:
            warn("attachment", href)
            return None
        return image(attachments[name], "", {"img": 0})

    if "/wp-content/uploads/" in u.path:
        # Always wrapped around the image it links to, as WordPress's "link to
        # media file". The image is on the page; a separate full-size copy is
        # not something this site publishes.
        warn("upload", href)
        return None

    if u.path.startswith("/category/"):
        warn("category", href)
        return None

    for seg in u.path.strip("/").split("/"):
        # A slug WordPress renamed is tried after the live ones: it is what the
        # reader actually got, because WordPress redirected the old permalink
        # itself rather than 404ing it.
        rec = posts.get(seg.lower()) or old_slugs.get(seg.lower())
        if rec:
            return internal(rec, u.fragment, href)
    warn("unknown", href)
    return None


def internal(rec: dict, frag: str, href: str) -> str | None:
    if rec["slug"] in SKIP:
        # A SKIPped article is as absent as an unpublished one. Reading only
        # the status let a link to one survive the move and go dead on a wiki
        # that no longer has the page.
        warn("skipped", f"{href}  -> {rec['slug']}")
        return None
    if rec["status"] != "publish":
        warn(rec["status"], f"{href}  -> {rec['slug']}")
        return None
    if not frag:
        return f"/{rec['slug']}/"
    found = anchor(rec, frag)
    if not found:
        warn("anchor", f"{href}  (no heading of that name in {rec['slug']})")
        return f"/{rec['slug']}/"
    return f"/{rec['slug']}/#{found}"


# --- images -----------------------------------------------------------------


def unjetpack(url: str) -> str:
    """i0.wp.com/endeavouros.com/wp-content/...?resize=650%2C366&ssl=1 is a CDN
    wrapper around a resized copy. Recover the original."""
    url = html.unescape(url)
    u = urllib.parse.urlsplit(url)
    if re.fullmatch(r"i\d\.wp\.com", u.netloc):
        return "https://" + u.path.lstrip("/")
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, "", ""))


def moved(url: str) -> str:
    """A MOVED prefix applied. Takes an already-unwrapped URL: two of the three
    Welcome screenshots reach the export through Jetpack's CDN, so the prefix
    to match is only there once unjetpack() has run."""
    for old, new in MOVED.items():
        if url.startswith(old):
            return new + url[len(old):]
    return url


def get(url: str) -> bytes | None:
    """One file, retried: the Wayback Machine answers a burst of requests with
    429s and short-lived 5xxs, and taking those for "not archived" would drop
    images that are there."""
    for wait in (2, 5, 15, 40, 0):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                # A 200 that is not an image is the host's error page, and
                # writing that into the repository as a .png is worse than a gap.
                if not r.headers.get_content_type().startswith("image/"):
                    return None
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or not wait:
                return None
        except (urllib.error.URLError, OSError):
            if not wait:
                return None
        time.sleep(wait)
    return None


def from_zip(path: str) -> bytes | None:
    """A wp-content/uploads path, out of the uploads backup.

    Forty-one references are a -WxH copy WordPress generated for a theme that
    no longer exists; the original is in the backup too, and shipping that
    lets Astro do the resizing.
    """
    name = "uploads" + path.split("/wp-content/uploads", 1)[1]
    original = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", name)
    for candidate in dict.fromkeys((original, name)):
        try:
            return uploads.read(candidate)
        except KeyError:
            continue
    return None


def image(src: str, alt: str, stats: dict) -> str | None:
    url = moved(unjetpack(src))
    u = urllib.parse.urlsplit(url)

    if u.netloc == "img.shields.io":
        # A live badge of someone else's build status is not wiki content.
        warn("badge", url)
        return None

    if u.netloc == HOST and "/wp-content/uploads/" in u.path:
        data = from_zip(u.path)
    else:
        # The main site's uploads are 404 now and the Wayback Machine has most
        # of them; the team's screenshots repo and the forum still serve
        # theirs, so the live URL is tried first either way.
        data = get(url) or get(WAYBACK + url)

    if not data:
        warn("MISSING", url)
        return None

    stats["img"] += 1
    return f"![{alt}]({store(url, data)})"


def dimensions(data: bytes) -> tuple[int, int] | None:
    """Pixel size out of the file header.

    Needed only to keep <Image> from asking for a size the file does not have,
    and PNG, JPEG and WebP are all that the featured images are. Four unpacks
    of a header is a smaller thing to own than a dependency.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X":
            return (int.from_bytes(data[24:27], "little") + 1,
                    int.from_bytes(data[27:30], "little") + 1)
        if kind == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if data[:2] == b"\xff\xd8":
        # JPEG keeps the size in a start-of-frame segment, reached by walking
        # the segment lengths -- it is not at a fixed offset.
        i = 2
        while i + 9 < len(data) and data[i] == 0xFF:
            marker = data[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def cover_image(rec: dict) -> tuple[str, int | None] | None:
    """The article's WordPress featured image, stored beside its body images.

    This is what the old theme drew beside the title, and the export keeps it
    as an attachment id rather than a URL. Two of the 101 articles never had
    one; that is an author's choice, not a failure, so it is silent. An id that
    resolves to a file the uploads backup does not hold is the real gap and
    warns.

    Returns the import path and the width to ask <Image> for -- the file's own,
    capped at COVER_MAX. Asking for more than the file has makes Astro write
    attributes describing an upscale it did not perform.
    """
    if rec["slug"] in NO_COVER:
        return None
    url = att_urls.get(rec.get("thumb") or "")
    if not url:
        return None
    url = unjetpack(url)
    data = from_zip(urllib.parse.urlsplit(url).path)
    if not data:
        warn("cover", url)
        return None
    size = dimensions(data)
    if not size:
        # No width attribute at all, rather than a guessed one: Astro then uses
        # the file's own size, which is never an upscale.
        warn("cover", url + " (could not read its size)")
    return store(url, data), min(size[0], COVER_MAX) if size else None


def store(url: str, data: bytes) -> str:
    """Where the file lands, and how the article refers to it. One directory
    per article, so the tree says what belongs to what."""
    if (here, url) in assets:
        return assets[(here, url)]
    name = Path(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).name
    dest = ASSETS / here / name
    n = 1
    while dest.exists() and dest.read_bytes() != data:
        dest = ASSETS / here / f"{Path(name).stem}-{n}{Path(name).suffix}"
        n += 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    assets[(here, url)] = f"../../assets/articles/{here}/{dest.name}"
    return assets[(here, url)]


# --- what the shared converter leaves to the caller -------------------------


def on_embed(block: str, stats: dict) -> str | None:
    yt = re.search(r"(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<\"]+)", block)
    if yt:
        stats["embed"] += 1
        return f'<YouTube url="{yt.group(1)}" />'
    # An embed of another Discovery article. Rendering WordPress's card is
    # pointless once migrated, and the only text the card carried was the
    # target's title, so that is what the link says.
    url = re.search(r"(https?://[^\s<\"]+)", block)
    if posts and url and urllib.parse.urlsplit(url.group(1)).netloc == HOST:
        rec = next((posts[s.lower()] for s in urllib.parse.urlsplit(url.group(1)).path.strip("/").split("/")
                    if s.lower() in posts), None)
        dest = target(url.group(1))
        if rec and dest:
            stats["xref"] += 1
            return f"[{rec['title']}]({dest})"
        return None
    return wp.default_embed(block, stats)


def on_gallery(parts: list[str], stats: dict) -> str | None:
    """A WordPress gallery as a <Gallery>, which lays the pictures out as a grid
    and links each one to itself at full size.

    The component takes the images as imports rather than as Markdown, because
    a link to the picture needs the built asset's URL and only Astro knows it.
    So the images are collected here and write() declares them. Whatever the
    region holds besides images -- a gallery's caption -- follows the grid as
    prose rather than becoming a cell in it.
    """
    names, rest = [], []
    for part in parts:
        m = re.fullmatch(r"!\[(.*)\]\((.+)\)", part, re.S)
        if not m:
            rest.append(part)
            continue
        if m.group(1):
            # The grid's pictures are decoration around the prose that explains
            # them, and <Gallery> says so with alt="". An author who wrote alt
            # text for one meant it to be read.
            warn("gallery", f"alt text dropped: {m.group(1)!r}")
        names.append(f"pic{len(gallery_imports) + 1}")
        gallery_imports.append((names[-1], m.group(2)))
    if not names:
        return "\n\n".join(rest) or None
    return "\n\n".join([f"<Gallery images={{[{', '.join(names)}]}} />"] + rest)


def icons(body: str) -> str:
    """The [icon] shortcode, the block, and the inline SVG the rich-text plugin
    left behind are all one icon named one way."""

    def glyph(name: str, shape: str) -> str:
        if name in ICONS:
            return ICONS[name]
        warn("icon", f"{name} ({shape}, dropped)")
        return ""

    def named(m: re.Match, shape: str) -> str:
        name = re.search(r'data-icon="([^"]+)"', m.group(0))
        return glyph(name.group(1), shape) if name else ""

    # The block is a bare <div>, which the split does not keep; a paragraph is
    # the smallest thing that survives it.
    body = re.sub(r"<!--\s*wp:font-awesome/icon.*?<!--\s*/wp:font-awesome/icon\s*-->",
                  lambda m: "<p>" + named(m, "block") + "</p>", body, flags=re.S)
    body = re.sub(r"<svg[^>]*>.*?</svg>", lambda m: named(m, "inline svg"), body, flags=re.S)
    body = re.sub(r"\[icon name=\"([^\"]+)\"[^\]]*\]",
                  lambda m: glyph(m.group(1), "shortcode"), body)
    # A heading that held nothing but the icon was a visual marker in front
    # of a note. As a heading it is a one-glyph entry in the page outline.
    def only_glyph(m: re.Match) -> str:
        text = re.sub(r"<[^>]+>|&nbsp;|\s", "", m.group(1))
        return "" if text in ICONS.values() else m.group(0)

    return re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>\s*", only_glyph, body, flags=re.S)


def mdx_safe(body: str) -> str:
    """MDX reads a bare `<` or `{` as JSX, so text WordPress escaped and the
    converter unescaped -- `<term>` in a synopsis, `{}` in a config -- is a
    build error. Code spans and fences are literal already; the tags this
    script emits are real JSX and have to stay, braces and all -- escape
    <Gallery images={[…]} /> and the grid ships as its own source, visible on
    the page."""
    ours = re.compile(r"</?YouTube\b[^>]*>|<Gallery\b[^>]*/>|<br />|<a id=\"[^\"]+\"></a>")
    parts = re.split(r"(```.*?```|`[^`\n]*`)", body, flags=re.S)
    for i, part in enumerate(parts):
        if i % 2:                                   # inside a code span or fence
            continue
        out, last = [], 0
        for m in ours.finditer(part):
            out.append(escape(part[last:m.start()]) + m.group(0))
            last = m.end()
        parts[i] = "".join(out) + escape(part[last:])
    return "".join(parts)


def escape(t: str) -> str:
    return t.replace("<", "&lt;").replace("{", "&#123;").replace("}", "&#125;")


# --- output -----------------------------------------------------------------


def write(slug: str, title: str, body: str, modified: str = "",
          cover: tuple[str, int | None] | None = None) -> None:
    body = wp.strip_repeated_title(body, title)
    # The description is read off the body before it is escaped: it is YAML,
    # not MDX, and &lt; in a search result would be the escaping showing.
    fm = ["---", f'title: "{title}"', f'description: "{wp.synth_description(body, title)}"']
    # Unquoted, so YAML reads it as the date Starlight's schema wants. The
    # config asks Starlight to print it; without this it would fall back to
    # git, where every file was last touched by the import.
    if modified:
        fm.append(f"lastUpdated: {modified}")
    fm.append("---")
    imports = []
    if "<YouTube" in body:
        imports.append('import YouTube from "../../components/YouTube.astro";')
    if gallery_imports:
        imports.append('import Gallery from "../../components/Gallery.astro";')
    if cover:
        imports.append('import { Image } from "astro:assets";')
        imports.append(f'import cover from "{cover[0]}";')
    imports += [f'import {name} from "{path}";' for name, path in gallery_imports]
    gallery_imports.clear()
    if imports:
        fm += [""] + imports
    # alt="" on purpose: the h1 above it already names the page, and every one
    # of these is decoration the theme chose. Eagerly, because as a banner it is
    # the first thing under the title and the page's largest image: lazy would
    # mean the reader watching the article's opening move down the screen.
    banner = ""
    if cover:
        w = f" width={{{cover[1]}}}" if cover[1] else ""
        banner = f'<Image src={{cover}} alt="" class="cover" loading="eager"{w} />\n\n'
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{slug}.mdx").write_text("\n".join(fm) + "\n\n" + banner + mdx_safe(body))


def check_sidebar() -> int:
    """Check the hand-authored sidebar; nothing here writes it.

    astro/sidebar.json is Joe Kamprad's menu plan of 2026-09-07, typed out by
    hand: the WordPress categories were a filing system, not a hierarchy, and
    what a reader looks for is an editorial decision. Nothing regenerates it,
    so a new article would simply be unreachable. These three warnings are what
    stop that -- an article in no group, a slug filed twice, a slug whose
    article is gone -- and a new article is added to that file by hand.
    """
    global here
    listed: list[str] = []

    def walk(items: list[dict]) -> None:
        for item in items:
            if "items" in item:
                walk(item["items"])
            else:
                listed.append(item["slug"])

    walk(json.loads(SIDEBAR.read_text()))
    seen: set[str] = set()
    for slug in listed:
        here = slug
        if slug in seen:
            warn("sidebar", "listed twice in sidebar.json")
        elif not (OUT / f"{slug}.mdx").exists():
            warn("sidebar", "in sidebar.json, but there is no article")
        seen.add(slug)
    # Every published post, not only the ones this run wrote: sidebar.json
    # covers the whole wiki whatever SLUGS narrowed the run to.
    for slug, rec in sorted(posts.items()):
        if rec["status"] == "publish" and slug not in seen and slug not in SKIP:
            here = slug
            warn("sidebar", "published, but in no sidebar group")
    here = ""
    return len(listed)


def convert_wxr(args) -> int:
    global uploads, here
    read_wxr(Path(args.wxr))
    if args.media:
        read_media(Path(args.media))
    uploads = zipfile.ZipFile(args.uploads)

    # Each dict exists to change the source, so an entry naming a slug the
    # export no longer has is the one entry nobody would notice going quiet.
    for slug in sorted(set(SKIP) | set(CUT) | set(DOUBLE_ESCAPED) | set(PATCH)):
        if slug not in posts:
            raise SystemExit(f"  {slug!r} is named in SKIP, CUT, DOUBLE_ESCAPED or "
                             "PATCH, but not in the export")

    wanted = args.slugs or sorted(
        s for s, r in posts.items() if r["status"] == "publish" and s not in SKIP)
    written: list[str] = []
    covers = 0
    totals: dict[str, int] = {}
    for slug in wanted:
        rec = posts.get(slug)
        if not rec:
            raise SystemExit(f"  no post named {slug!r} in the export")
        if rec["status"] != "publish":
            print(f"  {slug}: {rec['status']}, not converted")
            continue
        if slug in SKIP:
            print(f"  {slug}: skipped -- {SKIP[slug]}")
            continue
        here = slug
        body, st = wp.convert(icons(rec["body"]), on_embed=on_embed, on_image=image,
                              on_link=target, on_gallery=on_gallery)
        if st["fused"]:
            # What the converter cannot lift out of the prose by itself: a
            # <code> whose lines were typed as newlines rather than <br>, which
            # reads the same as a wrapped sentence. Editing the .mdx is the fix.
            warn("fused", f"{st['fused']} multi-line code spans, flattened onto one line")
        cover = cover_image(rec)
        write(slug, rec["title"], body, rec["modified"], cover)
        check_entities(body)
        written.append(slug)
        covers += bool(cover)
        for k, v in st.items():
            totals[k] = totals.get(k, 0) + v
        print(
            f"  {slug}.mdx  {st['code']} code blocks "
            f"({st['lang']} typed, {st['multiline']} multi-line), "
            f"{st['embed']} video embeds, {st['xref']} cross-refs, "
            f"{st['img']} images ({st['gallery']} galleries), {st['table']} tables"
        )

    here = ""
    listed = check_sidebar()
    print(f"\n  {len(written)} articles, {covers} with a thumbnail, {listed} in the sidebar: "
          + ", ".join(f"{v} {k}" for k, v in sorted(totals.items())))
    if warnings:
        print(f"\n  {len(warnings)} things this could not do:")
        for w in sorted(warnings):
            print("    " + w)
    return 0


def convert_rest(slugs: list[str]) -> int:
    global here
    for slug in slugs:
        here = slug
        post = wp.fetch(API, slug, FIELDS)
        title = wp.plain_title(post)
        body, st = wp.convert(post["content"]["rendered"], on_embed=on_embed)
        write(slug, title, body)
        print(f"  {slug}.mdx  {st['code']} code blocks, {st['img']} images")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--wxr", help="the posts export; without it the REST API is the source")
    p.add_argument("--uploads", help="the uploads backup zip, required with --wxr")
    p.add_argument("--media", help="the media export, for attachment pages linked by name")
    p.add_argument("slugs", nargs="*", help="articles to convert; default is every published one")
    args = p.parse_args()

    if not args.wxr:
        if not args.slugs:
            p.print_help()
            return 2
        return convert_rest(args.slugs)
    if not args.uploads:
        p.error("--wxr needs --uploads: the images are in the backup, not on the site")
    return convert_wxr(args)


if __name__ == "__main__":
    sys.exit(main())
