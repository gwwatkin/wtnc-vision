# Race Results Timeline — web/

Static front-end. No build step; served directly by Python's built-in HTTP server.

## Running locally

```sh
cd web
python -m http.server 8000
```

Then open <http://localhost:8000/> in a browser.

> **Why a server?** Browsers block `fetch()` over `file://`. Any static host
> (Nginx, GitHub Pages, etc.) works equally well in production.

## Configuration layers (highest priority first)

| Layer | How |
|-------|-----|
| Query string | `?gap=5&refresh=0&crossings=other.csv&roster=other.csv` |
| Page global | `<script>window.RESULTS_CONFIG = { gapSeconds: 5 }</script>` in `index.html` |
| Defaults | `DEFAULT_CONFIG` in `app.js` |

Query-string keys: `gap` → `gapSeconds`, `refresh` → `refreshMs`,
`crossings` → `crossingsUrl`, `roster` → `rosterUrl`.

## CSV paths

| File | Default path (relative to `web/`) | Config key |
|------|------------------------------------|------------|
| Crossings | `data/crossings.csv` | `crossingsUrl` |
| Roster | `data/roster.csv` | `rosterUrl` |

### crossings.csv format
No header row. Columns: `time` (ISO 8601 with UTC offset), `race_number`.

```
2026-07-11T14:47:00-07:00,412
```

### roster.csv format
No header row. Columns: `race_number`, `name`, `category`. Fields may be quoted.

```
412,"George Watkins","Cat 3"
```
