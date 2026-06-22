import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

// The `docs` collection powers Starlight's themed pages (the /the-pattern page
// today, and the gated devlog later). Per-skill pages + changelogs are NOT in a
// collection — they are generated directly from plugins/* by src/lib/skills.mjs.
export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
};
