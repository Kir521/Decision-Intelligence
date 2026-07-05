---
name: InsightAI Flask setup
description: Python Flask AI app setup, quirks, and decisions for the InsightAI project
---

## Key facts

- App lives at `artifacts/insightai/`, runs on port 5000 via workflow named `InsightAI`
- Command: `cd artifacts/insightai && python app.py`
- Python 3.11 installed as a module; packages in `.pythonlibs/`

## Template inheritance gotcha
Jinja2 does NOT allow the same `{% block name %}` to appear more than once in a template. In `base.html`, authenticated pages use `{% block content %}` and public pages use `{% block public_content %}`. Public templates (index, login, register) must use `{% block public_content %}`.

## Demo mode anomaly bug (fixed)
`random.randint(low, high)` raises ValueError if low > high. For datasets with < 10 rows, `min(8, rows // 10 + 1)` evaluates to 1, making `randint(2, 1)` crash. Fixed to `randint(1, max(1, ...))`.

## Session secret
App generates a random secret at startup if SESSION_SECRET env var is absent — avoids hardcoded fallback. SESSION_SECRET is already set as a Replit Secret.

## google-generativeai deprecation
The `google-generativeai` package shows a FutureWarning — it still works but should be migrated to `google.genai` in a future update.

**Why:** The new SDK is `google-genai` (not `google-generativeai`). Migration requires updating import paths and model initialization.
