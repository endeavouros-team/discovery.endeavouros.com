# Contributing

A change gets in through a pull request against `main`. CI
(`.github/workflows/check.yml`) runs on the pull request, and a maintainer
merges it. Merging publishes nothing — there is no release workflow, and the
preview host is updated by hand with `make deploy-preview`.

## Editing an article

Articles are `.mdx` files under `astro/src/content/docs/`. Starlight needs two
frontmatter fields, `title` and `description`; the description is what search
results and link previews show, so it is not decoration. Code fences take a
language — `bash` and `ini` are what the importer infers — which is what the
highlighting and the copy button work from.

`make convert SLUGS="the-slug"` re-imports one article from the WordPress
export and `make convert` re-imports all 93. The export lives outside the
repository and its location is the `EXPORT` variable in the Makefile. A run ends
with a list of what it could not do, and that list is the part to read; the
README covers what it rewrites and what it drops.

## Adding an article

Nothing is derived from the file tree, so an article missing from the sidebar is
reachable by search and by nothing else. Three steps:

1. Write `astro/src/content/docs/<slug>.mdx` — or `make convert
   SLUGS="<slug>"`, if it is in the WordPress export — with `title`,
   `description`, and `lastUpdated: YYYY-MM-DD` if you know when the content was
   last revised.
2. Add `{ "slug": "<slug>" }` to the group it belongs in, in
   `astro/sidebar.json`. That file is hand-authored; `make convert` checks it
   but never writes it, and `astro/astro.config.mjs` imports it.
3. `make check`.

An article in no group, a slug listed twice, or a slug whose `.mdx` is gone
comes out under `sidebar` in the warning list at the end of a `make convert`
run. That check is the only thing standing between a new article and silence.

## Before you commit

- `make verify` before anything that changes build output. It builds, then fails
  if `deploy/nginx-csp.conf` no longer matches what the build produced.
- `make links` after `make verify`. It checks every internal link and same-page
  anchor in the build, which is the one error that is invisible in review: the
  markup looks right, the build succeeds, and the 404 shows up when a reader
  clicks. CI runs it too.
- `make check` if you touched a component or the content config. It is
  `astro check` over the Astro sources and the content collections.

## What CI does

Every push to `main` and every pull request runs `.github/workflows/check.yml`:
`npm ci`, `npm run build` — the lockfile audit, the Astro build, then the CSP
generation — `make links`, `make check`, and a diff check on
`deploy/nginx-csp.conf`. It publishes nothing.

## Commit messages

Lowercase `area: summary` subject, imperative mood, wrapped at 76 columns, and a
body that explains *why* rather than restating the diff. `git log -3` is the
reference.

## Two things that fail silently

Both look like success and are expensive to miss.

- **`PUBLIC_INDEXABLE=true` is required for a production build.** Without it
  every page ships `<meta name="robots" content="noindex, nofollow">`. The build
  succeeds, the site looks perfect, and search engines are told to ignore it.
  The flag is unset by default so that preview builds cannot compete with the
  live wiki, which means it can only ever be forgotten.
- **`deploy/nginx-csp.conf` is generated, and it goes stale.** Change an inline
  script — a component edit, a Starlight upgrade — and the build rewrites it.
  `make verify` and CI both end with `git diff --exit-code
  deploy/nginx-csp.conf`, which prints the diff of hashes and exits 1. The fix
  is to commit the regenerated file, never to edit it: the next build overwrites
  anything typed in by hand, and a snippet that has drifted sends the preview
  host a policy that blocks scripts the pages actually load.
