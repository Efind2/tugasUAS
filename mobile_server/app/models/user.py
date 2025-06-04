from datetime import datetime, timezone
from app import db
from sqlalchemy.dialects.postgresql import JSONB

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='pembeli')
    name = db.Column(db.String(255))
    created_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    sessions = db.relationship('Session', backref='user', lazy=True, cascade="all, delete-orphan")
    activities = db.relationship('UserActivity', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"

class Session(db.Model):
    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    user_role = db.Column(db.String(50), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    expiry_time = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Session {self.token[:10]}... for User {self.user_id}>"

class UserActivity(db.Model):
    __tablename__ = 'user_activities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    activity_type = db.Column(db.String(100), nullable=False)
    related_id = db.Column(db.Integer, nullable=True)
    related_type = db.Column(db.String(50), nullable=True)
    details = db.Column(JSONB, nullable=True)
    timestamp = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))

    def __repr__(self):
        return f"<UserActivity {self.activity_type} by User {self.user_id} at {self.timestamp}>"