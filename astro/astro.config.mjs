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
      // Discovery's 102 articles carry flat categories and no hierarchy, so the
      // sidebar cannot be derived from the file tree. sidebar.json is generated
      // from the WordPress categories by scripts/convert-wp.py, as a starting
      // point rather than an answer: which groups, in what order and what gets
      // promoted is a content decision for the team, and re-authoring this by
      // hand is what closes it.
      sidebar,
      pagination: false,
      lastUpdated: false,
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
