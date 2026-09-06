#!/usr/bin/env node
/**
 * Supply-chain gate. The lockfile is the attack surface, so assert its shape
 * before any dependency code is allowed to run.
 *
 * A package that wants to execute an install script, resolves off-registry, or
 * ships without an integrity hash cannot land without a human editing the
 * allowlist below in a reviewable diff. That is the control the WordPress
 * plugin system never had.
 */
import { readFileSync } from 'node:fs';

/** Packages permitted to execute code at install time, each with a reason. */
const ALLOW_INSTALL_SCRIPTS = new Map([
  ['node_modules/esbuild', 'links the prebuilt platform binary; resolves via optionalDependencies, so --ignore-scripts is fine'],
  ['node_modules/fsevents', 'darwin-only optional dep of chokidar; never installed on Linux CI'],
]);

const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
const fails = [];

if ((lock.lockfileVersion ?? 0) < 3) {
  fails.push(`lockfileVersion ${lock.lockfileVersion} — regenerate with npm 9 or newer`);
}

let count = 0;
for (const [name, p] of Object.entries(lock.packages)) {
  if (!name || p.link) continue;
  count++;

  if (!p.integrity) {
    // Optional platform packages that were not installed for this OS/arch have
    // no integrity entry of their own; they are still pinned by their parent.
    if (!p.optional) fails.push(`${name}: no integrity hash`);
  } else if (!p.integrity.startsWith('sha512-')) {
    fails.push(`${name}: weak integrity (${p.integrity.split('-')[0]})`);
  }

  if (p.hasInstallScript && !ALLOW_INSTALL_SCRIPTS.has(name)) {
    fails.push(`${name}: declares an install script and is not on the allowlist`);
  }

  if (p.resolved && !p.resolved.startsWith('https://registry.npmjs.org/')) {
    fails.push(`${name}: resolved off-registry -> ${p.resolved}`);
  }

  if (/^(git|file|link|http):/.test(p.version ?? '')) {
    fails.push(`${name}: non-registry version specifier ${p.version}`);
  }
}

if (fails.length) {
  console.error(`\n  audit-lock: ${fails.length} problem(s)\n`);
  for (const f of fails) console.error(`    ${f}`);
  console.error('');
  process.exit(1);
}

console.log(`  audit-lock ok — ${count} packages, all sha512, ${ALLOW_INSTALL_SCRIPTS.size} allowlisted install scripts`);
