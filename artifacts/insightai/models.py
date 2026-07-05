from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyses = db.relationship("Analysis", backref="user", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Analysis(db.Model):
    __tablename__ = "analyses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    data_source = db.Column(db.String(50), default="upload")  # upload | manual
    original_filename = db.Column(db.String(255))
    row_count = db.Column(db.Integer, default=0)
    column_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # AI results stored as JSON strings
    executive_summary = db.Column(db.Text)
    key_trends = db.Column(db.Text)       # JSON list
    risk_level = db.Column(db.String(20), default="Medium")
    risk_details = db.Column(db.Text)
    opportunities = db.Column(db.Text)   # JSON list
    recommended_actions = db.Column(db.Text)  # JSON list
    confidence_score = db.Column(db.Float, default=0.0)
    decision_score = db.Column(db.Float, default=0.0)
    anomalies = db.Column(db.Text)       # JSON list
    predictions = db.Column(db.Text)     # JSON list
    chart_data = db.Column(db.Text)      # JSON
    raw_stats = db.Column(db.Text)       # JSON

    def get_key_trends(self):
        try:
            return json.loads(self.key_trends) if self.key_trends else []
        except Exception:
            return []

    def get_opportunities(self):
        try:
            return json.loads(self.opportunities) if self.opportunities else []
        except Exception:
            return []

    def get_recommended_actions(self):
        try:
            return json.loads(self.recommended_actions) if self.recommended_actions else []
        except Exception:
            return []

    def get_anomalies(self):
        try:
            return json.loads(self.anomalies) if self.anomalies else []
        except Exception:
            return []

    def get_predictions(self):
        try:
            return json.loads(self.predictions) if self.predictions else []
        except Exception:
            return []

    def get_chart_data(self):
        try:
            return json.loads(self.chart_data) if self.chart_data else {}
        except Exception:
            return {}

    def get_raw_stats(self):
        try:
            return json.loads(self.raw_stats) if self.raw_stats else {}
        except Exception:
            return {}

    def risk_badge_class(self):
        mapping = {"Low": "success", "Medium": "warning", "High": "danger", "Critical": "danger"}
        return mapping.get(self.risk_level, "secondary")

    def __repr__(self):
        return f"<Analysis {self.title}>"
