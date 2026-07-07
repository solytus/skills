// Structured-data (JSON-LD) + title helpers for the site's <head>.
//
// Builders return schema.org *nodes* with no `@context` — Layout.astro wraps a
// page's nodes in a single `{ "@context": …, "@graph": [...] }` block. Nodes
// cross-reference by stable `@id`, so Google and AI answer engines resolve one
// consistent Organization / Person / WebSite entity across every page.
import {
  SITE_URL,
  SITE_NAME,
  SITE_DESCRIPTION,
  AUTHOR,
  SAME_AS,
  DEFAULT_OG_IMAGE,
  GITHUB_OWNER_REPO,
} from '../config.mjs';

const abs = (path) => new URL(path, SITE_URL).href;

// Stable entity anchors reused across pages.
export const ORG_ID = `${SITE_URL}/#organization`;
export const SITE_ID = `${SITE_URL}/#website`;
export const PERSON_ID = `${SITE_URL}/#person`;

// SPDX id → canonical license URL (Google prefers a URL over a bare id).
const LICENSE_URL = { MIT: 'https://spdx.org/licenses/MIT.html' };

export const titleCase = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/**
 * Per-skill browser/SERP <title>. Prefers a hand-set job phrase (overview.md
 * `seoJob:`), falling back to the tagline, then to just the brand.
 *   "Habitat — find & track places to live | Solytus"
 */
export function skillTitle(skill) {
  const display = titleCase(skill.name);
  const phrase = (skill.seoJob || skill.tagline || '').trim();
  return phrase ? `${display} — ${phrase} | ${SITE_NAME}` : `${display} — ${SITE_NAME}`;
}

export function personSchema() {
  return {
    '@type': 'Person',
    '@id': PERSON_ID,
    name: AUTHOR,
    url: SITE_URL,
    sameAs: SAME_AS,
  };
}

export function organizationSchema() {
  return {
    '@type': 'Organization',
    '@id': ORG_ID,
    name: SITE_NAME,
    url: SITE_URL,
    description: SITE_DESCRIPTION,
    logo: abs('/icon-512.png'),
    image: abs(DEFAULT_OG_IMAGE),
    sameAs: SAME_AS,
    founder: { '@id': PERSON_ID },
  };
}

export function websiteSchema() {
  return {
    '@type': 'WebSite',
    '@id': SITE_ID,
    name: SITE_NAME,
    url: SITE_URL,
    description: SITE_DESCRIPTION,
    publisher: { '@id': ORG_ID },
  };
}

/**
 * SoftwareApplication node for a skill detail page. `pageUrl` is the page's
 * absolute canonical URL. Dates come from the skill's dated changelog releases
 * (newest first): oldest = datePublished, newest = dateModified.
 */
export function softwareApplicationSchema(skill, pageUrl) {
  const repoUrl = `https://github.com/${GITHUB_OWNER_REPO}/tree/main/plugins/${skill.name}`;
  const node = {
    '@type': 'SoftwareApplication',
    '@id': `${pageUrl}#software`,
    name: titleCase(skill.name),
    url: pageUrl,
    description: skill.description || skill.cardDescription || '',
    applicationCategory: 'DeveloperApplication',
    operatingSystem: 'Claude Code',
    softwareVersion: skill.latestVersion,
    isAccessibleForFree: true,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
    author: { '@id': PERSON_ID },
    publisher: { '@id': ORG_ID },
    codeRepository: repoUrl,
  };
  if (skill.license) node.license = LICENSE_URL[skill.license] || skill.license;
  const rels = skill.releases || [];
  if (rels.length) {
    node.dateModified = rels[0].date;
    node.datePublished = rels[rels.length - 1].date;
  } else if (skill.latestDate) {
    node.datePublished = skill.latestDate;
  }
  return node;
}

/** BreadcrumbList from [{ name, url? }]; omit `url` on the current (last) item. */
export function breadcrumbSchema(items) {
  return {
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      ...(it.url ? { item: it.url } : {}),
    })),
  };
}
