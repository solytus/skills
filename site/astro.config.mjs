// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { getSkills } from './src/lib/skills.mjs';

// Sidebar is built from the repo's plugins at build time — adding a skill needs
// no edits here.
const skills = getSkills();

export default defineConfig({
  site: 'https://solytus.com',
  integrations: [
    starlight({
      title: 'Solytus',
      description: 'Productized Claude Code skills — install them, point them at your own data, make them yours.',
      sidebar: [
        {
          label: 'Skills',
          items: skills.map((s) => ({
            label: `${s.name} (v${s.version})`,
            link: `/skills/${s.name}/`,
          })),
        },
        {
          label: 'About',
          items: [{ label: 'The Solytus pattern', link: '/the-pattern/' }],
        },
        // ── GATE ────────────────────────────────────────────────────────────
        // The build-in-public devlog is intentionally NOT built until there is a
        // real-usage signal. The pipeline is ready: to go live, drop markdown into
        // src/content/docs/devlog/ and uncomment the next line. Nothing else.
        // { label: 'Devlog', autogenerate: { directory: 'devlog' } },
        // ────────────────────────────────────────────────────────────────────
      ],
    }),
  ],
});
