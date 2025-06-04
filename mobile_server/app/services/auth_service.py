import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from flask import current_app, request, jsonify

from app import db
from app.models.user import User, Session

class AuthService:
    @staticmethod
    def _hash_password_sha256_static(password_string):
        """
        Menghitung hash SHA-256 dari password_string dengan static salt.
        """
        static_salt = current_app.config['STATIC_SALT']
        string_to_hash = password_string + static_salt
        return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()

    @staticmethod
    def register_user(email, password, name=None, role='pembeli'):
        """
        Mendaftarkan pengguna baru dengan menghash password menggunakan SHA-256 + static salt.
        """
        if User.query.filter_by(email=email).first():
            return None, "Email sudah terdaftar"

        password_hash = AuthService._hash_password_sha256_static(password)

        new_user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            role=role,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(new_user)
        try:
            db.session.commit()
            return new_user, None
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saat registrasi user: {e}")
            return None, "Gagal menyimpan user ke database"

    @staticmethod
    def login_user(email, password, client_type):
        # Cari user di DB
        user = User.query.filter_by(email=email).first()

        if not user:
            return None, "Kredensial salah"

        received_password_hash = AuthService._hash_password_sha256_static(password)

        if received_password_hash == user.password_hash:
            # Otentikasi berhasil
            if client_type == "mobile":
                # Hapus token lama untuk user ini jika ada (opsional, untuk memastikan hanya 1 token aktif per user)
                Session.query.filter_by(user_id=user.id).delete()
                db.session.commit()

                # Generate token acak yang aman
                token = secrets.token_urlsafe(64)

                expiry_time = datetime.now(timezone.utc) + timedelta(days=current_app.config['MOBILE_TOKEN_EXPIRY_DAYS'])

                new_session = Session(
                    user_id=user.id,
                    user_role=user.role,
                    token=token,
                    expiry_time=expiry_time,
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(new_session)
                try:
                    db.session.commit()
                    return {"user": user, "token": token, "role": user.role}, None
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error saat membuat sesi mobile: {e}")
                    return None, "Gagal membuat sesi"
            else:
                return None, "Jenis klien tidak didukung atau tidak valid untuk endpoint ini."
        else:
            return None, "Kredensial salah"

    @staticmethod
    def verify_auth_token(token):
        """
        Memverifikasi token otentikasi dan mengembalikan informasi pengguna jika valid.
        """
        session = Session.query.filter_by(token=token).first()

        current_app.logger.debug(f"Verify token: {token}")
        current_app.logger.debug(f"Session found: {session}")
        if session:
            current_app.logger.debug(f"Session expiry_time: {session.expiry_time}")
            current_app.logger.debug(f"Current UTC time (aware): {datetime.now(timezone.utc)}")

        if not session or session.expiry_time is None or session.expiry_time < datetime.now(timezone.utc):
            return None # Token tidak valid atau kadaluwarsa

        user = User.query.get(session.user_id)
        if not user:
            return None

        return user
