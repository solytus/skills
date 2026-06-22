# Solytus site

The solytus.com static site. Built with [Astro](https://astro.build) +
[Starlight](https://starlight.astro.build). Per-skill pages and changelogs are
**generated from the repo at build time** — they are never hand-edited, so the
site can't drift from what's released.

## How generation works

`src/lib/skills.mjs` discovers every `../plugins/<name>/` and reads its
`plugin.json` (version, description), its skill `SKILL.md` (usage), and its
`CHANGELOG.md`. That one module feeds:

- the landing catalog (`src/pages/index.astro`),
- a page per skill (`src/pages/skills/[name].astro`),
- a changelog per skill (`src/pages/skills/[name]/changelog.astro`),
- the sidebar (`astro.config.mjs`).

Adding a new skill to `plugins/` requires **zero** edits here.

## Develop / build

```bash
cd site
npm install
npm run dev       # local preview at http://localhost:4321
npm run build     # static output to site/dist
npm run preview   # serve the built output
```

> Requires Node 20+ (and npm). Versions are pinned in `package.json`
> (`astro ^5.6`, `@astrojs/starlight ^0.34`, `marked ^14`). If a pinned minor has
> drifted by the time you install, the two API touch-points to check are the
> Starlight `sidebar` config and `marked.parse` (used with `await`, so it is safe
> whether sync or async).

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

## Two things to set before going fully live

1. **Public repo slug** — edit `GITHUB_OWNER_REPO` in `src/config.mjs` (the only
   place it appears) once the public repo exists.
2. **Devlog (gated)** — the build-in-public devlog is intentionally not built yet.
   To go live: add markdown to `src/content/docs/devlog/` and uncomment the
   `Devlog` sidebar entry in `astro.config.mjs`. Nothing else needs wiring.
