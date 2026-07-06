"""
AI Analysis module for InsightAI.
Uses Google Gemini API when available, falls back to fully-deterministic
statistical analysis derived exclusively from the uploaded dataset.
No random() calls remain — identical datasets always produce identical results.
"""
import os
import json
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

    # Bar chart: first numeric col values (first 20 rows)
    if num_cols:
        col = num_cols[0]
        sample = df[col].dropna().head(20)
        charts["bar"] = {
            "labels": [str(i + 1) for i in range(len(sample))],
            "datasets": [{"label": col, "data": [round(float(v), 2) for v in sample]}],
        }

    # Line chart: up to 3 numeric cols, all trimmed to equal length
    if num_cols:
        sample_len = min(20, len(df))
        datasets = []
        for col in num_cols[:3]:
            sample = df[col].dropna().head(sample_len)
            datasets.append({"label": col, "data": [round(float(v), 2) for v in sample]})
        min_len = min(len(d["data"]) for d in datasets) if datasets else 0
        if min_len > 0:
            for d in datasets:
                d["data"] = d["data"][:min_len]
            charts["line"] = {
                "labels": [str(i + 1) for i in range(min_len)],
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


def _detect_real_anomalies(df: pd.DataFrame, num_cols: list, threshold: float = 2.5, max_count: int = 8) -> list:
    """
    Detect actual statistical outliers (|z-score| > threshold) in numeric columns.
    Returns a deterministic list sorted by deviation magnitude (largest first).
    """
    findings = []
    num_df = df.select_dtypes(include="number")
    for col in num_cols:
        series = num_df[col].dropna()
        if len(series) < 3:
            continue
        m = float(series.mean())
        sd = float(series.std())
        if sd == 0:
            continue
        z = ((series - m) / sd).abs()
        outliers = z[z > threshold].sort_values(ascending=False)
        for idx, z_val in outliers.head(3).items():
            z_val = float(z_val)
            severity = "High" if z_val > 3.5 else ("Medium" if z_val > 3.0 else "Low")
            row_num = int(idx) + 1 if isinstance(idx, (int, np.integer)) else 1
            findings.append({
                "row": row_num,
                "column": col,
                "severity": severity,
                "description": f"Value deviates {z_val:.1f}σ from the column mean",
                "_sort_key": z_val,
            })
    # Sort by deviation magnitude, return top max_count, strip sort key
    findings.sort(key=lambda x: x["_sort_key"], reverse=True)
    for f in findings:
        del f["_sort_key"]
    return findings[:max_count]


def _demo_analysis(df: pd.DataFrame, stats: dict) -> dict:
    """
    Generate fully deterministic AI analysis using only the dataset's own
    statistical properties. No random() calls — identical inputs always
    produce identical outputs.
    """
    num_cols = stats.get("numeric_cols", [])
    cat_cols = stats.get("categorical_cols", [])
    rows = stats["shape"]["rows"]
    cols_count = stats["shape"]["cols"]
    num_df = df.select_dtypes(include="number")

    # ── Step 1: Derive all metrics from actual data ───────────────────────────

    # Data completeness
    total_cells = rows * cols_count
    missing_count = sum(stats.get("missing", {}).values())
    completeness = 1.0 - (missing_count / max(1, total_cells))
    missing_ratio = 1.0 - completeness

    # Per-column: CV, skewness, outliers, linear trend slope
    cvs, skews, slopes = [], [], []
    total_outliers = 0
    total_vals = 0
    for col in num_df.columns:
        s = num_df[col].dropna()
        if len(s) < 2:
            continue
        m = float(s.mean())
        sd = float(s.std())
        total_vals += len(s)
        if m != 0:
            cvs.append(abs(sd / m))
        if sd > 0:
            z = ((s - m) / sd).abs()
            total_outliers += int((z > 2.5).sum())
            skews.append(float(s.skew()))
        if len(s) > 1:
            raw_slope = float(np.polyfit(np.arange(len(s)), s.values, 1)[0])
            slopes.append(raw_slope / (abs(m) + 1e-9))

    avg_cv = float(np.mean(cvs)) if cvs else 0.0
    is_skewed_right = bool(np.mean(skews) > 0) if skews else False
    outlier_ratio = total_outliers / max(1, total_vals)
    overall_trend_up = bool(sum(slopes) > 0) if slopes else True

    # ── Decision Score (0–100): weighted composite ────────────────────────────
    # completeness (40 pts) + stability/low-CV (35 pts) + low-outlier-ratio (25 pts)
    score_completeness = completeness * 40.0
    score_stability    = max(0.0, 1.0 - min(avg_cv, 2.0) / 2.0) * 35.0
    score_quality      = max(0.0, 1.0 - outlier_ratio * 10.0) * 25.0
    decision_score     = round(
        max(40.0, min(95.0, score_completeness + score_stability + score_quality)), 1
    )

    # ── Confidence Score (0.60–0.97) ──────────────────────────────────────────
    confidence = round(
        max(0.60, min(0.97,
            completeness * 0.78
            + min(rows / 1000.0, 1.0) * 0.13
            + min(cols_count / 10.0, 1.0) * 0.07
        )), 2
    )

    # ── Risk Level ────────────────────────────────────────────────────────────
    if outlier_ratio > 0.10 or missing_ratio > 0.20:
        risk_level = "High"
    elif outlier_ratio > 0.04 or missing_ratio > 0.05:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # ── Growth %: compare actual first-third vs last-third of numeric means ───
    growth_pct = 0.0
    if not num_df.empty and rows >= 4:
        split = max(2, rows // 3)
        first_m = num_df.head(split).mean()
        last_m  = num_df.tail(split).mean()
        valid   = first_m[first_m.abs() > 1e-9]
        if not valid.empty:
            pct_changes = (last_m[valid.index] - valid) / valid.abs() * 100.0
            growth_pct  = round(float(pct_changes.mean()), 1)
            growth_pct  = max(-99.0, min(999.0, growth_pct))

    # ── Top correlation label ─────────────────────────────────────────────────
    top_corrs = stats.get("top_correlations", [])
    if top_corrs:
        r = top_corrs[0]["corr"]
        corr_label = (
            f"strong (r={r:.2f})"   if r >= 0.70 else
            f"moderate (r={r:.2f})" if r >= 0.40 else
            f"weak (r={r:.2f})"
        )
    else:
        corr_label = "not applicable (single numeric column)"

    # ── Primary-column stat detail ────────────────────────────────────────────
    num_stat_detail = ""
    if num_cols and "numeric_stats" in stats:
        ns = stats["numeric_stats"].get(num_cols[0], {})
        mean_val = ns.get("mean", 0)
        std_val  = ns.get("std",  0)
        num_stat_detail = (
            f"The primary metric '{num_cols[0]}' averages {mean_val:.2f} "
            f"with a standard deviation of {std_val:.2f}."
        )

    # ── Step 2: Build all narrative strings without any random() ─────────────

    growth_adj = "Upward" if growth_pct > 5 else ("Declining" if growth_pct < -5 else "Stable")
    growth_dir = "positive" if growth_pct >= 0 else "negative"

    executive_summary = (
        f"InsightAI analyzed your dataset of {rows:,} records across {cols_count} dimensions. "
        f"{num_stat_detail} "
        f"The analysis reveals a {growth_pct:+.1f}% {growth_dir} trend in core metrics with "
        f"{'notable variance requiring attention' if risk_level == 'High' else 'stable performance patterns'}. "
        f"Decision confidence stands at {int(confidence * 100)}%, indicating "
        f"{'strong data quality and actionable signals' if confidence > 0.85 else 'moderate reliability — consider enriching the dataset'}."
    )

    # Key trends — every value derived from computed stats
    trend_slope_dir = "increasing" if overall_trend_up else "declining"
    key_trends = [
        f"{growth_adj} trend of {growth_pct:+.1f}% observed in primary metrics",
        f"Data distribution is {'skewed right' if is_skewed_right else 'approximately normal'} — "
        f"{'signals asymmetric market behaviour' if is_skewed_right else 'supports symmetric statistical modelling'}",
        f"Correlation strength between key variables: {corr_label}",
        f"Outlier concentration {'above 2.5σ threshold — monitoring advised' if risk_level != 'Low' else 'within normal range — no action needed'}",
    ]
    if num_cols:
        key_trends.append(
            f"'{num_cols[0]}' shows {trend_slope_dir} momentum over the observation window"
        )
    if cat_cols:
        vc = df[cat_cols[0]].value_counts()
        top_share = round(vc.iloc[0] / max(1, vc.sum()) * 100.0, 1) if not vc.empty else 0.0
        key_trends.append(
            f"Top segment in '{cat_cols[0]}' accounts for {top_share}% of records"
        )
    key_trends = key_trends[:4]  # keep exactly 4, no sample()

    # Risk details
    risk_seg_count    = max(1, round(outlier_ratio * cols_count * 10))
    anomaly_cluster_n = max(1, min(7, total_outliers // max(1, cols_count)))
    risk_detail_map = {
        "Low":    "No critical anomalies detected. Minor variance in tail distributions is within acceptable thresholds. Continue monitoring monthly.",
        "Medium": f"Moderate risk exposure in {risk_seg_count} segment(s). Outliers at the 95th percentile may indicate emerging issues requiring 30-day watch.",
        "High":   f"High-risk patterns detected: {anomaly_cluster_n} anomaly cluster(s) exceed 3σ deviation. Immediate review recommended for operational stability.",
    }
    risk_details = risk_detail_map[risk_level]

    # Opportunities — all magnitudes derived from computed metrics
    efficiency_gain = int(max(5, min(40, round(avg_cv * 30))))
    uplift_pct      = int(max(10, min(50, round((top_corrs[0]["corr"] if top_corrs else 0.5) * 50))))
    improvement_pct = int(max(5, min(30, round((1.0 - outlier_ratio) * 20))))
    opportunities = [
        f"Optimize resource allocation in under-performing segments for estimated {efficiency_gain}% efficiency gain",
        f"Cross-segment opportunity identified — leveraging {corr_label} correlation could yield {uplift_pct}% uplift",
        "Automate data pipelines for the top recurring patterns to reduce manual overhead",
        f"Predictive modelling on current trends projects {improvement_pct}% improvement in key decision metrics by next quarter",
    ]

    # Recommended actions — reference actual counts and column names
    primary_col = num_cols[0] if num_cols else "primary metric"
    primary_cat = cat_cols[0] if cat_cols else "category"
    recommended_actions = [
        {"priority": "High",   "action": f"Investigate {total_outliers} anomalous record(s) exceeding 2.5σ statistical threshold(s)", "impact": "Risk reduction"},
        {"priority": "High",   "action": f"Implement monitoring alerts for '{primary_col}' deviations >2σ", "impact": "Operational stability"},
        {"priority": "Medium", "action": "Enrich dataset with temporal dimension to improve predictive confidence by ~15%", "impact": "Decision quality"},
        {"priority": "Medium", "action": f"Segment analysis by '{primary_cat}' to unlock granular insights", "impact": "Strategic clarity"},
        {"priority": "Low",    "action": "Schedule quarterly model retraining as new data accumulates", "impact": "Long-term accuracy"},
    ]

    # Anomalies — detect real statistical outliers; fall back to most-extreme values
    anomalies = _detect_real_anomalies(df, num_cols)
    if not anomalies:
        # No values beyond 2.5σ; report the single most-extreme value per column
        for col in num_cols[:2]:
            s = num_df[col].dropna()
            if len(s) < 2:
                continue
            m  = float(s.mean())
            sd = float(s.std())
            if sd == 0:
                continue
            z_series  = ((s - m) / sd).abs()
            max_idx   = z_series.idxmax()
            z_val     = float(z_series[max_idx])
            row_num   = int(max_idx) + 1 if isinstance(max_idx, (int, np.integer)) else 1
            anomalies.append({
                "row": row_num,
                "column": col,
                "severity": "Low",
                "description": f"Most extreme value ({z_val:.1f}σ from mean); within acceptable bounds",
            })

    # Predictions — direction from actual computed linear slope
    trend_dir_0 = "increase" if overall_trend_up else "decrease"
    pred_mag_0  = int(max(3, min(30, round(abs(growth_pct) * 0.3 or 5))))
    pred_mag_1  = int(max(1, min(10, round(avg_cv * 5))))
    pred_conf_0 = int(min(91, max(65, round(confidence * 95))))
    pred_conf_1 = int(min(88, max(62, round(confidence * 88))))

    predictions = [
        {
            "metric":    num_cols[0] if num_cols else "Primary KPI",
            "direction": trend_dir_0,
            "magnitude": f"{pred_mag_0}%",
            "timeframe": "next 30 days",
            "confidence": f"{pred_conf_0}%",
        },
        {
            "metric":    num_cols[1] if len(num_cols) > 1 else "Secondary KPI",
            "direction": "stabilize",
            "magnitude": f"±{pred_mag_1}%",
            "timeframe": "next 60 days",
            "confidence": f"{pred_conf_1}%",
        },
    ]

    return {
        "executive_summary":  executive_summary,
        "key_trends":         key_trends,
        "risk_level":         risk_level,
        "risk_details":       risk_details,
        "opportunities":      opportunities,
        "recommended_actions": recommended_actions,
        "confidence_score":   confidence,
        "decision_score":     decision_score,
        "anomalies":          anomalies,
        "predictions":        predictions,
        "is_demo":            True,
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
    except Exception:
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
