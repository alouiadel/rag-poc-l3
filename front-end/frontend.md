# Frontend

Vanilla HTML/CSS/JS UI served by the FastAPI backend. No build step. The API base URL defaults to the page origin and can be overridden with `window.RAG_API_BASE_URL` (see `config.js`).

## Layout

```
front-end/
├── config.js          # API base URL + endpoint map
├── lib/
│   ├── marked.min.js  # Markdown renderer
│   ├── purify.min.js  # DOMPurify (sanitizes chat HTML)
│   ├── icons.svg      # inline SVG icon sprite
│   ├── ui.js          # shared helpers, auth guard, logout
│   └── theme.css      # shared reset, icons & common chrome
├── login/             # login page
├── chat/              # chat interface (custom persona dropdown)
├── admin/             # personas, users & knowledge-base panels
├── stats/             # vector store statistics
└── assets/            # SVG logo, favicon & login slides
```

## Pages

| Page | Route | Purpose |
| --- | --- | --- |
| Login | `/` | Authenticate; stores `access_token` + `username` in `localStorage` |
| Chat | `/chat` | Multi-turn chat, file upload, session history |
| Admin | `/admin` | Personas, user roles, and knowledge-base ingest/reset (admin only) |
| Stats | `/stats` | Vector store statistics from `/collection-info` (admin only) |

## API usage (`config.js`)

The frontend calls: `POST /login`, `POST /logout`, `POST /chat`, `POST /upload`, `GET /chat/sessions`, `DELETE /chat/sessions/{id}`, `GET|POST|PUT|DELETE /personas`, `GET /users`, `POST /update-user-admin`, `POST /ingest`, `POST /reset-collection`, and `GET /collection-info`.

Notes:
- Chat sends the selected persona via `persona_prompt`; the backend applies it to the assistant's instructions.
- Icons come from the `lib/icons.svg` sprite via `<svg class="icon"><use href="…/icons.svg#i-…"/></svg>`.

## Development

Open the pages through the backend (e.g. `http://127.0.0.1:8000/`); serving the HTML files with a separate static server will break the API calls and asset paths unless `window.RAG_API_BASE_URL` is set.
