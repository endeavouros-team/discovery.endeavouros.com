import type { APIRoute } from 'astro';

// Mirrors the noindex meta in astro.config.mjs. Until PUBLIC_INDEXABLE is set
// for launch, this build refuses crawlers outright so it cannot compete with
// the WordPress install it replaces -- or, after the cutover, with itself on a
// preview host.
//
// Starlight writes the sitemap without being asked and names it
// sitemap-index.xml; nothing pointed a crawler at it before this file existed.
export const GET: APIRoute = ({ site }) => {
  const indexable = import.meta.env.PUBLIC_INDEXABLE === 'true';
  const body = indexable
    ? `User-agent: *\nAllow: /\nSitemap: ${new URL('sitemap-index.xml', site)}\n`
    : `User-agent: *\nDisallow: /\n`;
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
