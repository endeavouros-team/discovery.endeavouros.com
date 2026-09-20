#!/usr/bin/env python3
"""Generate the nginx redirect map from the WordPress permalinks.

Discovery's WordPress URLs were dated and filed under a category --
/network/firewalld/2021/03/ -- and this build serves /firewalld/. Every forum
post, search result and bookmark pointing at the old shape breaks at cutover
unless nginx is told where each one went.

The export knows the answer already: every published item carries the permalink
WordPress served it at in <link>, so this is a generation step and not a
research problem. Run it from the repository root:

    make redirects

The output, deploy/nginx-redirects.conf, is committed and gated the same way
deploy/nginx-csp.conf is -- `make verify` and CI both fail on a diff -- so a
converted article whose slug changed cannot quietly stop being reachable from
its old URL.

The map is keyed on $uri, not $request_uri. $request_uri is the raw line the
client sent, query string and all, so an old link that picked up a tracking
parameter somewhere -- ?utm_source=forum is the common one -- would miss every
key in the map and 404. $uri is the normalised, decoded path, which is exactly
what these keys are.

Nine published slugs have no article here; they are listed in the README under
"What is not here". One of them, `firewall`, does have somewhere to go: it was
superseded by FirewallD, so its old URL is redirected by hand below. The other
eight were the Video Tutorials group, and where their URLs should land is an
editorial decision nobody has made yet, so they are emitted commented out with
the question attached rather than guessed at.
"""

import argparse
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "astro/src/content/docs"
OUT = ROOT / "deploy/nginx-redirects.conf"

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

# A retired slug that still has a destination. The ufw article was superseded by
# FirewallD as the default firewall, so its readers want the article that
# replaced it rather than the front page.
RIDERS = {
    "/network/firewall/2021/03/": "firewalld",
}

# The Video Tutorials group, retired on the forum thread of 8 September 2026.
# Nothing on this site replaces them, so these are written out commented and
# left for the team to answer.
OPEN_QUESTION = (
    "send them to the wiki front page, to the forum, or serve 410 Gone?"
)


def old_slugs(item: ET.Element) -> list[str]:
    """Every slug this post has been filed under before.

    WordPress writes one `_wp_old_slug` postmeta row per rename, so this reads
    all of them rather than the first.
    """
    return [m.findtext("wp:meta_value", namespaces=NS) or ""
            for m in item.findall("wp:postmeta", namespaces=NS)
            if m.findtext("wp:meta_key", namespaces=NS) == "_wp_old_slug"]


def published(wxr: Path) -> list[tuple[str, str]]:
    """(slug, permalink path) for every published post, in export order.

    A post WordPress renamed gets a row per old slug as well. WordPress went on
    serving those permalinks with a redirect of its own, so they were live URLs
    for as long as the wiki was, and people linked them: the add-packages
    article still points at `installation-intro`. The old permalink is the
    current one with the slug segment put back by position --
    /<category>/<slug>/<year>/<month>/ -- because renaming an article moves it
    out of neither its category nor its month.
    """
    out = []
    for item in ET.parse(wxr).getroot().findall("./channel/item"):
        if item.findtext("wp:post_type", namespaces=NS) != "post":
            continue
        if item.findtext("wp:status", namespaces=NS) != "publish":
            continue
        slug = item.findtext("wp:post_name", namespaces=NS) or ""
        path = urllib.parse.urlsplit(item.findtext("link") or "").path
        if not slug or not path:
            raise SystemExit(f"  a published post has no slug or no <link>: {slug!r}")
        out.append((slug, path))
        for old in old_slugs(item):
            segments = path.split("/")
            if len(segments) != 6 or segments[2] != slug:
                raise SystemExit(
                    f"  {slug}: {path} is not /<category>/<slug>/<year>/<month>/, so "
                    f"the renamed slug {old!r} cannot be put back into it by position")
            segments[2] = old
            out.append((slug, "/".join(segments)))
    return out


def check(conf: Path, have: set[str]) -> int:
    """Validate the committed map without the export.

    CI never has the export -- it carries drafts, private posts and author
    addresses and stays outside every repository -- so `git diff --exit-code`
    there only proves the file was committed as generated on somebody's laptop.
    This is the half of the gate that does work without it: every live target
    must still be an article that exists, which is what goes wrong when a slug
    changes and the map is not regenerated.
    """
    if not conf.is_file():
        print(f"  no {conf} -- run make redirects", file=sys.stderr)
        return 1
    seen: dict[str, str] = {}
    bad: list[str] = []
    n = 0
    for line in conf.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or not line.startswith("/"):
            continue
        key, _, target = line.rstrip(";").partition("  ")
        key, target = key.strip(), target.strip()
        n += 1
        if key in seen:
            bad.append(f"{key} is mapped twice")
        seen[key] = target
        if target.strip("/") not in have:
            bad.append(f"{key} -> {target}, which is not an article here")
    if not n:
        bad.append("the map has no entries at all")
    for b in bad:
        print(f"  {b}", file=sys.stderr)
    if bad:
        return 1
    print(f"  {conf.name}: {n} keys, every target resolves")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wxr", type=Path, help="the WordPress export")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--check",
        action="store_true",
        help="validate the committed map against the articles; needs no export",
    )
    args = ap.parse_args()

    have = {p.stem for p in DOCS.glob("*.mdx")}
    if args.check:
        return check(args.out, have)
    if not args.wxr:
        ap.error("--wxr is required unless --check is given")
    posts = published(args.wxr)
    renamed = sum(1 for slug, path in posts if path.split("/")[2] != slug)

    rows: list[tuple[str, str]] = []      # old path -> /slug/
    retired: list[tuple[str, str]] = []   # old path -> the slug that is gone
    for slug, path in posts:
        if slug in have:
            rows.append((path, f"/{slug}/"))
        elif path in RIDERS:
            rows.append((path, f"/{RIDERS[path]}/"))
        else:
            retired.append((path, slug))

    # Every target has to be a page that exists. A slug that changed in the
    # converter and not here would otherwise redirect the whole of the old site
    # into a 404, which is worse than not redirecting at all.
    missing = sorted({t for _, t in rows if t.strip("/") not in have})
    if missing:
        print("  redirect targets with no article:", file=sys.stderr)
        for t in missing:
            print(f"    {t}", file=sys.stderr)
        return 1

    rows.sort()
    retired.sort()

    # Both forms: WordPress advertised the trailing slash, but the bare path is
    # what people paste, and nginx would answer it with its own 301 to the
    # slashed form only if a directory of that name existed here, which it does
    # not.
    keys = [(k, t) for path, t in rows for k in (path, path.rstrip("/"))]
    width = max(len(k) for k, _ in keys)

    out = [
        "# Generated by scripts/gen-redirects.py. Do not edit.",
        f"# {len(rows)} WordPress permalinks, each with and without the trailing slash.",
        f"# {renamed} of them are slugs WordPress renamed and went on redirecting itself,",
        "# read out of the _wp_old_slug postmeta.",
        "#",
        "# Keyed on $uri rather than $request_uri: $request_uri carries the query",
        "# string, so an old link that picked up ?utm_source= on the way would match",
        "# nothing. deploy/nginx-production.conf includes this and returns 301 when",
        "# the variable is set.",
        "#",
        "# The bucket size is raised because a key has to fit in one bucket and the",
        "# default is the CPU cache line -- 64 bytes on the usual x86-64 builds.",
        "# WordPress nested these paths under their category, so the longest key here",
        f"# is {width} characters, and nginx -t would refuse the whole config with",
        '# "could not build map_hash, you should increase map_hash_bucket_size"',
        "# rather than start.",
        "map_hash_bucket_size 128;",
        "",
        "map $uri $discovery_redirect {",
        '    default "";',
        "",
    ]
    out += [f"    {k.ljust(width)}  {t};" for k, t in keys]
    out += [
        "",
        "    # The eight Video Tutorials pages are retired and nothing here replaces",
        f"    # them. Open question for the team: {OPEN_QUESTION}",
        "    # Uncomment with the answer filled in -- a target below, or drop these",
        "    # and add `location = <path> { return 410; }` to the production config.",
        "    #",
    ]
    for path, slug in retired:
        for k in (path, path.rstrip("/")):
            out.append(f"    # {k.ljust(width)}  /;   # was {slug}")
    out += ["}", ""]

    args.out.write_text("\n".join(out), encoding="utf-8")
    print(f"  {args.out}: {len(rows)} redirects ({renamed} from renamed slugs), "
          f"{len(retired)} left open")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
