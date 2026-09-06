# The Discovery wiki: a Starlight site in astro/, the importer that lifts its
# articles out of the WordPress install, and the nginx config the preview host
# serves the build with. The main site lives in its own repository.

.PHONY: check links dev-astro build-astro build verify serve deploy-preview clean convert

# astro check over the components and the content collections.
check:
	@cd astro && npm run check

# A link to a page that does not exist is invisible in review and only shows up
# when someone clicks. Needs a build in astro/dist to check against.
links:
	@python3 scripts/check-links.py

dev-astro:
	@cd astro && npm run dev

build-astro:
	@cd astro && npm run build

build: build-astro

# The build regenerates deploy/nginx-csp.conf from the real dist/. This is the
# drift gate CI runs: a diff here means the committed snippet no longer matches
# the pages, and the fix is to commit the regenerated one.
verify: build
	@git diff --exit-code deploy/nginx-csp.conf

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

# Import an article from WordPress:  make convert SLUGS="pacman-basic-commands"
convert:
	@python3 scripts/convert-wp.py $(SLUGS)
