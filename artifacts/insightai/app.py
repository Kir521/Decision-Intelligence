"""InsightAI — AI-powered Decision Intelligence Platform"""
import os
import json
import io
import traceback
from datetime import datetime
from functools import wraps

import pandas as pd
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, send_file, session)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

from models import db, User, Analysis
import ai_analyzer
import email_service

# ─── App setup ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
_secret = os.environ.get("SESSION_SECRET")
if not _secret:
    import secrets
    _secret = secrets.token_hex(32)
app.secret_key = _secret

# Database
db_path = os.path.join(BASE_DIR, "insightai.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Upload
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()


# ─── Helpers ──────────────────────────────────────────────────────────────────
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_df_from_file(filepath):
    ext = filepath.rsplit(".", 1)[1].lower()
    if ext == "csv":
        return pd.read_csv(filepath)
    elif ext in ("xlsx", "xls"):
        return pd.read_excel(filepath)
    raise ValueError(f"Unsupported file type: {ext}")


def load_df_from_manual(rows_json):
    """Parse manually entered JSON rows into a DataFrame."""
    data = json.loads(rows_json)
    if isinstance(data, list) and data:
        return pd.DataFrame(data)
    raise ValueError("Invalid manual data format")


def save_analysis_result(user_id, title, df, result, source="upload", filename=None):
    """Persist an analysis to the database."""
    a = Analysis(
        user_id=user_id,
        title=title,
        data_source=source,
        original_filename=filename,
        row_count=len(df),
        column_count=len(df.columns),
        executive_summary=result.get("executive_summary", ""),
        key_trends=json.dumps(result.get("key_trends", [])),
        risk_level=result.get("risk_level", "Medium"),
        risk_details=result.get("risk_details", ""),
        opportunities=json.dumps(result.get("opportunities", [])),
        recommended_actions=json.dumps(result.get("recommended_actions", [])),
        confidence_score=float(result.get("confidence_score", 0)),
        decision_score=float(result.get("decision_score", 0)),
        anomalies=json.dumps(result.get("anomalies", [])),
        predictions=json.dumps(result.get("predictions", [])),
        chart_data=json.dumps(result.get("chart_data", {})),
        raw_stats=json.dumps(result.get("raw_stats", {})),
    )
    db.session.add(a)
    db.session.commit()
    return a


# ─── Public routes ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("register.html")
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "danger")
            return render_template("register.html")
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"Welcome to InsightAI, {username}! Start your first analysis.", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            # Send login notification email asynchronously (never blocks login)
            try:
                raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
                client_ip = raw_ip.split(",")[0].strip() if "," in raw_ip else raw_ip
                user_agent = request.headers.get("User-Agent", "")
                email_service.send_login_notification(
                    user.email, user.username, client_ip, user_agent
                )
            except Exception:
                pass  # email errors must never prevent login
            next_page = request.args.get("next")
            flash(f"Welcome back, {user.username}!", "success")
            # Validate next_page to prevent open-redirect attacks
            if next_page and next_page.startswith("/") and not next_page.startswith("//"):
                return redirect(next_page)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


# ─── Authenticated routes ──────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    analyses = Analysis.query.filter_by(user_id=current_user.id).order_by(Analysis.created_at.desc()).all()
    total = len(analyses)
    insights = sum(len(a.get_key_trends()) + len(a.get_opportunities()) for a in analyses)
    high_risk = sum(1 for a in analyses if a.risk_level in ("High", "Critical"))
    recommendations = sum(len(a.get_recommended_actions()) for a in analyses)
    avg_decision = round(sum(a.decision_score or 0 for a in analyses) / total, 1) if total else 0
    recent = analyses[:5]

    # Build dashboard chart data inline (avoids AJAX routing issues)
    risk_dist = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    scores = []
    dates = []
    for a in analyses:
        risk_dist[a.risk_level] = risk_dist.get(a.risk_level, 0) + 1
        # Use `is not None` so a legitimate 0.0 score is kept, preserving
        # date/score index alignment for the line chart.
        if a.decision_score is not None:
            scores.append(round(float(a.decision_score), 1))
            dates.append(a.created_at.strftime("%b %d"))

    return render_template(
        "dashboard.html",
        analyses=analyses,
        recent=recent,
        total=total,
        insights=insights,
        high_risk=high_risk,
        recommendations=recommendations,
        avg_decision=avg_decision,
        risk_distribution=risk_dist,
        decision_scores=scores,
        dates=dates,
    )


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        if "file" not in request.files or request.files["file"].filename == "":
            flash("Please select a file.", "danger")
            return render_template("upload.html")
        file = request.files["file"]
        if not allowed_file(file.filename):
            flash("Only CSV, XLSX, and XLS files are supported.", "danger")
            return render_template("upload.html")
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        try:
            df = load_df_from_file(filepath)
            if df.empty:
                flash("The uploaded file has no data.", "danger")
                return render_template("upload.html")
            title = request.form.get("title", "").strip() or f"Analysis — {filename}"
            result = ai_analyzer.analyze(df)
            analysis = save_analysis_result(current_user.id, title, df, result, "upload", filename)
            flash("Analysis complete! Here are your AI insights.", "success")
            return redirect(url_for("analysis", analysis_id=analysis.id))
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "danger")
            return render_template("upload.html")
    return render_template("upload.html")


@app.route("/manual", methods=["GET", "POST"])
@login_required
def manual_entry():
    if request.method == "POST":
        rows_json = request.form.get("rows_json", "").strip()
        title = request.form.get("title", "").strip() or "Manual Data Analysis"
        if not rows_json:
            flash("Please enter some data.", "danger")
            return render_template("manual_entry.html")
        try:
            df = load_df_from_manual(rows_json)
            if df.empty:
                flash("No valid data found.", "danger")
                return render_template("manual_entry.html")
            result = ai_analyzer.analyze(df)
            analysis = save_analysis_result(current_user.id, title, df, result, "manual")
            flash("Analysis complete! AI has processed your data.", "success")
            return redirect(url_for("analysis", analysis_id=analysis.id))
        except Exception as e:
            flash(f"Error processing data: {str(e)}", "danger")
            return render_template("manual_entry.html")
    return render_template("manual_entry.html")


@app.route("/analysis/<int:analysis_id>")
@login_required
def analysis(analysis_id):
    a = Analysis.query.filter_by(id=analysis_id, user_id=current_user.id).first_or_404()
    return render_template("analysis.html", a=a, chart_data=a.get_chart_data())


@app.route("/history")
@login_required
def history():
    analyses = Analysis.query.filter_by(user_id=current_user.id).order_by(Analysis.created_at.desc()).all()
    return render_template("history.html", analyses=analyses)


@app.route("/analysis/<int:analysis_id>/delete", methods=["POST"])
@login_required
def delete_analysis(analysis_id):
    a = Analysis.query.filter_by(id=analysis_id, user_id=current_user.id).first_or_404()
    db.session.delete(a)
    db.session.commit()
    flash("Analysis deleted.", "info")
    return redirect(url_for("history"))


# ─── PDF Report ───────────────────────────────────────────────────────────────
@app.route("/analysis/<int:analysis_id>/report")
@login_required
def download_report(analysis_id):
    a = Analysis.query.filter_by(id=analysis_id, user_id=current_user.id).first_or_404()
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()

        BLUE = colors.HexColor("#1976D2")
        LIGHT_BLUE = colors.HexColor("#E3F2FD")
        DARK = colors.HexColor("#212121")
        GRAY = colors.HexColor("#757575")

        title_style = ParagraphStyle("title", parent=styles["Title"],
                                     textColor=BLUE, fontSize=24, spaceAfter=4)
        h2_style = ParagraphStyle("h2", parent=styles["Heading2"],
                                  textColor=BLUE, fontSize=14, spaceBefore=14, spaceAfter=6)
        body_style = ParagraphStyle("body", parent=styles["Normal"],
                                    textColor=DARK, fontSize=10, leading=16)
        sub_style = ParagraphStyle("sub", parent=styles["Normal"],
                                   textColor=GRAY, fontSize=9)

        risk_color = {"Low": colors.green, "Medium": colors.orange,
                      "High": colors.red, "Critical": colors.darkred}

        story = []
        story.append(Paragraph("InsightAI", title_style))
        story.append(Paragraph("AI-Powered Decision Intelligence Report", sub_style))
        story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=12))

        # Meta
        meta_data = [
            ["Report Title", a.title],
            ["Generated", datetime.utcnow().strftime("%B %d, %Y %H:%M UTC")],
            ["Data Source", a.data_source.capitalize()],
            ["Records Analyzed", f"{a.row_count:,}"],
            ["Dimensions", str(a.column_count)],
            ["Risk Level", a.risk_level],
            ["Confidence Score", f"{int((a.confidence_score or 0) * 100)}%"],
            ["Decision Score", f"{a.decision_score or 0:.1f}/100"],
        ]
        t = Table(meta_data, colWidths=[5*cm, 11*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
            ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 16))

        story.append(Paragraph("Executive Summary", h2_style))
        story.append(Paragraph(a.executive_summary or "No summary available.", body_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Key Trends", h2_style))
        for i, trend in enumerate(a.get_key_trends(), 1):
            story.append(Paragraph(f"• {trend}", body_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph(f"Risk Assessment — {a.risk_level}", h2_style))
        story.append(Paragraph(a.risk_details or "", body_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Opportunities", h2_style))
        for opp in a.get_opportunities():
            story.append(Paragraph(f"• {opp}", body_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Recommended Actions", h2_style))
        actions = a.get_recommended_actions()
        if actions:
            act_data = [["Priority", "Action", "Expected Impact"]]
            for act in actions:
                act_data.append([
                    act.get("priority", ""),
                    act.get("action", ""),
                    act.get("impact", ""),
                ])
            at = Table(act_data, colWidths=[2.5*cm, 9.5*cm, 4*cm])
            at.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ]))
            story.append(at)
        story.append(Spacer(1, 16))

        story.append(HRFlowable(width="100%", thickness=1, color=GRAY, spaceAfter=8))
        story.append(Paragraph(
            f"Generated by InsightAI · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · "
            f"Powered by Google Gemini AI",
            sub_style))

        doc.build(story)
        buf.seek(0)
        safe_title = secure_filename(a.title or "report")
        return send_file(buf, mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"InsightAI_{safe_title}.pdf")
    except Exception as e:
        flash(f"Error generating report: {str(e)}", "danger")
        return redirect(url_for("analysis", analysis_id=analysis_id))


# ─── API helpers ──────────────────────────────────────────────────────────────
@app.route("/api/dashboard-stats")
@login_required
def api_dashboard_stats():
    analyses = Analysis.query.filter_by(user_id=current_user.id).all()
    risk_dist = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    scores = []
    dates = []
    for a in analyses:
        risk_dist[a.risk_level] = risk_dist.get(a.risk_level, 0) + 1
        if a.decision_score:
            scores.append(a.decision_score)
        dates.append(a.created_at.strftime("%b %d"))
    return jsonify({
        "risk_distribution": risk_dist,
        "decision_scores": scores,
        "dates": dates,
        "total": len(analyses),
    })


@app.route("/api/analysis/<int:analysis_id>/chart-data")
@login_required
def api_chart_data(analysis_id):
    a = Analysis.query.filter_by(id=analysis_id, user_id=current_user.id).first_or_404()
    return jsonify(a.get_chart_data())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
