// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import sidebar from './sidebar.json' with { type: 'json' };

export default defineConfig({
  site: 'https://discovery.endeavouros.com',
  integrations: [
    starlight({
      title: 'Discovery',
      description: 'The EndeavourOS wiki.',
      // Starlight renders the logo with <img>, and currentColor does not cross
      // into an <img>-referenced SVG, so the wordmark cannot follow the theme
      // the way it does on the main site. Two baked variants instead.
      logo: {
        light: './src/assets/logo-light.svg',
        dark: './src/assets/logo-dark.svg',
        replacesTitle: true,
      },
      favicon: '/favicon.svg',
      customCss: ['./src/styles/brand.css'],
      // Unset until launch, same as the main site: an indexed preview would
      // compete with the live wiki in search.
      head: process.env.PUBLIC_INDEXABLE === 'true' ? [] : [
        { tag: 'meta', attrs: { name: 'robots', content: 'noindex, nofollow' } },
      ],
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/endeavouros-team' },
        { icon: 'discourse', label: 'Forum', href: 'https://forum.endeavouros.com' },
      ],
      // Discovery's articles carry no hierarchy, so the sidebar cannot be
      // derived from the file tree. sidebar.json is hand-authored, from Joe
      // Kamprad's menu plan of 2026-09-07: nine sections, the subgroups
      // collapsed. Nothing generates it -- `make convert` only checks that
      // every published article appears in it exactly once -- so a new article
      // is added to that file by hand or it is unreachable.
      sidebar,
      pagination: false,
      // The date comes from each article's `lastUpdated` frontmatter, which the
      // importer takes from WordPress's modified date. Left to itself Starlight
      // reads git, where every article was last touched by the import.
      lastUpdated: true,
    }),
  ],
  // Astro's native security.csp is deliberately NOT used here: it only hashes
  // scripts that pass through its own pipeline, so the six that Starlight writes
  // directly into the HTML end up blocked by the policy Astro emitted. The CSP is
  // generated from the built output instead - see scripts/gen-csp.mjs - which
  // cannot miss anything, and is delivered as a header so frame-ancestors works.

  build: { inlineStylesheets: 'never' },
  devToolbar: { enabled: false },
});
