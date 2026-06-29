# Changelog

All notable changes to the **habitat** skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this skill adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-06-28
### Changed
- Documentation pass across `SKILL.md` and the references: removed build-process history,
  status/test-count boasts, and internal project jargon (Bet/F-codes, UC labels); tightened
  language for clarity and concision. No functional changes.

## [1.0.0] - 2026-06-22
### Added
- First packaged release of Habitat as a Solytus single-skill plugin.
- Tier-1/2/3 architecture: generic skill logic ships here; instance config lives in
  `~/.solytus/habitat/config.yaml`; instance data lives in a user-chosen data root
  (default `~/.solytus/habitat/data`), discovered via `scripts/config.py`
  (`HABITAT_DATA_ROOT` env → config → default).
- US cached adapters (climate, cost, safety, air quality, dynamism, social) plus an
  international country-grain backbone (World Bank), all with graceful degradation when
  optional API keys are absent.
- Utility lookups (family distance, internet, airport, walkability, hazard) and a
  gem-finder over a bundled gazetteer.
- Config schema versioning (`version: 1`) with a forward-only migration check, an optional
  `tenant_id`, and a mock-MCP readiness layer.
- Opt-in propose-improvement workflow plus issue/PR templates.
- 241 stdlib-only tests (1 skipped).
