# EndeavourOS Discovery

Discovery is the EndeavourOS wiki.
It is static HTML built from this repository with Starlight on Astro.
It is live at `https://discovery.endeavouros.com`.

Starlight is the documentation theme. Astro is the static site generator: it turns the source
files in this repository into the HTML files that nginx serves.

## How a change reaches the server

The source in this repository is the input. The path to production is: edit here -> commit ->
push -> push a `v*` tag -> CI builds -> Release asset -> server.

A commit is a saved set of changes with a message. A push sends your commits to GitHub. A tag
is a named bookmark on a commit; pushing one is what starts the build. CI is the automated
GitHub Actions work that checks and builds the site.

CI attaches one file to a GitHub Release:
`eos-wiki-<tag>-<short sha>.tar.gz`, for example
`eos-wiki-v2026.10.20-a1b2c3d.tar.gz`. You download that file and unpack it into the webroot.

The tarball is output, never input. Nobody runs it, edits it, repacks it, or makes one by hand.
No contributor builds locally to publish; CI builds from the source in git. The development
server is only for looking at changes on your own machine.

## Set up your machine, once

These instructions are for EndeavourOS. Python 3.11 or newer is already installed there, and
the `make` targets use it.

Start in your home directory.

    cd ~

Install git, make, Node.js, npm, and the GitHub command-line tool. Git records changes, `make`
runs the checks, Node.js runs Astro, npm installs Astro's dependencies, and `gh` talks to GitHub.

    sudo pacman -S --needed git make nodejs npm github-cli

Pacman may ask `Proceed with installation? [Y/n]`; press Enter. Success returns to the prompt
after `:: Running post-transaction hooks...`, or prints `there is nothing to do` when every
package is already installed. `--needed` is what skips the ones already present.

Log in to GitHub.

    gh auth login

Choose `GitHub.com`, choose `HTTPS`, answer `Y` to `Authenticate Git with your GitHub
credentials?`, and choose to log in with a web browser. Success ends
with `✓ Logged in as` followed by your GitHub user name. This also stores the credentials
that `git push` needs.

Tell git who you are once, because a commit records an author and the first commit otherwise
stops with `Author identity unknown`.

    git config --global user.name "Your Name"
    git config --global user.email "you@example.com"

Use the name and email address of your GitHub account. Success prints nothing.

Download the repository.

    gh repo clone endeavouros-team/discovery.endeavouros.com

Success prints `Cloning into 'discovery.endeavouros.com'...` and returns to the prompt without an
error. The files are now in `~/discovery.endeavouros.com/`.

Enter the Astro directory.

    cd ~/discovery.endeavouros.com/astro

Install the exact dependency versions recorded in the lockfile.

    npm ci

Success includes a line like `added 433 packages, and audited 434 packages in 2s`; the counts and
seconds vary. A vulnerabilities notice follows and suggests `npm audit fix`. That notice is
expected and must be ignored: `npm audit fix` would rewrite the lockfile that the build audits.
Use `npm ci`, not `npm install`, because `npm ci` installs exactly what the committed lockfile
pins.

On another distribution, install git, GitHub CLI, Python 3.11 or newer, Node 22.12 or newer,
and npm with that distribution's package manager. `astro/.nvmrc` names Node 22 for nvm
users; nvm is not required.

## See the wiki on your machine

Enter the repository root before updating it.

    cd ~/discovery.endeavouros.com

Download the latest commits.

    git pull

Success either lists updated files or ends with `Already up to date.`

If the list of updated files includes `astro/package-lock.json`, run `npm ci` again from
`~/discovery.endeavouros.com/astro` before starting the server.

Enter the Astro directory.

    cd ~/discovery.endeavouros.com/astro

Start the development server.

    npm run dev

Success prints a banner containing `┃ Local    http://localhost:4321/` and ending with
`watching for file changes...`. Open the Local URL in a browser. Saving a source file reloads
the page. The terminal stays busy until you press Ctrl-C to stop the server.

The server keeps this terminal busy. Open a second terminal for the commands below; it starts in
your home directory, so begin with the `cd` line each section gives.

Search shows a notice instead of results in the development server; it only works in a built
site, which CI makes.

## Everyday tasks

File paths in this section are relative to the repository root,
`~/discovery.endeavouros.com`.

### Edit an article

Articles are `.mdx` files under `astro/src/content/docs/`. MDX is Markdown that may also use
Astro components. The filename becomes the article's address: for example,
`astro/src/content/docs/pacman-basic-commands.mdx` is served at
`http://localhost:4321/pacman-basic-commands/`.

Front matter is the block between the `---` lines at the top of an article. Starlight requires
`title`, and every article here carries both `title` and `description`:

    ---
    title: Pacman basic commands
    description: The commands used for everyday package management.
    ---

The description appears in search results and link previews, so it is not decoration. Code
fences take a language such as `bash` or `ini`; the language controls syntax highlighting and
the copy button.

Ordinary Markdown covers headings, emphasis, lists, and links:

    ## Install packages
    Run **the update** first.
    - Install the package.
    Read the [pacman documentation](https://wiki.archlinux.org/title/Pacman).

Put an image in `astro/src/assets/articles/<slug>/`, creating that directory with the article's
filename without `.mdx`. For `pacman-basic-commands.mdx`, the worked directory is
`astro/src/assets/articles/pacman-basic-commands/`. Reference
`astro/src/assets/articles/<slug>/picture.png` from the article as
`![what the picture shows](../../assets/articles/<slug>/picture.png)`; the worked reference is
`![the pacman terminal](../../assets/articles/pacman-basic-commands/picture.png)`.

Two pages are written by hand and no import touches them: `index.mdx`, the landing page, and
`article-removed.mdx`, which the retired WordPress URLs use. Edit them like any other file.

Keep the development server running while you edit. Save the file and check the article's own
address, for example `http://localhost:4321/pacman-basic-commands/`.

### Add an article

`my-new-article` is a placeholder. The filename becomes the address, so use lowercase words
joined by hyphens.

1. Write `astro/src/content/docs/my-new-article.mdx`. If the article is in the WordPress export,
   use the importer covered in "Converting an article" under Reference. Give the file `title`,
   `description`, and `lastUpdated: 2026-10-20` if you know when the content was last revised.
2. Add its slug to the group where it belongs in `astro/sidebar.json`. That file is hand-authored;
   the importer checks it but never writes it. The surrounding JSON has this shape:

       "items": [
         { "slug": "an-existing-article" },
         { "slug": "my-new-article" }
       ]

3. Run the content check from the repository root. First enter that directory.

       cd ~/discovery.endeavouros.com

   Then run the check.

       make check

   Success ends with `0 errors`, `0 warnings`, and `0 hints`.

A slug in `astro/sidebar.json` that has no article fails the build with a message that ends
in `specified in the Starlight sidebar config does not exist`, in the development server and
in CI, so a typo cannot reach the site. The reverse is not caught by
anything: an article missing from `astro/sidebar.json` is in nobody's navigation, although it is
still built and reachable by its URL and by search. Check the sidebar in the browser.

## Publish

You need push access to the repository; everyone on the website team has it. Anyone else opens a
pull request instead, see `CONTRIBUTING.md`.

Enter the repository root.

    cd ~/discovery.endeavouros.com

Optionally run the same checks CI runs before sending the change. They take about a minute and
save a round trip when something is wrong; CI runs them anyway.

    make verify
    make links

Both commands return to the prompt without an error when the checks pass.

Review the changed files.

    git status

Success shows the changed files.

Stage everything that `git status` listed.

    git add -A

This stages every file `git status` listed. If `git status` listed a file you did not mean to
change, unstage it and look at it before going on.

    git restore --staged <path>

Replace `<path>` with the path that `git status` printed, for example
`astro/src/content/docs/index.mdx`. Success prints nothing. A second `git status`
shows the intended files under `Changes to be committed`.

Save the staged change as a commit. Subjects use lowercase `area: summary` form and imperative
mood.

    git commit -m "wiki: clarify pacman commands"

Replace the example message with one that describes your change.

Success starts with a line such as `[main a1b2c3d] wiki: clarify pacman commands`.

Send the commit to GitHub.

    git push

Success ends with a line containing `main -> main`.

Open the
[Actions tab](https://github.com/endeavouros-team/discovery.endeavouros.com/actions). The run for
your commit is the top row that carries your commit message. Wait for its `Check` run to show a
green tick. A red cross means the change is not ready to release; open the failed step and fix it
before continuing.

The
[Releases page](https://github.com/endeavouros-team/discovery.endeavouros.com/releases) shows the
tags already used. A tag can also exist without a Release when its build failed, so check
your copy as well, from `~/discovery.endeavouros.com`:

    git tag -l v2026.10.20

Output means the tag exists; append `.1`. No output means it is free. The commands below use
`v2026.10.20` as an example; use your tag, not the example, in every command that follows.

Create an annotated tag for the release. Tags use `vYYYY.MM.DD`, for example `v2026.10.20`.
Append `.1`, `.2`, and so on for another release on the same day.

    git tag -a v2026.10.20 -m "release v2026.10.20"

Success prints nothing.

Push the tag to start the release build.

    git push origin v2026.10.20

Success ends with `[new tag] v2026.10.20 -> v2026.10.20`.

Return to the Actions tab and wait for the `Build wiki` run to show a green tick. Then return to
the Releases page. Release `v2026.10.20` must contain an asset named like
`eos-wiki-v2026.10.20-a1b2c3d.tar.gz`, where `a1b2c3d` is the short commit ID.

Download the release asset.

    gh release download v2026.10.20 -p '*.tar.gz' -D ~/Downloads

Success leaves the `.tar.gz` asset in `~/Downloads`.

Copy it the way you already reach the server. This example uses `scp`; replace `you` and `server`
with your server user and host.

    scp ~/Downloads/eos-wiki-v2026.10.20-*.tar.gz you@server:

Success returns to the prompt without an error and puts the tarball in that user's home directory
on the server.

On the production server, work from that home directory. The path
`/var/www/discovery.endeavouros.com/` is the webroot named in
`deploy/nginx-production.conf` and must match the host.

Create a fresh directory and unpack the release there. `tar` adds and replaces files but never
removes old ones, so the fresh directory keeps the webroot holding this release and nothing else.

    sudo rm -rf /var/www/discovery.endeavouros.com.new
    sudo mkdir /var/www/discovery.endeavouros.com.new
    sudo tar -xzf eos-wiki-v2026.10.20-*.tar.gz -C /var/www/discovery.endeavouros.com.new/
    sudo chown -R root:root /var/www/discovery.endeavouros.com.new
    sudo mv /var/www/discovery.endeavouros.com /var/www/discovery.endeavouros.com.old
    sudo mv /var/www/discovery.endeavouros.com.new /var/www/discovery.endeavouros.com

Success prints nothing and places `index.html`, `robots.txt`, and the built site under the
webroot. The webroot must be owned by root or a dedicated deploy user and must not be writable by
the nginx user.

The release tarball contains the site, not the nginx files under `deploy/`. Keep the production
nginx configuration, CSP snippet, and redirect map from the same tag installed as described in
"Nginx configuration and deployment verification" under Reference.

Test and reload nginx.

    sudo nginx -t && sudo systemctl reload nginx

Success includes `syntax is ok` and `test is successful`; the reload command then prints no
error.

The checks below run from any directory on any machine. Set the address they use.

    base=https://discovery.endeavouros.com

Success prints nothing. The following commands use `base` for the live wiki address.

Check the root page.

    curl -sS -D - -o /dev/null "$base/"

It must return `200` with the seven security headers named in the Reference section and no
`X-Robots-Tag`.

Check both forms of an old firewalld address.

    curl -sS -D - -o /dev/null "$base/applications/firewalld/2022/03/"

    curl -sS -D - -o /dev/null "$base/applications/firewalld/2022/03?utm_source=deploy-check"

Each must return `301` to `/firewalld/`.

Check a retired article.

    curl -sS -D - -o /dev/null "$base/video-tutorials/back-up/2021/04/"

It must return `301` to `/article-removed/`.

Find one built asset.

    asset=$(curl -fsS "$base/" | grep -o '/_astro/[^"]*' | head -1)
    echo "$asset"

The second command must print a path starting `/_astro/`; an empty line means the first command
did not get the page.

Check that asset.

    curl -sS -D - -o /dev/null "$base$asset"

It must return `200`, the seven security headers, and
`Cache-Control: public, max-age=31536000, immutable`.

Check the crawler instructions.

    curl -fsS "$base/robots.txt"

It must allow `/` and name the sitemap.

Finally open the page you changed on the live site, for example
`https://discovery.endeavouros.com/pacman-basic-commands/`, and confirm the change is there.

After every check passes, remove the old webroot from the production server.

    sudo rm -rf /var/www/discovery.endeavouros.com.old

Success prints nothing.

## When something goes wrong

- `gh` is not found: repeat the pacman install step. `github-cli` provides it.
- `gh` says you are not authenticated: repeat the GitHub login step and choose GitHub.com,
  HTTPS, and web-browser login.
- The dependency install reports an unsupported engine: install Node 22.12 or newer, then repeat
  the install from `~/discovery.endeavouros.com/astro`.
- The development server says port 4321 is in use: stop the earlier server with Ctrl-C, then
  start it again from `~/discovery.endeavouros.com/astro`.
- The browser cannot reach `localhost:4321` after `npm run dev`: read the terminal. An article
  with a bad front-matter field stops the server before it listens. Fix the field and start
  the server again.
- `make check` prints `[InvalidContentEntryDataError] docs → <slug> data does not match
  collection schema. title: Required`: the named article has no `title` line in its front
  matter. Add it and run the check again.
- CI's "literal emphasis markers" step fails: a `**` in an article is not closed, usually a
  space before the closing one as in `**text **`. The step names the page.
- A push is rejected because the remote changed: pull from `~/discovery.endeavouros.com`, resolve
  any reported conflict, run the checks again, and push.
- `Check` has a red cross: open the failed Actions step. Do not create a tag until `Check` has a
  green tick.
- No `Build wiki` run starts: confirm that the tag begins with `v` and that the tag push
  succeeded.
- `Build wiki` fails or the Release has no `.tar.gz` asset: open the failed Actions step. Do not
  build or repack the tarball locally.
- `Build wiki` failed after a CI or server fix and the tag is already pushed: rebuild it without a
  new tag, see "Cutting and rebuilding a release" under Reference.
- An article builds but is absent from the sidebar: add its slug to the right group in
  `astro/sidebar.json`.
- The content check fails: read "Building" under Reference and fix the diagnostics it prints.
- CI's CSP snippet step fails: read "The content security policy" under Reference. Commit the
  generated snippet; never edit it by hand.
- CI's redirect map step fails: read "What CI does" and "Converting an article" under Reference.
  The export is required to regenerate the map, and the committed map is checked without it.

## Reference

The built wiki has no runtime, database or admin panel, and nothing in the webroot is writable by
nginx. The sections below keep the importer, build, preview, release and server details together.

### Layout

- `astro/` — the Starlight site: the articles under `src/content/docs/`, their images under
  `src/assets/articles/<slug>/`, the site configuration in `astro.config.mjs`, the
  hand-authored sidebar in `sidebar.json`, the brand palette in `src/styles/`. The
  build-output gates live in `astro/scripts/`, where the build can run them.
- `deploy/` — `nginx-production.conf` is the intended production config; the host does not
  match it yet, as "After launch" explains. `nginx-csp.conf` and `nginx-redirects.conf` beside
  it are generated and committed, one by the build and one from the export. The preview host's
  own files sit in `deploy/preview/`:
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

### Converting an article

    make convert                                  # every published article
    make convert SLUGS="gaming-101 i3-wm"         # only these

The source is the WordPress export, not the live site: the WordPress install at
`discovery.endeavouros.com`, now retired, had answered every request with a 503 maintenance
page since before 6 September 2026, the REST API included, and the main site's news API
disappeared the same way for good. The REST path in `scripts/convert-wp.py` still exists,
behind the absence of `--wxr`, but nothing answers it.

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
- Two anchors in the source point at headings that do not exist in the source either. Both
  are a heading linking to itself — in `create-install-media-usb-key` and in `firewalld` —
  and dalto's answer on the forum, 2026-09-20, was that the links should go, which the
  conversion had already done by dissolving them into the plain headings. Two more anchors
  are gone rather than accepted: the id an author put on the RTD3 note in `nvidia-intro`
  now survives into the page, and the "N" in front of it was a dead link of its own.
- One link now finds an article that WordPress had renamed under it: `installation-intro`
  is the slug `live-iso-tricks-tips` used to have, and `_wp_old_slug` in the export says so.
  A paragraph's id and a renamed slug are the two things a WordPress export knows that the
  first pass through it did not read.

#### What is not here

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

The eight retired Video Tutorials slugs redirect to `/article-removed/`, a hand-written
page that says the article was removed, names all eight, and points at the front page and
the forum. dalto settled that on the forum, 2026-09-20: one page for every removed article,
rather than a `410 Gone` or a silent drop onto the front page that leaves a reader
wondering what became of the article they clicked. `firewall` is the exception it always
was — FirewallD superseded it, so its old URL rides to `/firewalld/` instead.

Category pages are not here either. WordPress served an archive at `/category/<name>/` for
each of the 31 categories its published posts carried; Starlight has no such page, the
sidebar groups are navigation rather than URLs, and the redirect map covers post permalinks
only, so every one of those addresses is a 404. Twenty-six of the categories hold more than
one article, so there is no target to derive for them — sending `/category/arm/` to any one
of its eight articles would be a choice, not a redirect. Nobody has made that choice yet.
Do not link to a category URL from anywhere, the main site included.

### The sidebar

`astro/sidebar.json` is hand-authored and nothing generates it. It is Joe Kamprad's menu
plan of 2026-09-07: nine sections — Getting Started, Hardware, Desktops, Software &
Packages, Storage & Filesystems, System Rescue & Boot, Advanced, ARM / Homeserver,
Community — left open, with their subgroups collapsed. `astro/astro.config.mjs` imports it.

A group is `{"label": …, "collapsed": true, "items": […]}` and a leaf is `{"slug":
"the-slug"}`, which takes its label from the article's own `title`. So **a new article is
shown in the sidebar only once its slug is added to this file by hand.** That is what
`make convert` checks and what the `sidebar` warnings in a run mean: a published article in
no group, a slug listed twice, a slug whose `.mdx` no longer exists. Leaving a page out
hides it from navigation and nothing more — it is still built, and still reachable by its
URL and by search. `article-removed` is such a page on purpose.

The home page's "Start here" grid is the other hand-picked list: six `LinkCard`s in
`astro/src/content/docs/index.mdx`, nothing derived from traffic or dates, and a comment in
the file saying so. Changing which six is editing that file.

### Building

Node 22.12 or later and the dependencies, once per checkout. `astro/.nvmrc` pins the version
for nvm users (`nvm use` first, if you use it) and the lockfile is committed:

    (cd astro && npm ci)

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

### The content security policy

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

### Deploying to the preview host

The preview is at `https://eos-wiki.sradjoker.cc`. It is unlisted and serves `noindex`. It is
separate from the production release and deploy sections below: an always-on host, so reviewing
this needs a link rather than a VPN invitation and a laptop that has to stay awake. Nothing here
ships anywhere else.

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

### Cutting and rebuilding a release

The build does not happen on the server, and the server needs no toolchain — no runtime, no
interpreter, no build step, which is the whole point of replacing the WordPress install
rather than repairing it. CI builds the wiki and attaches a tarball to a GitHub Release; the
deploy is downloading that and unpacking it into the webroot.

#### Cut a release

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

### Nginx configuration and deployment verification

#### Get the tarball

    gh release download v2026.09.20 --repo endeavouros-team/discovery.endeavouros.com

Or from the Releases page. The filename carries the tag and the short commit it was built
from — `eos-wiki-<tag>-<short sha>.tar.gz`.

#### Put it on the server

Into a fresh directory, then swap it into place; the swap sequence is under "Publish" above.
The one-line form is only for a directory that is still empty:

    sudo tar -xzf eos-wiki-v2026.09.20-*.tar.gz -C /var/www/discovery.endeavouros.com.new/

`tar -xzf` adds and replaces files but never removes one, so use it only into an empty
directory, or a fresh one that is then swapped into place. Otherwise a page removed between
releases, or a file something else left there, stays reachable. If you would rather rsync
an extracted copy into the existing webroot, use `--delete`. It is load-bearing: it is what
keeps the webroot holding this wiki and nothing else. On the previous host that meant the
WordPress tree the rebuild exists to retire; on any host the target must hold **only** this
site, so check before running it.

The webroot and everything in it are owned by root or a dedicated deploy user, and are not
writable by the user nginx runs as — through ownership, group or ACL. "Nothing writable in
the webroot" is a promise the first paragraph makes and only the deploy can keep: nothing
in the tarball or in the nginx config enforces it.

#### Install the nginx config

The release tarball contains only `astro/dist`, not the three files under `deploy/`. Take
`deploy/nginx-production.conf`, `deploy/nginx-csp.conf`, and `deploy/nginx-redirects.conf`
from the repository at the same tag. `nginx-redirects.conf` is included at http level because
it holds a `map`; `nginx-csp.conf` is included in the server block and again inside
`location /_astro/`. If the files go somewhere other than `/etc/nginx/conf.d/`, change every
include path with them.

The lines marked `CONFIRM` are what has to be checked against the box: the `server_name`, the
webroot, the TLS certificate paths and whether the certificate covers
`discovery.endeavouros.com` at all, and the include paths. There is no `www` for this host
and none is claimed.

Confirm that no other server block on the host claims `discovery.endeavouros.com`. Two server
blocks claiming one name are resolved by include order rather than by intent, and the loser
fails silently. Nothing else serves the dated permalinks, so until `nginx-redirects.conf` is
installed they return 404, which was the state found on 2026-10-04.

Then the usual:

    sudo nginx -t && sudo systemctl reload nginx

#### Verify the deploy

    base=https://discovery.endeavouros.com
    curl -sS -D - -o /dev/null "$base/"
    curl -sS -D - -o /dev/null "$base/applications/firewalld/2022/03/"
    curl -sS -D - -o /dev/null "$base/applications/firewalld/2022/03?utm_source=deploy-check"
    curl -sS -D - -o /dev/null "$base/video-tutorials/back-up/2021/04/"
    asset=$(curl -fsS "$base/" | grep -o '/_astro/[^"]*' | head -1)
    curl -sS -D - -o /dev/null "$base$asset"
    curl -fsS "$base/robots.txt"

Expected results:

- `/` is 200 with `Content-Security-Policy`, `Strict-Transport-Security`,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and
  `Cross-Origin-Opener-Policy`, and no `X-Robots-Tag`.
- Both firewalld forms are 301 to `/firewalld/`, and the retired permalink is 301 to
  `/article-removed/`.
- The asset is 200 with the same seven headers and
  `Cache-Control: public, max-age=31536000, immutable`.
- `robots.txt` allows `/` and names the sitemap.

The asset is checked separately because nginx's `add_header` in a location replaces the
inherited header set.

### What CI does

`.github/workflows/check.yml` runs on every push to `main` and every pull request: `npm ci`,
`npm run build`, `make links`, `make check`, then `git diff --exit-code
deploy/nginx-csp.conf` and the same check over `deploy/nginx-redirects.conf`, and
`make emphasis` over the built pages. The redirect map's diff alone would always pass there,
because the export it is generated from is not on the runner, so CI also runs
`scripts/gen-redirects.py --check`: no key appears twice and every target is an article
that exists. What it cannot see is a permalink deleted from the committed map — the
remaining lines all still resolve. It publishes nothing. `.github/workflows/build.yml` is
the one that publishes, and a `v*` tag or a manual dispatch starts it — see "Cutting and
rebuilding a release".

It is also what makes the wiki editable by people who do not run the toolchain. An article
is a Markdown file that can be edited in the GitHub web UI, and that only holds if something
builds and link-checks the result on their behalf.

### After launch

The wiki was confirmed on 2026-10-04 serving release `v2026.09.20` unchanged. It holds 93 of
Discovery's 102 published articles; "What is not here" names the nine that were left out and why.

What launch needed from this repository is in it: `astro/src/pages/robots.txt.ts` writes a
`robots.txt` that names Starlight's `sitemap-index.xml` once `PUBLIC_INDEXABLE` is set,
`.github/workflows/build.yml` sets that flag and refuses to publish a build that does not
honour it, `deploy/nginx-production.conf` is the intended production config — without the
preview's `X-Robots-Tag` — and `deploy/nginx-redirects.conf` maps 104 old WordPress
permalinks onto their articles here.

What the server still lacked when it was probed from outside on 2026-10-04 — the content
was right, byte for byte, and the config around it was not the one in `deploy/`:

- **The redirect map is not installed.** Every old WordPress permalink is a 404, which is
  every link to the wiki the forum and the search engines hold. It needs
  `nginx-redirects.conf` included at http level and the `if ($discovery_redirect)` line in
  the server block.
- **No Content-Security-Policy header is sent**, on any page. It needs `nginx-csp.conf`
  included in the server block.
- **`/_astro/` sends two headers of seven.** `Cache-Control` and `X-Content-Type-Options`
  arrive; the CSP and the other four do not. The `location /_astro/` block in the config
  repeats the whole set for the reason given under "Verify the deploy".
- **The verify link is released but not confirmed installed.** The main site's download
  page links `/how-to-check-and-trust-key-and-signature-for-the-endeavouros-iso/` here as
  of its `v2026.10.03`; whether that release is on the server is not known from here.
- **Category URLs are unhandled** — see "What is not here".

"Verify the deploy" is the check that closes the first three. The `CONFIRM` lines in
`deploy/nginx-production.conf` remain the checklist for this host or any later one.
