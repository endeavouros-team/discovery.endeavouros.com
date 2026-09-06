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

A new article also needs a sidebar entry in `astro/astro.config.mjs`. Nothing is
derived from the file tree. `make convert SLUGS="the-slug"` imports one from the
WordPress install; the README covers what that does and does not rewrite.

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
