---
name: InsightAI Flask setup
description: Python Flask AI app setup, quirks, and decisions for the InsightAI project
---

## Key facts

- App lives at `artifacts/insightai/`, runs via managed workflow `artifacts/insightai: web`
- Port: **18287** (set by artifact, via PORT env var injected by Replit)
- Artifact registered at previewPath `/` — this is what registers it with the shared proxy
- Flask reads PORT from env: `port = int(os.environ.get("PORT", 5000))`
- Workflow command: `cd /home/runner/workspace/artifacts/insightai && python app.py`
  - Must be absolute path — managed workflows don't run from workspace root

## Why this architecture matters

Replit's shared proxy at port 80 only routes to services registered in `artifact.toml` with a matching `paths` entry. A plain `configureWorkflow(outputType: "webview")` does NOT register with the proxy. Without a proper artifact registration, the HTML loads but all `/static/…` CSS/JS requests 404 → blank white page.

**Fix**: use `createArtifact` (which writes a valid artifact.toml and registers with the proxy). If the artifact directory already exists, rename it first, run `createArtifact`, then copy Flask files back and update artifact.toml via `verifyAndReplaceArtifactToml`.

## Template inheritance rule

Jinja2 rejects duplicate block names in one template. `base.html` uses:
- `{% block content %}` — for authenticated pages (dashboard, upload, analysis, history, manual_entry)
- `{% block public_content %}` — for public pages (index, login, register)

## Favicon

Copied from `public/favicon.svg` → `static/favicon.svg`. Linked via:
```html
<link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='favicon.svg') }}">
```

## Security fixes applied

- Demo mode anomaly: `randint(1, max(1, min(8, rows // 10 + 1)))` — avoids ValueError on <10-row datasets
- Session secret: generates a random key at startup if SESSION_SECRET env var absent (SESSION_SECRET is set as a Replit Secret)
- Open redirect in login: validates `next` starts with `/` and not `//` before redirecting

## google-generativeai deprecation

`google-generativeai` shows a FutureWarning. Still works. Future migration path: switch to `google.genai` package.

**Why:** The new SDK is `google-genai` (not `google-generativeai`). Migration requires updating import paths and model init.
