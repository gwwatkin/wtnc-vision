/**
 * csv.js — RFC4180-ish CSV parser.
 * Owned exclusively by task2 for implementation; stub created in task1.
 */

/** Parse RFC4180-ish CSV. Handles quoted fields, embedded commas, CRLF.
 *  Blank lines skipped. Does NOT interpret a header row.
 *  @param {string} text
 *  @returns {string[][]}
 */
export function parseCsv(text) {
  if (!text) return [];

  const rows = [];
  let i = 0;
  const n = text.length;

  while (i < n) {
    const fields = [];
    let rowHasContent = false;

    // Parse one row (may span multiple real lines when quoted fields contain \n)
    while (i < n) {
      if (text[i] === '"') {
        // Quoted field
        rowHasContent = true;
        i++; // skip opening quote
        let field = "";
        while (i < n) {
          if (text[i] === '"') {
            if (i + 1 < n && text[i + 1] === '"') {
              // Escaped quote ""  →  "
              field += '"';
              i += 2;
            } else {
              // Closing quote
              i++;
              break;
            }
          } else {
            field += text[i];
            i++;
          }
        }
        fields.push(field);
        // After closing quote, expect , or line ending
        if (i < n && text[i] === ',') {
          i++; // consume comma, next field follows
        } else {
          // End of row (CR LF, LF, or EOF)
          if (i < n && text[i] === '\r') i++;
          if (i < n && text[i] === '\n') i++;
          break;
        }
      } else {
        // Unquoted field — read until , or newline
        let field = "";
        while (i < n && text[i] !== ',' && text[i] !== '\n' && text[i] !== '\r') {
          field += text[i];
          i++;
        }
        fields.push(field);
        if (field !== "" || fields.length > 1) rowHasContent = true;
        if (i < n && text[i] === ',') {
          i++; // consume comma, next field follows
          rowHasContent = true;
        } else {
          // End of row
          if (i < n && text[i] === '\r') i++;
          if (i < n && text[i] === '\n') i++;
          break;
        }
      }
    }

    // Skip blank/whitespace-only rows
    const isBlank = fields.length === 0 ||
      (fields.length === 1 && fields[0].trim() === "");
    if (!isBlank) {
      rows.push(fields);
    }
  }

  return rows;
}
