# The Discovery wiki: a Starlight site in astro/, the importer that lifts its
# articles out of the WordPress install, and the nginx config the preview host
# serves the build with. The main site lives in its own repository.

.PHONY: check links emphasis dev-astro build-astro build verify serve deploy-preview clean convert redirects

# astro check over the components and the content collections.
check:
	@cd astro && npm run check

# A link to a page that does not exist is invisible in review and only shows up
# when someone clicks. Needs a build in astro/dist to check against.
links:
	@python3 scripts/check-links.py

# `**text **` is not bold, it is four asterisks on the page, and the .mdx of one
# reads exactly like emphasis that works. Needs a build, for the same reason
# links does: only the rendered page says which it was.
emphasis:
	@python3 scripts/check-emphasis.py

dev-astro:
	@cd astro && npm run dev

build-astro:
	@cd astro && npm run build

build: build-astro

# The build regenerates deploy/nginx-csp.conf from the real dist/. This is the
# drift gate CI runs: a diff here means the committed snippet no longer matches
# the pages, and the fix is to commit the regenerated one.
#
# The redirect map is gated the same way, with one difference: it is generated
# from the export, which is not in the repository and is not on the CI runner,
# so nothing regenerates it here. --check is the half of the gate that works
# without the export -- every target in the committed map must still be an
# article that exists -- and the diff catches a map generated but not committed.
verify: build
	@git diff --exit-code deploy/nginx-csp.conf
	@python3 scripts/gen-redirects.py --check
	@git diff --exit-code deploy/nginx-redirects.conf

# Preview the build on the LAN/tailnet for team review.
serve:
	@test -d astro/dist || { echo "  no astro/dist — run make build first"; exit 1; }
	@echo "  wiki -> http://$$(hostname):8813"
	@(cd astro/dist && python3 -m http.server 8813 --bind 0.0.0.0 >/dev/null 2>&1 &) ; \
	 echo "  serving; stop with: pkill -f 'http.server 8813'"

# Publish to the always-on preview host.
deploy-preview:
	@scripts/deploy-preview.sh

clean:
	@rm -rf astro/dist astro/.astro

# Import from the WordPress export: every published article, or only the ones
# named in SLUGS="gaming-101 i3-wm". The export is a plain directory beside the
# repositories and never inside one -- it carries drafts, private posts and
# author email addresses -- so its location is a variable, not a path in git.
EXPORT ?= $(HOME)/Documents/code/discovery-export
WXR ?= $(EXPORT)/posts-discovery.WordPress.2026-09-06.xml
UPLOADS ?= $(EXPORT)/backup_2026-09-06-1841_Discovery_66fa0c6f4f7d-uploads.zip

convert:
	@python3 scripts/convert-wp.py --wxr "$(WXR)" --uploads "$(UPLOADS)" $(SLUGS)

# Regenerate deploy/nginx-redirects.conf from the same export. Needs the export
# for the permalinks; commit the result, which is what `make verify` and CI
# check against.
redirects:
	@python3 scripts/gen-redirects.py --wxr "$(WXR)"
