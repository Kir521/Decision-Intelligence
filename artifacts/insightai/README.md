# InsightAI — AI-Powered Decision Intelligence Platform

InsightAI is a full-stack web application that uses Google Gemini AI to analyze data and generate actionable business insights, trend detection, risk assessment, and predictive recommendations.

## Features

- **User Authentication** — Secure register/login with Flask-Login
- **File Upload** — CSV, XLSX, XLS (up to 16 MB)
- **Manual Data Entry** — Interactive spreadsheet editor in the browser
- **AI Analysis** — Google Gemini AI detects trends, risks, opportunities, and anomalies
- **Demo Mode** — Realistic AI responses generated automatically when no API key is set
- **Interactive Charts** — Bar, line, pie, scatter via Chart.js
- **PDF Reports** — Download professional analysis reports via ReportLab
- **Analysis History** — View, revisit, and delete past analyses
- **Responsive UI** — Material Design + Bootstrap 5, mobile-friendly

## AI Output Per Analysis

- Executive Summary
- Key Trends (4 bullets)
- Risk Level (Low / Medium / High / Critical)
- Risk Details
- Opportunities (4 bullets)
- Recommended Actions (prioritized: High / Medium / Low)
- Confidence Score (0–100%)
- Decision Score (0–100)
- Anomaly Detection (row, column, severity)
- Predictive Insights (direction, magnitude, timeframe)

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python Flask 3, Flask-SQLAlchemy, Flask-Login |
| Database | SQLite (via SQLAlchemy) |
| AI | Google Gemini 1.5 Flash (`google-generativeai`) |
| Data | Pandas, NumPy |
| Charts | Chart.js 4 |
| Frontend | Bootstrap 5, Material Icons, vanilla JS |
| PDF | ReportLab |

## Setup & Running

### Requirements
- Python 3.10+
- `pip install -r requirements.txt`

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SESSION_SECRET` | Yes | Flask session secret key |
| `GEMINI_API_KEY` | Optional | Google Gemini API key (demo mode if absent) |

### Run Locally

```bash
cd artifacts/insightai
pip install -r requirements.txt
export SESSION_SECRET=your-secret
export GEMINI_API_KEY=your-gemini-key   # optional
python app.py
```

App runs on `http://localhost:5000`.

## Project Structure

```
artifacts/insightai/
├── app.py              # Flask app, routes, auth, PDF
├── ai_analyzer.py      # Gemini AI + demo fallback
├── models.py           # SQLAlchemy models (User, Analysis)
├── requirements.txt
├── README.md
├── static/
│   ├── css/style.css   # Full custom Material + Bootstrap theme
│   └── js/app.js       # Sidebar, animations, counters
└── templates/
    ├── base.html        # Layout: sidebar, topbar, flash messages
    ├── index.html       # Landing page
    ├── login.html
    ├── register.html
    ├── dashboard.html   # KPIs + charts + recent table
    ├── upload.html      # Drag-and-drop file upload
    ├── manual_entry.html # Editable spreadsheet
    ├── analysis.html    # Full AI analysis view + charts
    └── history.html     # Past analyses table
```

## Demo Mode

When `GEMINI_API_KEY` is not set, InsightAI automatically generates realistic simulated AI responses based on actual statistical computation from the uploaded data. This allows full end-to-end testing and demos without an API key.

## Adding the Gemini API Key

1. Obtain a key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Set it as a Replit Secret named `GEMINI_API_KEY`
3. Restart the workflow — real Gemini AI kicks in automatically

## Hackathon Submission Notes

- All routes handle errors gracefully with flash messages
- Uploaded files are stored in `artifacts/insightai/uploads/`
- SQLite database at `artifacts/insightai/insightai.db`
- PDF reports generated server-side with ReportLab
- Chart data served via `/api/analysis/<id>/chart-data`
- Dashboard stats via `/api/dashboard-stats`
