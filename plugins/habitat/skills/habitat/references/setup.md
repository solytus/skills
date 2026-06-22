# First-run setup

Run this once when a user installs Habitat (no `~/.solytus/habitat/config.yaml` yet). It's a
short, guided flow — walk the user through it conversationally; don't dump commands.

## 1. Instance config (Tier-2)

```bash
mkdir -p ~/.solytus/habitat
cp config.example.yaml ~/.solytus/habitat/config.yaml
```

Ask the user where they want their data to live (default `~/.solytus/habitat/data`) and set
`data_root:` in that file. Then confirm discovery works:

```bash
python3 scripts/config.py        # should print the resolved data_root, tenant_id, version
```

## 2. Data root scaffold (Tier-3)

Create the user's data tree from the bundled example (which contains **no** personal data):

```bash
cp -r examples/data-root/. "$(python3 scripts/config.py | python3 -c 'import sys,json;print(json.load(sys.stdin)["data_root"])')"
```

Then run a short preference interview (`references/interview.md`) to replace the placeholder
profile with the user's own. Edit `<data_root>/profile/config.yaml` for family locations,
home currency, and (optionally) an immigration profile.

## 3. API keys (Tier-2 secrets — optional but recommended)

```bash
cp secrets.env.example ~/.solytus/habitat/secrets.env   # Tier-2; gitignored, never commit
```

Register the free-tier keys following `references/api-keys-guide.md` and fill them in. Keys are
**optional-tiered**: every adapter degrades gracefully without its key (returns `unavailable`,
never fabricated). Verify what's live:

```bash
set -a && . ./secrets.env && set +a
python3 scripts/verify_keys.py          # OK / FAIL / SKIP per key
```

## 4. You're set

Invoke by name ("Habitat, evaluate Boise"). The skill resolves the data root on each run via
`scripts/config.py` and passes it to every script as `--data-root`.
