// Build-time skill discovery — the single source that makes the site regenerate
// from the repo. Reads every plugins/<name>/ and returns its manifest + skill body
// + editorial + changelog. Adding a new plugin requires ZERO edits here or anywhere
// in site/.
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
 * Minimal frontmatter reader for plugins/<skill>/overview.md.
 * Parses simple single-line `key: value` pairs from the leading `---` fence
 * (value = rest of line, so colons survive; surrounding quotes stripped). Editorial
 * frontmatter values are single-line by convention — no block scalars needed. Returns
 * { data, body }; body is the markdown after the fence.
 */
function parseOverview(raw) {
  const m = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) return { data: {}, body: raw.trim() };
  const data = {};
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^([A-Za-z][\w-]*):\s*(.*)$/);
    if (!kv) continue;
    let v = kv[2].trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    data[kv[1]] = v;
  }
  return { data, body: m[2].trim() };
}

/** Every dated release in a Keep-a-Changelog file: `## [x.y.z] - YYYY-MM-DD`,
 *  newest first (file order). Skips an undated `## [Unreleased]` heading. */
function parseReleases(changelog) {
  const out = [];
  for (const m of changelog.matchAll(/^##\s*\[([^\]]+)\]\s*-\s*(\d{4}-\d{2}-\d{2})/gm)) {
    out.push({ version: m[1], date: m[2] });
  }
  return out;
}

/**
 * @returns {Array<{name:string,version:string,description:string,homepage:string,
 *   license:string,skillBody:string,changelog:string,tagline:string,
 *   cardDescription:string,seoJob:string,overviewBody:string,releases:Array<{version:string,date:string}>,
 *   latestVersion:string,latestDate:string}>}
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
    const description = manifest.description || '';
    const skillMdPath = join(pdir, 'skills', name, 'SKILL.md');
    const changelogPath = join(pdir, 'CHANGELOG.md');
    const overviewPath = join(pdir, 'overview.md');

    // Per-skill editorial — kept OUT of SKILL.md so the runtime skill file isn't
    // bloated with marketing copy. Absent overview.md degrades gracefully.
    let tagline = '';
    let cardDescription = description;
    let seoJob = ''; // short job phrase for the SEO <title>; falls back to tagline
    let overviewBody = '';
    if (existsSync(overviewPath)) {
      const { data, body } = parseOverview(readFileSync(overviewPath, 'utf8'));
      tagline = data.tagline || '';
      cardDescription = data.cardDescription || description;
      seoJob = data.seoJob || '';
      overviewBody = body;
    }

    const changelog = existsSync(changelogPath)
      ? readFileSync(changelogPath, 'utf8')
      : '';
    const releases = parseReleases(changelog);
    const rel = releases[0] || null;

    out.push({
      name,
      version: manifest.version || '0.0.0',
      description,
      homepage: manifest.homepage || '',
      license: manifest.license || '',
      skillBody: existsSync(skillMdPath)
        ? stripFrontmatter(readFileSync(skillMdPath, 'utf8'))
        : '',
      changelog,
      tagline,
      cardDescription,
      seoJob,
      overviewBody,
      releases,
      latestVersion: rel ? rel.version : manifest.version || '0.0.0',
      latestDate: rel ? rel.date : '',
    });
  }
  out.sort((a, b) => a.name.localeCompare(b.name));
  return out;
}
