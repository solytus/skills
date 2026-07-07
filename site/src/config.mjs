// ──────────────────────────────────────────────────────────────────────────
// The public repo slug (owner/repo). The ONLY place it appears.
export const GITHUB_OWNER_REPO = 'solytus/skills';
// ──────────────────────────────────────────────────────────────────────────

export const MARKETPLACE_NAME = 'solytus';
export const SITE_URL = 'https://solytus.com';
export const SITE_NAME = 'Solytus';
export const AUTHOR = 'Sean Park';

// One canonical description, reused as the homepage <meta> default and in the
// site's structured data so search and AI engines see a single consistent line.
export const SITE_DESCRIPTION =
  'Solytus is an umbrella for things I build and open up — currently productized Claude Code skills. Install-first, open source, yours to keep.';

// Footer contact (intentionally public — solytus@gmail.com is allowlisted in
// tooling/scan_pii.py). The GitHub org link is derived from GITHUB_OWNER_REPO.
export const CONTACT_EMAIL = 'solytus@gmail.com';
export const LINKEDIN_URL = 'https://www.linkedin.com/in/solytus/';
export const GITHUB_OWNER = GITHUB_OWNER_REPO.split('/')[0];
export const GITHUB_ORG_URL = `https://github.com/${GITHUB_OWNER}`;

// Default social-share image (Open Graph / Twitter). Absolute URL built at use.
export const DEFAULT_OG_IMAGE = '/og-default.png';

// Identity graph (schema.org `sameAs`): the public profiles that are the same
// entity as Solytus / Sean, so search + AI can resolve one consistent identity.
export const SAME_AS = [GITHUB_ORG_URL, LINKEDIN_URL];
