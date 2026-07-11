# Exporting

Render a report / checklist / guide to a shareable Markdown file via
`scripts/export.py`. Exports leave the home-private data root, so **VIN/plate are
redacted by default** (`render_markdown(..., redact=True)`); pass `redact=False` only for
a packet that genuinely needs identity (a sale-records or registration sheet). A header
disclaimer rides every export, and the PII guard (`scripts/redact.assert_no_pii`) is the
structural backstop.

Common exports (compose the body Markdown, then render):
- **Pre-trip / pre-wheeling checklist** — what's due + a fluids/pressures/torque quick-card.
- **Sell sheet** — the full service history + money spent (use `redact=False` to *show* the
  VIN so a buyer can match the records to the truck).
- **Job torque sheet** — every torque spec for the items in a planned job, on one card,
  each with its source/tier and the verify-before-final-torque note.

Carry tier / estimate / source into any exported safety number — a bare safety-critical
value with no provenance shouldn't leave in a sheet someone will torque to. Write with
`export.write_export(body, vehicle, kind=…, title=…, out_dir=<data_root>/exports)`.
Markdown is the portable artifact; print to PDF from a browser if a paper copy is needed.
