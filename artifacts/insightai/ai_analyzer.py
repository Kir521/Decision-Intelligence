"""
AI Analysis module for InsightAI.
Uses Google Gemini API when available, falls back to realistic demo responses.
"""
import os
import json
import random
import numpy as np
import pandas as pd
from datetime import datetime

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def _get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not GEMINI_AVAILABLE:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception:
        return None


def compute_stats(df: pd.DataFrame) -> dict:
    """Compute descriptive statistics from a DataFrame."""
    stats = {
        "shape": {"rows": len(df), "cols": len(df.columns)},
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing": {col: int(df[col].isna().sum()) for col in df.columns},
        "numeric_cols": list(df.select_dtypes(include="number").columns),
        "categorical_cols": list(df.select_dtypes(include=["object", "category"]).columns),
    }
    num_df = df.select_dtypes(include="number")
    if not num_df.empty:
        desc = num_df.describe().to_dict()
        stats["numeric_stats"] = {
            col: {k: round(float(v), 4) for k, v in vals.items()}
            for col, vals in desc.items()
        }
        # Correlation matrix (top pairs)
        if num_df.shape[1] >= 2:
            corr = num_df.corr().abs()
            pairs = []
            cols = list(num_df.columns)
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    val = corr.iloc[i, j]
                    if not np.isnan(val):
                        pairs.append({"col1": cols[i], "col2": cols[j], "corr": round(float(val), 3)})
            pairs.sort(key=lambda x: x["corr"], reverse=True)
            stats["top_correlations"] = pairs[:5]
    return stats


def build_chart_data(df: pd.DataFrame) -> dict:
    """Build chart-ready data structures from a DataFrame."""
    charts = {}
    num_cols = list(df.select_dtypes(include="number").columns)
    cat_cols = list(df.select_dtypes(include=["object", "category"]).columns)

    # Bar chart: first numeric col values (sample)
    if num_cols:
        col = num_cols[0]
        sample = df[col].dropna().head(20)
        charts["bar"] = {
            "labels": [str(i + 1) for i in range(len(sample))],
            "datasets": [{"label": col, "data": [round(float(v), 2) for v in sample]}],
        }

    # Line chart: up to 3 numeric cols
    if num_cols:
        sample_len = min(20, len(df))
        datasets = []
        for col in num_cols[:3]:
            sample = df[col].dropna().head(sample_len)
            datasets.append({"label": col, "data": [round(float(v), 2) for v in sample]})
        charts["line"] = {
            "labels": [str(i + 1) for i in range(sample_len)],
            "datasets": datasets,
        }

    # Pie chart: first categorical col top 6
    if cat_cols:
        col = cat_cols[0]
        vc = df[col].value_counts().head(6)
        charts["pie"] = {
            "labels": list(vc.index.astype(str)),
            "datasets": [{"data": [int(v) for v in vc.values]}],
        }

    # Scatter: first two numeric cols
    if len(num_cols) >= 2:
        sample = df[[num_cols[0], num_cols[1]]].dropna().head(50)
        charts["scatter"] = {
            "datasets": [{
                "label": f"{num_cols[0]} vs {num_cols[1]}",
                "data": [{"x": round(float(row[num_cols[0]]), 2), "y": round(float(row[num_cols[1]]), 2)}
                         for _, row in sample.iterrows()],
            }]
        }

    return charts


def _demo_analysis(df: pd.DataFrame, stats: dict) -> dict:
    """Generate realistic demo AI analysis without an API key."""
    num_cols = stats.get("numeric_cols", [])
    cat_cols = stats.get("categorical_cols", [])
    rows = stats["shape"]["rows"]
    cols = stats["shape"]["cols"]

    # Compute simple derived stats for realism
    growth_pct = round(random.uniform(8.5, 34.2), 1)
    confidence = round(random.uniform(0.78, 0.96), 2)
    decision_score = round(random.uniform(62, 92), 1)
    risk_choices = ["Low", "Medium", "High"]
    risk_weights = [0.3, 0.45, 0.25]
    risk_level = random.choices(risk_choices, weights=risk_weights)[0]

    num_stat_detail = ""
    if num_cols and "numeric_stats" in stats:
        col = num_cols[0]
        ns = stats["numeric_stats"].get(col, {})
        mean_val = ns.get("mean", 0)
        std_val = ns.get("std", 0)
        num_stat_detail = f"The primary metric '{col}' averages {mean_val:.2f} with a standard deviation of {std_val:.2f}."

    executive_summary = (
        f"InsightAI analyzed your dataset of {rows:,} records across {cols} dimensions. "
        f"{num_stat_detail} "
        f"The analysis reveals a {growth_pct}% growth trend in core metrics with "
        f"{'notable variance requiring attention' if risk_level == 'High' else 'stable performance patterns'}. "
        f"Decision confidence stands at {int(confidence * 100)}%, indicating "
        f"{'strong data quality and actionable signals' if confidence > 0.85 else 'moderate reliability — consider enriching the dataset'}."
    )

    trend_templates = [
        f"{'Upward' if growth_pct > 15 else 'Moderate'} growth of {growth_pct}% observed in primary metrics",
        f"Data distribution is {'skewed right' if random.random() > 0.5 else 'approximately normal'} — signals market expansion",
        f"{random.randint(3, 8)} seasonal patterns detected across the dataset timeline",
        f"Correlation strength between key variables: {random.choice(['strong (r=0.82)', 'moderate (r=0.61)', 'weak (r=0.38)'])}",
        f"Outlier concentration {'above 2σ threshold' if risk_level != 'Low' else 'within normal range'} flagged",
    ]

    if num_cols:
        trend_templates.append(f"'{num_cols[0]}' shows {'increasing' if random.random() > 0.4 else 'declining'} momentum over the observation window")
    if cat_cols:
        trend_templates.append(f"Segment '{cat_cols[0]}' drives {random.randint(28, 52)}% of total variance")

    key_trends = random.sample(trend_templates, min(4, len(trend_templates)))

    risk_detail_map = {
        "Low": "No critical anomalies detected. Minor variance in tail distributions is within acceptable thresholds. Continue monitoring monthly.",
        "Medium": f"Moderate risk exposure in {random.randint(2, 4)} segments. Outliers at the 95th percentile may indicate emerging issues requiring 30-day watch.",
        "High": f"High-risk patterns detected: {random.randint(3, 7)} anomaly clusters exceed 3σ deviation. Immediate review recommended for operational stability.",
    }
    risk_details = risk_detail_map[risk_level]

    opportunities = [
        f"Optimize resource allocation in under-performing segments for estimated {random.randint(12, 28)}% efficiency gain",
        f"Cross-segment opportunity identified — leveraging correlation between top variables could yield {random.randint(15, 35)}% uplift",
        f"Automate data pipelines for the top {random.randint(3, 6)} recurring patterns to reduce manual overhead",
        f"Predictive modeling on current trends projects {random.randint(8, 22)}% improvement in key decision metrics by next quarter",
    ]

    recommended_actions = [
        {"priority": "High", "action": f"Investigate {random.randint(3, 8)} anomalous records exceeding statistical thresholds immediately", "impact": "Risk reduction"},
        {"priority": "High", "action": f"Implement monitoring alerts for '{num_cols[0] if num_cols else 'primary metric'}' deviations >2σ", "impact": "Operational stability"},
        {"priority": "Medium", "action": "Enrich dataset with temporal dimension to improve predictive confidence by ~15%", "impact": "Decision quality"},
        {"priority": "Medium", "action": f"Segment analysis by '{cat_cols[0] if cat_cols else 'category'}' to unlock granular insights", "impact": "Strategic clarity"},
        {"priority": "Low", "action": "Schedule quarterly model retraining as new data accumulates", "impact": "Long-term accuracy"},
    ]

    anomaly_count = random.randint(1, max(1, min(8, rows // 10 + 1)))
    anomalies = []
    for i in range(anomaly_count):
        row_idx = random.randint(1, rows)
        col_name = random.choice(num_cols) if num_cols else "value"
        severity = random.choice(["Low", "Medium", "High"])
        anomalies.append({
            "row": row_idx,
            "column": col_name,
            "severity": severity,
            "description": f"Value deviates {random.uniform(2.1, 4.8):.1f}σ from the column mean",
        })

    predictions = [
        {"metric": num_cols[0] if num_cols else "Primary KPI", "direction": "increase" if random.random() > 0.4 else "decrease",
         "magnitude": f"{random.randint(5, 25)}%", "timeframe": "next 30 days", "confidence": f"{random.randint(72, 91)}%"},
        {"metric": num_cols[1] if len(num_cols) > 1 else "Secondary KPI", "direction": "stabilize",
         "magnitude": f"±{random.randint(2, 8)}%", "timeframe": "next 60 days", "confidence": f"{random.randint(65, 88)}%"},
    ]

    return {
        "executive_summary": executive_summary,
        "key_trends": key_trends,
        "risk_level": risk_level,
        "risk_details": risk_details,
        "opportunities": opportunities,
        "recommended_actions": recommended_actions,
        "confidence_score": confidence,
        "decision_score": decision_score,
        "anomalies": anomalies,
        "predictions": predictions,
        "is_demo": True,
    }


def _gemini_analysis(model, df: pd.DataFrame, stats: dict) -> dict:
    """Use Gemini to generate AI analysis."""
    preview = df.head(10).to_csv(index=False)
    stats_summary = json.dumps({k: v for k, v in stats.items() if k != "numeric_stats"}, indent=2)
    numeric_stats = json.dumps(stats.get("numeric_stats", {}), indent=2)

    prompt = f"""You are InsightAI, a world-class business intelligence analyst. Analyze this dataset and provide actionable insights.

DATASET PREVIEW (first 10 rows):
{preview}

STATISTICAL SUMMARY:
{stats_summary}

NUMERIC STATISTICS:
{numeric_stats}

Respond ONLY with a valid JSON object (no markdown, no code blocks) with this exact structure:
{{
  "executive_summary": "2-3 sentence executive summary highlighting the most critical finding",
  "key_trends": ["trend 1", "trend 2", "trend 3", "trend 4"],
  "risk_level": "Low|Medium|High|Critical",
  "risk_details": "1-2 sentence description of key risks",
  "opportunities": ["opportunity 1", "opportunity 2", "opportunity 3", "opportunity 4"],
  "recommended_actions": [
    {{"priority": "High|Medium|Low", "action": "specific action", "impact": "expected impact"}},
    {{"priority": "High|Medium|Low", "action": "specific action", "impact": "expected impact"}},
    {{"priority": "High|Medium|Low", "action": "specific action", "impact": "expected impact"}}
  ],
  "confidence_score": 0.85,
  "decision_score": 78.5,
  "anomalies": [
    {{"row": 5, "column": "col_name", "severity": "High|Medium|Low", "description": "description"}}
  ],
  "predictions": [
    {{"metric": "metric name", "direction": "increase|decrease|stabilize", "magnitude": "X%", "timeframe": "next 30 days", "confidence": "85%"}}
  ]
}}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        result["is_demo"] = False
        return result
    except Exception as e:
        # Fallback to demo if Gemini fails
        result = _demo_analysis(df, stats)
        result["is_demo"] = True
        return result


def analyze(df: pd.DataFrame) -> dict:
    """Main entry point: analyze a DataFrame and return AI insights."""
    stats = compute_stats(df)
    chart_data = build_chart_data(df)

    model = _get_gemini_client()
    if model:
        ai_result = _gemini_analysis(model, df, stats)
    else:
        ai_result = _demo_analysis(df, stats)

    ai_result["chart_data"] = chart_data
    ai_result["raw_stats"] = stats
    return ai_result
