# InsightAI

AI-powered Decision Intelligence Platform — users upload or enter data, Gemini AI analyzes it for trends, risks, and opportunities, and delivers interactive charts and downloadable reports.

## Run & Operate

- `cd artifacts/insightai && python app.py` — run the Flask app (port 5000)
- Workflow: `InsightAI` (auto-started)

## Stack

- Python Flask 3.0 + Flask-SQLAlchemy + Flask-Login
- SQLite database (`artifacts/insightai/insightai.db`)
- Google Gemini AI (`google-generativeai`) — falls back to realistic demo mode if key absent
- Pandas + NumPy for statistical analysis
- Chart.js 4 for interactive charts
- ReportLab for PDF report generation
- Bootstrap 5 + Material Icons + custom CSS

## Where things live

- `artifacts/insightai/app.py` — Flask routes, auth, PDF download
- `artifacts/insightai/ai_analyzer.py` — Gemini AI + demo fallback
- `artifacts/insightai/models.py` — User and Analysis SQLAlchemy models
- `artifacts/insightai/templates/` — Jinja2 HTML templates
- `artifacts/insightai/static/css/style.css` — Full Material Design theme
- `artifacts/insightai/static/js/app.js` — Sidebar, animations, counters

## Architecture decisions

- Demo mode auto-activates when `GEMINI_API_KEY` is not set — computes real stats from data, generates realistic narrative from them
- SQLite is used for simplicity; all analysis results stored as JSON strings in columns
- PDF reports generated server-side with ReportLab (no browser print)
- Chart data served via JSON API endpoints (`/api/analysis/<id>/chart-data`, `/api/dashboard-stats`)

## Product

- Landing page → Register/Login → Dashboard (KPI cards + charts + recent history)
- Upload CSV/XLSX or manual spreadsheet entry → AI analysis page
- Analysis: executive summary, key trends, risk level + anomalies, opportunities, recommended actions, predictive insights
- Download PDF report, view analysis history, delete analyses

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- Use `google.genai` (new SDK) eventually — current `google-generativeai` shows a FutureWarning but still works
- Uploaded files go to `artifacts/insightai/uploads/` (created automatically)
- Port 5000 is used by the InsightAI workflow; do not use it for other services
