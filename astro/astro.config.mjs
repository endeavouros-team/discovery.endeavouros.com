// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

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
      // Discovery's 102 articles carry 32 flat categories and no hierarchy, so
      // the sidebar has to be authored rather than derived from the file tree.
      // This is the demo subset; the full mapping is a decision for the team.
      sidebar: [
        {
          label: 'Package management',
          items: [{ slug: 'pacman-basic-commands' }],
        },
        {
          label: 'Storage and partitions',
          items: [{ slug: 'adding-swap-after-installation' }],
        },
        {
          label: 'Gaming',
          items: [{ slug: 'gaming-101' }],
        },
      ],
      pagination: false,
      lastUpdated: false,
    }),
  ],
  // Starlight emits ~40 inline scripts per build (theme provider, search modal,
  // sidebar state), which makes a hand-maintained hash allowlist impractical -
  // the main site's approach does not scale here. Astro generates the hashes
  // itself and emits a per-page CSP meta tag, so the policy stays strict with
  // no 'unsafe-inline' and nothing to keep in sync by hand.
  security: {
    csp: {
      algorithm: 'SHA-256',
      directives: [
        "default-src 'self'",
        "img-src 'self' data: https://discovery.endeavouros.com",
        "font-src 'self'",
        "frame-src https://www.youtube-nocookie.com",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "object-src 'none'",
      ],
    },
  },

  build: { inlineStylesheets: 'never' },
  devToolbar: { enabled: false },
});
