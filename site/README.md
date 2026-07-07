# Solytus site

The solytus.com static site, built with [Astro](https://astro.build). Per-skill
pages and changelogs are **generated from the repo at build time** — they are
never hand-edited, so the site can't drift from what's released.

## How generation works

`src/lib/skills.mjs` discovers every `../plugins/<name>/` and reads its
`plugin.json` (version, description), its skill `SKILL.md` (usage), its
`CHANGELOG.md`, and an optional `overview.md` (editorial tagline + copy). That one
module feeds:

- the landing catalog (`src/pages/index.astro`),
- a page per skill (`src/pages/skills/[name].astro`).

Adding a new skill to `plugins/` requires **zero** edits here.

## Discoverability (SEO + AI)

Every page's `<head>` is built in `src/layouts/Layout.astro`: unique title +
description, canonical, Open Graph + Twitter card, icons, and a JSON-LD block.
Structured data and the title helpers live in `src/lib/seo.mjs` — the homepage
emits `WebSite` + `Organization` + `Person` (one `sameAs` identity graph), and
each skill page emits `SoftwareApplication` + `BreadcrumbList`.

- `@astrojs/sitemap` emits `/sitemap-index.xml` at build time.
- `public/robots.txt` is author-owned: it allows AI *search* crawlers
  (OAI-SearchBot, Claude-SearchBot, PerplexityBot, …) for citation eligibility
  and blocks *training* crawlers (GPTBot, ClaudeBot, Google-Extended, …).
- `public/` also holds the favicon set, `site.webmanifest`, and `og-default.png`
  (the social share card).

> Cloudflare note: for `public/robots.txt` to be served, Cloudflare's *managed*
> robots.txt (AI Crawl Control) must be off for the zone, or its policy aligned to
> match. Web Analytics is enabled at the Cloudflare dashboard (no code).

## Develop / build

```bash
cd site
npm install
npm run dev       # local preview at http://localhost:4321
npm run build     # static output to site/dist
npm run preview   # serve the built output
```

> Requires Node 20+ (pinned in `.nvmrc`). Key deps: `astro ^5.6`,
> `@astrojs/sitemap ^3.7`, `marked ^14`.

## Deploy — Cloudflare Pages

Connect the **public** repo to Cloudflare Pages with:

| Setting | Value |
| --- | --- |
| Framework preset | Astro |
| Root directory | `site` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Node version | `20` (or newer) |

Because a release lands on the public repo's `main` as a fresh snapshot, Pages
rebuilds automatically on that push and the new version/changelog appear with no
extra wiring. `dist/` and `.astro/` are gitignored at the repo root.

## Two things to set

1. **Public repo slug** — `GITHUB_OWNER_REPO` in `src/config.mjs` (the only place
   it appears).
2. **Devlog (gated)** — the build-in-public devlog is intentionally not built yet.
   To go live, add a plain Astro route under `src/pages/devlog/`. Nothing else
   needs wiring.
