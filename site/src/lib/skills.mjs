// Build-time skill discovery — the single source that makes the site regenerate
// from the repo. Reads every plugins/<name>/ and returns its manifest + skill body
// + changelog. Adding a new plugin requires ZERO edits here or anywhere in site/.
//
// Resolution is anchored to this file's location (import.meta.url), so it works
// the same whether called from astro.config.mjs or from a page, regardless of cwd.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url)); // site/src/lib
const REPO_ROOT = resolve(here, '../../..'); // -> repo root (parent of site/)
const PLUGINS_DIR = join(REPO_ROOT, 'plugins');

/** Strip leading YAML frontmatter, return the markdown body. */
function stripFrontmatter(raw) {
  const m = raw.match(/^---\n[\s\S]*?\n---\n?([\s\S]*)$/);
  return m ? m[1] : raw;
}

/**
 * @returns {Array<{name:string,version:string,description:string,homepage:string,
 *   license:string,skillBody:string,changelog:string}>}
 */
export function getSkills() {
  if (!existsSync(PLUGINS_DIR)) return [];
  const out = [];
  for (const entry of readdirSync(PLUGINS_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    if (entry.name.startsWith('_')) continue; // skip _template, etc.
    const pdir = join(PLUGINS_DIR, entry.name);
    const manifestPath = join(pdir, '.claude-plugin', 'plugin.json');
    if (!existsSync(manifestPath)) continue;
    let manifest;
    try {
      manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    } catch {
      continue; // a malformed manifest shouldn't take the whole site down
    }
    const name = manifest.name || entry.name;
    const skillMdPath = join(pdir, 'skills', name, 'SKILL.md');
    const changelogPath = join(pdir, 'CHANGELOG.md');
    out.push({
      name,
      version: manifest.version || '0.0.0',
      description: manifest.description || '',
      homepage: manifest.homepage || '',
      license: manifest.license || '',
      skillBody: existsSync(skillMdPath)
        ? stripFrontmatter(readFileSync(skillMdPath, 'utf8'))
        : '',
      changelog: existsSync(changelogPath)
        ? readFileSync(changelogPath, 'utf8')
        : '',
    });
  }
  out.sort((a, b) => a.name.localeCompare(b.name));
  return out;
}
