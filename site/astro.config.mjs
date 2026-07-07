// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Plain static Astro site (no Starlight). The home catalog and per-skill pages are
// generated from the repo at build time by src/lib/skills.mjs — adding a skill needs
// no edits here or anywhere in site/. `astro build` emits static HTML to site/dist.
//
// ── GATE: build-in-public devlog ─────────────────────────────────────────────
// The devlog is intentionally NOT built until there is a real-usage signal. It was
// previously stubbed as a Starlight `autogenerate` sidebar entry; with Starlight
// removed, going live means adding a plain Astro route (e.g. src/pages/devlog/) — a
// deliberate, separate step. Nothing else here depends on it.
// ─────────────────────────────────────────────────────────────────────────────

export default defineConfig({
  site: 'https://solytus.com',
  // Emits /sitemap-index.xml + /sitemap-0.xml at build time from the static routes
  // (home + every /skills/<name>/). Referenced from public/robots.txt.
  integrations: [sitemap()],
});
