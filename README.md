# EndeavourOS Discovery

Discovery, the EndeavourOS wiki, rebuilt as a static site with
[Starlight](https://starlight.astro.build) on [Astro](https://astro.build) — no runtime, no
database, no admin panel, nothing writable in the webroot.

**This has not launched.** The live wiki is still the WordPress install at
discovery.endeavouros.com. What exists here is a preview at
`https://eos-wiki.sradjoker.cc` — unlisted, serving `noindex` — holding 93 of Discovery's
102 published articles; "What is not here" below names the nine that were left out and why.
"What launch still needs" at the end is the honest list of what stands between the two.

Three tasks cover most of what people come here for:

- Adding or re-importing an article — see "Converting an article".
- Building the site on your own machine — see "Building".
- Putting it in front of the team — see "Deploying to the preview host".

## Layout

- `astro/` — the Starlight site: the articles under `src/content/docs/`, their images under
  `src/assets/articles/<slug>/`, the site configuration in `astro.config.mjs`, the
  hand-authored sidebar in `sidebar.json`, the brand palette in `src/styles/`. The
  build-output gates live in `astro/scripts/`, where the build can run them.
- `deploy/` — `nginx-production.conf` is the live config, and `nginx-csp.conf` and
  `nginx-redirects.conf` beside it are generated and committed, one by the build and one
  from the export. The preview host's own files sit in `deploy/preview/`:
  `nginx-preview.conf` and `docker-compose.yml`.
- `scripts/` — the WordPress importer, the Gutenberg conversion it shares with the main
  site, the link check, the emphasis check, the redirect map, the preview deploy.

The main site lives in its own repository at
`https://github.com/endeavouros-team/endeavouros.com`, laid out the same way on purpose.

`scripts/wp_common.py` is a hand-kept copy of the main site's file of the same name. Both
properties import out of the same Gutenberg editor and hit the same three problems, so the
block splitting, the `<pre>` unwrapping and the inline conversion live in one file — which
means a fix made in either repository has to be applied to the other by hand.

Operational notes for the preview host are kept outside this repository.

## Converting an article

    make convert                                  # every published article
    make convert SLUGS="gaming-101 i3-wm"         # only these

The source is the WordPress export, not the live site: `discovery.endeavouros.com` has
answered every request with a 503 maintenance page since before 6 September 2026, the REST
API included, and the main site's news API disappeared the same way for good. The REST path
in `scripts/convert-wp.py` still exists, behind the absence of `--wxr`, but nothing answers
it.

The export is three files, published by Joe and kept in a plain directory beside the
repositories — `~/Documents/code/discovery-export/` by default, `EXPORT=` to override:

- `posts-discovery.WordPress.2026-09-06.xml` — 120 posts, of which 102 are published. Drafts
  and private posts are parsed but never written: a published article may link to one, and
  that link cannot survive the move.
- `backup_…-uploads.zip` — every file under `wp-content/uploads/`.
- `media-discovery.WordPress.2026-09-06.xml` — optional, `--media`. Nothing in today's export
  needs it.

**It is never copied into a repository.** The WXR carries drafts, private posts and author
email addresses. The only part of it that is committed is the images the importer extracts,
under `astro/src/assets/articles/<slug>/`, which is why nothing on these pages hotlinks the
WordPress install any more.

Three shapes of Gutenberg code block become fenced blocks, with `bash` or `ini` inferred
from the first token. Headings are shifted so the shallowest becomes `h2`, because articles
disagree about whether they open at `h2` or `h4` and a page that starts at `h4` produces a
table of contents with no top level. Tables become Markdown tables, lists keep their
nesting, the eight galleries and the one 26-slide Jetpack slideshow become a `<Gallery>` —
a grid of auto-fitting columns laid out by `astro/src/styles/brand.css`, in which every
picture is a link to itself at full size, because a screenshot in a 358px cell on a phone
is unreadable and there is no lightbox to open — and the `[icon name=…]` shortcodes the
Font Awesome plugin used to render become
the glyph they meant. YouTube embeds become the `<YouTube>` component — a lazy
`youtube-nocookie` iframe, no plugin and no tracking script — and embeds of other Discovery
articles flatten to plain links.

A line break the author typed inside a paragraph stays a line break. 52 of the 93 articles
have one, and they are rarely decorative: a command under the sentence that introduces it,
one step per line, a prompt and its answer. They come across as Markdown hard breaks —
except inside a table cell, where a newline would end the row and the break stays `<br />`.

Links are rewritten rather than carried over. A dated WordPress URL becomes `/<slug>/`; a
`wp-admin/post.php?…` edit URL published inside article text becomes the article it meant;
and every `#heading--…` anchor is remapped to the id Starlight actually generates, which
comes from the heading text and never matched WordPress's. Where a link cannot survive — a
search URL, a category archive, an article that was never published — the label stays as
plain text and the run prints why. That warning list at the end of a run is the output to
read: it names every image that could not be found, every dropped icon and every link that
lost its destination.

The article's WordPress featured image comes across as a banner under the title, centred
and drawn at its own size. The export keeps it as a `_thumbnail_id` pointing at an
attachment, which resolves to a file in the uploads backup; it is stored beside that
article's body images and rendered with `<Image>` asked for the file's own width, capped at
1440 — twice the 720px content column, for a 2x display. Nothing is ever upscaled: 30 of
the 90 are narrower than the column and simply sit in the middle of it, and the only limit
the CSS imposes is a 30rem `max-height`, which binds on the square covers and crops
nothing. It loads eagerly, being the first thing under the title, and its `alt` is empty on
purpose: it is decoration and the heading above it names the page.

90 of the 93 articles have one. Two authors never set a featured image, which is not a
warning; `pacman-basic-commands` had one and is in `NO_COVER` in the importer, because the
picture carries a stock-library watermark across it.

Each article's frontmatter carries `lastUpdated`, taken from the export's
`wp:post_modified_gmt`, and Starlight prints it under the page. The modified date rather
than the publish date, because for a wiki that is the honest one:
`update-troubles-meet-timeshift` is dated 2019 and was last edited in 2022, and 18 articles
were edited this year. Without that field Starlight falls back to git, where every article
was last touched by the import on the same afternoon.

Known gaps, from the last full run:

- One image cannot be found — a `wiki.lxde.org` URL that was never an image, and which the
  Wayback Machine does not have either. Everything else is in the repository, including the
  29 images the main site once served and now 404s, recovered from the Wayback Machine, and
  the Welcome app's three screenshots, which had moved rather than gone: `MOVED` in the
  importer rewrites the `PKGBUILDS` prefix to the `welcome` repository they live in now.
- One `[icon name="frog"]` shortcode names something with no glyph in the map in
  `convert-wp.py`; it is dropped and listed by name. Every other icon in the export now has
  one.
- `wp:spacer` blocks are dropped. `wp:separator` is not: the 41 of them become thematic
  breaks, because authors used the separator to divide sections that have no heading.
- Four anchors in the source point at headings that do not exist in the source either.

### What is not here

Nine of the export's 102 published articles are deliberately not converted, and two more
that were never public left text behind in articles that are. Removing an article is
`SKIP` in `scripts/convert-wp.py`, never a deleted `.mdx`: the next `make convert` would
write a deleted file straight back, and `SKIP` is also what keeps the sidebar check from
asking where the page went. Removing text an article kept about a page that is not here is
`CUT` beside it, two verbatim substrings of the export bracketing the span.

| Slug | Title | Why |
|---|---|---|
| `firewall` | Firewall | ufw, superseded by FirewallD as the default; Joe had meant to make it private and the export caught it first |
| `back-up` | Back up | Video Tutorials group, retired |
| `fix-arch-linux-boot-with-arch-chroot` | Fix Arch Linux Boot with arch-chroot | Video Tutorials group, retired |
| `general-linux-tutorials` | General Linux tutorials | Video Tutorials group, retired |
| `gui-applications` | GUI applications | Video Tutorials group, retired |
| `install-endeavouros` | Install EndeavourOS | Video Tutorials group, retired |
| `joekamprad-video-tutorials` | joekamprad video tutorials | Video Tutorials group, retired |
| `maintenance` | Maintenance | Video Tutorials group, retired |
| `pacman-aur-tutorials` | Pacman & AUR tutorials | Video Tutorials group, retired |

The eight Video Tutorials pages went on the forum thread of 8 September 2026: Bryanpwo
asked whether a group of years-old embedded videos should come across at all and joekamprad
agreed it should not. Videos embedded inside an ordinary article are untouched — nine
articles still have one — so the `<YouTube>` component and the `frame-src` entry for
`youtube-nocookie.com` in the CSP both stay.

Two articles were private in WordPress and were therefore never imported, but articles that
are here still carried text about them. The same forum thread settled that they stay
private, so `CUT` removes the remnants:

| Slug | Title | What was cut |
|---|---|---|
| `envy-control` | Envy Control | the EnvyControl entry in `nvidia-optimus-notebooks-hybrid-graphics` — a bold sentence introducing the tool and a bare label under it, which is what the dissolved link had become |
| `bumblebee-for-nvidia-optimus-older-systems` | Bumblebee for NVIDIA Optimus (older systems) | the closing Bumblebee section of `new-nvidia-driver-installer-nvidia-inst`, whose only instruction was to read that page |

`arch-chroot` is cut for a related reason: its "Useful links" list opened with a bullet
whose link text was the retired video tutorial's own URL, so dissolving the link would have
left the dead URL standing there as prose.

None of the eight retired Video Tutorials slugs needs an entry in the redirect map from the
old WordPress URLs, because there is nothing on this site to send a reader to. What those
URLs should answer with instead is an editorial decision rather than a generation step.
`firewall` is the exception: FirewallD superseded it, so its old URL redirects to
`/firewalld/`.

## The sidebar

`astro/sidebar.json` is hand-authored and nothing generates it. It is Joe Kamprad's menu
plan of 2026-09-07: nine sections — Getting Started, Hardware, Desktops, Software &
Packages, Storage & Filesystems, System Rescue & Boot, Advanced, ARM / Homeserver,
Community — left open, with their subgroups collapsed. `astro/astro.config.mjs` imports it.

A group is `{"label": …, "collapsed": true, "items": […]}` and a leaf is `{"slug":
"the-slug"}`, which takes its label from the article's own `title`. So **a new article is
reachable only once its slug is added to this file by hand.** That is what `make convert`
checks and what the `sidebar` warnings in a run mean: a published article in no group, a
slug listed twice, a slug whose `.mdx` no longer exists.

The home page's "Start here" grid is the other hand-picked list: six `LinkCard`s in
`astro/src/content/docs/index.mdx`, nothing derived from traffic or dates, and a comment in
the file saying so. Changing which six is editing that file.

## Building

Node 22.12 or later and the dependencies, once per checkout. `astro/.nvmrc` pins the version
and the lockfile is committed:

    (cd astro && nvm use && npm ci)

`npm ci` rather than `npm install`: it installs exactly what the lockfile pins. `npm run
build` then runs three things in order — `astro/scripts/audit-lock.mjs`, the Astro build,
then `astro/scripts/gen-csp.mjs` over the output it produced. The first refuses a package
that executes an install script, resolves off-registry, or ships without a sha512 integrity
hash, unless it is in the allowlist in that file — the control the WordPress plugin system
never had. The third is the CSP, below.

Then:

    make check          # astro check over the components and the content collections
    make links          # every internal link and anchor in astro/dist/ resolves
    make emphasis       # no literal ** left standing in the prose

    make dev-astro      # astro dev on :4321
    make build-astro    # -> astro/dist/  (make build is the same target)

    make verify         # build, then fail if either generated file has drifted
    make redirects      # regenerate deploy/nginx-redirects.conf from the export
    make serve          # serve astro/dist/ on :8813 for LAN review
    make deploy-preview # build, rsync to the preview host
    make clean          # drop the dist/ and .astro/ trees

`make links` and `make emphasis` need a build to check against. Everything under
`astro/dist/` is gitignored, so a clean checkout and `make build-astro` reproduces it.

## The content security policy

`deploy/nginx-csp.conf` is generated, committed, and the one file here you must not edit by
hand. `astro/scripts/gen-csp.mjs` walks the built `astro/dist/`, hashes every inline script
on every page, and writes the nginx `add_header` line; `deploy/preview/nginx-preview.conf`
includes it.

Astro's native `security.csp` was tried first and does not work with Starlight. It hashes
only the scripts that pass through Astro's own pipeline, so the six that Starlight writes
straight into the HTML — theme provider, search modal, sidebar persistence — end up blocked
by the policy Astro itself emitted: 4 of 10 inline scripts covered. Hashing the real build
cannot miss any. Emitting a header rather than a `<meta>` tag also means `frame-ancestors`
is honoured, which browsers ignore in `<meta>`.

Two tokens in the policy look loose and are deliberate:

- `script-src` carries `'wasm-unsafe-eval'`. Pagefind, which is Starlight's search, runs its
  index as WebAssembly, and a browser refuses to compile WASM under a hash-pinned
  `script-src` without that token. It permits compilation only — not `eval()`, not
  `Function()`.
- `style-src` keeps `'unsafe-inline'`. Starlight sets inline style attributes for the
  sidebar and code-block layout, and hashing those requires `'unsafe-hashes'`, which weakens
  script handling too. An inline style cannot execute code, so this is the smaller exposure
  by a wide margin, and `script-src` stays fully hash-pinned.

Change an inline script and the next build rewrites the snippet, at which point `make
verify` and CI both fail on the diff until the regenerated file is committed. That is the
point: the preview host cannot be handed a policy that blocks scripts the pages actually
load.

## Deploying to the preview host

The preview is where this is reviewed, and it is separate from the production deploy in the
next section: an always-on host, so reviewing this needs a link rather than a VPN invitation
and a laptop that has to stay awake. It serves `noindex` and nothing here ships anywhere
else.

    make deploy-preview

That builds, rsyncs `astro/dist/` to `sra-oracle:/home/ubuntu/discovery-preview/html/` with
`--delete`, syncs both nginx configs, reloads nginx inside the `eos-wiki` container and
probes `http://127.0.0.1:8083/` on the host. `PREVIEW_HOST` and `PREVIEW_DIR` override the
target.

The stack is `deploy/preview/docker-compose.yml`: one `nginx:alpine` bound to
`127.0.0.1:8083`, with content and config bind-mounted so a redeploy needs no restart.
Create it once with:

    scripts/deploy-preview.sh --setup

The config is mounted as a directory, not a single file. A single-file bind mount pins one
inode, and rsync writes a replacement and renames it, so the container would go on serving
the old config forever with no visible error.

`deploy/preview/nginx-preview.conf` sends the generated CSP plus `X-Content-Type-Options`,
`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`
and — the preview-only one — `X-Robots-Tag: noindex, nofollow`. Access logs are off.

The public hostname is served through a Cloudflare Tunnel already running on that box for
other services. Its route is managed in the dashboard and is not scriptable from here, so if
the URL 404s or hangs after a deploy, that is where to look.

## Deploying to production

The build does not happen on the server, and the server needs no toolchain — no runtime, no
interpreter, no build step, which is the whole point of replacing the WordPress install
rather than repairing it. CI builds the wiki and attaches a tarball to a GitHub Release; the
deploy is downloading that and unpacking it into the webroot.

### 1. Cut a release

Tags are `vYYYY.MM.DD`, the day of the release, with `.1`, `.2` and so on appended for a
further release on the same day:

    git tag -a v2026.09.20 -m "launch"
    git push origin v2026.09.20

Pushing a `v*` tag is what triggers a build. **Pushing to `main` does not** — ordinary
commits are checked by `.github/workflows/check.yml` and publish nothing, so an article edit
or a converter fix never produces a release.

The release job (`.github/workflows/build.yml`) audits the lockfile, builds with
`PUBLIC_INDEXABLE=true`, then runs the same gates as an ordinary push — the link check, the
Astro type check, the CSP snippet, the redirect map, the emphasis check — and finally asserts
the result is actually indexable: `robots.txt` allows crawling and names the sitemap, and no
page carries `noindex`. A build with that flag missing fails here rather than being
published.

    gh run watch --repo endeavouros-team/discovery.endeavouros.com

To rebuild a tag that already exists — a CI fix, or a run that failed halfway — start the
*Build wiki* workflow by hand (Actions → Build wiki → Run workflow) and give it the tag name.
It checks that tag out, builds it, and replaces the asset on that release.

### 2. Get the tarball

    gh release download v2026.09.20 --repo endeavouros-team/discovery.endeavouros.com

Or from the Releases page. The filename carries the tag and the short commit it was built
from — `eos-wiki-<tag>-<short sha>.tar.gz`.

### 3. Put it on the server

    tar -xzf eos-wiki-v2026.09.20-*.tar.gz -C /var/www/discovery.endeavouros.com/

If you would rather rsync an extracted copy, use `--delete`. It is load-bearing: it is what
keeps the webroot holding this wiki and nothing else, and anything left beside it stays
reachable — which for this host means the WordPress tree the rebuild exists to retire. The
target must therefore hold **only** this site; check before running it.

### 4. Install the nginx config

`deploy/nginx-production.conf`, plus the two generated files it includes —
`deploy/nginx-csp.conf` and `deploy/nginx-redirects.conf` — which go beside it in the
directory the `include` lines name.

The lines marked `CONFIRM` are what has to be checked against the box: the `server_name`, the
webroot, the TLS certificate paths and whether the certificate covers
`discovery.endeavouros.com` at all, and the include paths. There is no `www` for this host
and none is claimed.

The last check is the one that cannot be done from here: **the WordPress vhost answering for
`discovery.endeavouros.com` has to be disabled as this config loads.** Two server blocks
claiming one name is resolved by include order rather than by intent, and the loser fails
silently, so a half-done cutover looks like nothing happened. The old install is also what
serves the dated permalinks today, and `nginx-redirects.conf` takes that job over; both
cannot be live at once.

Then the usual:

    sudo nginx -t && sudo systemctl reload nginx

## What CI does

`.github/workflows/check.yml` runs on every push to `main` and every pull request: `npm ci`,
`npm run build`, `make links`, `make check`, then `git diff --exit-code
deploy/nginx-csp.conf` and the same check over `deploy/nginx-redirects.conf`, and
`make emphasis` over the built pages. It publishes nothing.
`.github/workflows/build.yml` is the one that publishes, and only a `v*` tag starts it —
see "Deploying to production".

It is also what makes the wiki editable by people who do not run the toolchain. An article
is a Markdown file that can be edited in the GitHub web UI, and that only holds if something
builds and link-checks the result on their behalf.

## What launch still needs

Most of it is now in the repository: `astro/src/pages/robots.txt.ts` writes a `robots.txt`
that names Starlight's `sitemap-index.xml` once `PUBLIC_INDEXABLE` is set,
`.github/workflows/build.yml` sets that flag and refuses to publish a build that does not
honour it, `deploy/nginx-production.conf` is the live config — without the preview's
`X-Robots-Tag` — and `deploy/nginx-redirects.conf` maps 94 old WordPress permalinks onto
their articles here. See "Deploying to production".

What is left is not code:

- **The nine retired slugs.** Eight of them — the Video Tutorials group under "What is not
  here" — are in `deploy/nginx-redirects.conf` as a commented block, because nothing on this
  site replaces them and where their URLs should land is an editorial decision: the wiki
  front page, the forum, or `410 Gone`. That question is on the forum. Uncommenting the block
  with a target, or answering it with `return 410`, is what closes this. The ninth,
  `firewall`, needed no decision — FirewallD superseded it, so its old URL already redirects
  to `/firewalld/`.
- **The `CONFIRM` lines in `deploy/nginx-production.conf`.** The `server_name`, the webroot,
  the certificate paths and whether the certificate covers `discovery.endeavouros.com`, the
  include paths, and the WordPress vhost being disabled as the config loads. Every one of
  them is about the box rather than about this repository, so none can be settled from here.
- **The verify link on the main site's download page.** On go-live day, and deliberately
  not before, `VerifyInstructions.astro` in the site repository gains a link to
  `/how-to-check-and-trust-key-and-signature-for-the-endeavouros-iso/` here — agreed on
  the forum, 2026-09-08. Added any earlier it would point at the WordPress install this
  wiki replaces, which answers with a 503.
