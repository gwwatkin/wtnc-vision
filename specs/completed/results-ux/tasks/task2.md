# Task 2 — CSV parser (Wave 1, parallel) · sonnet

Implement `parseCsv` in `web/csv.js`. Depends only on the Wave-0 scaffold.

## Exclusive file
- `web/csv.js` (implement; do not touch other files)

## Contract (design §5.1)
```js
export function parseCsv(text /*: string */) /*: string[][] */
```

## Requirements
- RFC4180-ish: fields separated by `,`, rows by newline; handle **`\r\n` and `\n`**.
- **Quoted fields**: `"..."` may contain commas, newlines, and escaped quotes (`""` → `"`).
- Trim nothing inside quotes; unquoted fields are taken verbatim (callers trim/convert).
- **Skip blank lines** (a line that is empty or whitespace-only produces no row).
- Do **not** interpret a header row — return every data row as `string[]`.
- Never throw on ragged input; return whatever parses (NFR4). Empty input → `[]`.

## Acceptance
- `parseCsv('412,"George Watkins","Cat 3"')` → `[["412","George Watkins","Cat 3"]]`.
- A quoted field containing a comma stays one field.
- `""` inside a quoted field decodes to a single `"`.
- CRLF file and trailing newline both parse without empty phantom rows.
- Include a short self-check (comment or tiny inline assertions) covering the above; no
  test framework.
