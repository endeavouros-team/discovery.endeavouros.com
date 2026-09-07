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
    "asterisk": "*",
}

# Published in the export, but not on the wiki. The export is a snapshot of a
# WordPress install nobody is tending any more, so `publish` is not always the
# intent -- and the fix cannot be to delete the .mdx, which the next run would
# write straight back.
SKIP = {
    "firewall": "ufw, superseded by firewalld; Joe meant to make it private",
}

posts: dict[str, dict] = {}       # slug -> record, whatever its status
by_id: dict[str, dict] = {}
attachments: dict[str, str] = {}  # attachment slug -> file URL
att_urls: dict[str, str] = {}     # attachment post id -> file URL, for _thumbnail_id
uploads: zipfile.ZipFile | None = None
assets: dict[tuple[str, str], str] = {}
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
        body = item.findtext("content:encoded", namespaces=NS) or ""
        rec = {
            "slug": item.findtext("wp:post_name", namespaces=NS),
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
        rec = posts.get(seg.lower())
        if rec:
            return internal(rec, u.fragment, href)
    warn("unknown", href)
    return None


def internal(rec: dict, frag: str, href: str) -> str | None:
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
    url = unjetpack(src)
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


def cover_image(rec: dict) -> str | None:
    """The article's WordPress featured image, stored beside its body images.

    This is what the old theme drew above the title, and the export keeps it as
    an attachment id rather than a URL. Two of the 101 articles never had one;
    that is an author's choice, not a failure, so it is silent. An id that
    resolves to a file the uploads backup does not hold is the real gap and
    warns.
    """
    url = att_urls.get(rec.get("thumb") or "")
    if not url:
        return None
    url = unjetpack(url)
    data = from_zip(urllib.parse.urlsplit(url).path)
    if not data:
        warn("cover", url)
        return None
    return store(url, data)


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
    return re.sub(r"\[icon name=\"([^\"]+)\"[^\]]*\]",
                  lambda m: glyph(m.group(1), "shortcode"), body)


def mdx_safe(body: str) -> str:
    """MDX reads a bare `<` or `{` as JSX, so text WordPress escaped and the
    converter unescaped -- `<term>` in a synopsis, `{}` in a config -- is a
    build error. Code spans and fences are literal already; the two tags this
    script emits are real JSX and have to stay."""
    ours = re.compile(r"</?YouTube\b[^>]*>|<br />")
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


def write(slug: str, title: str, body: str, modified: str = "", cover: str | None = None) -> None:
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
    if cover:
        imports.append('import { Image } from "astro:assets";')
        imports.append(f'import cover from "{cover}";')
    if imports:
        fm += [""] + imports
    # alt="" on purpose: the h1 under it already names the page, and every one
    # of these is decoration the theme chose. width caps what Astro emits --
    # without it the resized asset is the full-size original, and some of these
    # are 2500px wide.
    banner = '<Image src={cover} alt="" class="cover" width={1200} />\n\n' if cover else ""
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
        body, st = wp.convert(icons(rec["body"]), on_embed=on_embed, on_image=image, on_link=target)
        cover = cover_image(rec)
        write(slug, rec["title"], body, rec["modified"], cover)
        written.append(slug)
        covers += bool(cover)
        for k, v in st.items():
            totals[k] = totals.get(k, 0) + v
        print(
            f"  {slug}.mdx  {st['code']} code blocks "
            f"({st['lang']} typed, {st['multiline']} multi-line), "
            f"{st['embed']} video embeds, {st['xref']} cross-refs, "
            f"{st['img']} images, {st['table']} tables"
        )

    here = ""
    listed = check_sidebar()
    print(f"\n  {len(written)} articles, {covers} with a banner, {listed} in the sidebar: "
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
