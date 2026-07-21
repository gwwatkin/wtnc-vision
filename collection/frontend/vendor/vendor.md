# Vendor Provenance

| File | Package | Version | Source URL |
|------|---------|---------|------------|
| preact.module.js | preact | 10.24.3 | https://esm.sh/preact@10.24.3/es2022/preact.mjs |
| preact-hooks.module.js | preact/hooks | 10.24.3 | https://esm.sh/preact@10.24.3/es2022/hooks.mjs (import rewritten: `./preact.mjs` → `./preact.module.js`) |
| htm.module.js | htm | 3.1.1 | https://esm.sh/htm@3.1.1/es2022/htm.mjs |

## Update procedure

1. `curl -sSL <source-url> -o vendor/<file>` to replace the file.
2. For `preact-hooks.module.js`: rewrite the import line: `sed -i 's|from"./preact.mjs"|from"./preact.module.js"|g' vendor/preact-hooks.module.js`
3. Update the version and URL in this table.
4. Run `npm run check` — must stay green.
