# Ingesting a document

The owner photographs the owner's manual, FSM/Haynes page, or a prior service record.
Accept one or more photos per turn.

**Reference doc → `verified-spec` events.** Extract the value + what it applies to +
the page/section. **Echo every extracted value back for the owner to confirm BEFORE
saving — vision OCR is not trusted for safety-critical numbers.** On confirmation, write
one `verified-spec` event per fact (`key` matching an existing KB key where possible so it
overrides the community value at answer time), with `source_doc` = the page citation.
Store the derived fact + citation, **not** photographed manual pages (copyright). An FSM
citation backed by this ingest can be `method: fsm-ocr` in the KB — the confabulation guard
requires an ingested doc for an official manual cite.

**Service record → `maintenance` / `baseline` events.** Extract date, mileage, work,
parts, cost; echo for confirmation; write `baseline` for pre-ownership work (before the
purchase date) or `maintenance` for the owner's own. Unknown mileage stays unknown.

Strip EXIF/GPS at capture — never store location. Then rebuild with `scripts/build_state.py`.
