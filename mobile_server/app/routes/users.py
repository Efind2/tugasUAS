from flask import Blueprint, request, jsonify, g, current_app, url_for, send_from_directory
from functools import wraps
from app.services.auth_service import AuthService
from app.services.activity_service import ActivityService
from app.models.user import User, UserActivity
from app.models.product import Product # Import Product untuk JOIN di activities
from app.schemas.user_schema import UserSchema
from datetime import datetime, timezone
import os
from werkzeug.utils import secure_filename
from app import db

users_bp = Blueprint('users', __name__)
user_schema = UserSchema()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"message": "Header otorisasi tidak ditemukan"}), 401

        try:
            token_type, token = auth_header.split(' ', 1)
            if token_type.lower() != 'bearer':
                raise ValueError("Tipe token tidak valid. Gunakan 'Bearer'.")
        except ValueError:
            return jsonify({"message": "Format header otorisasi tidak valid. Gunakan 'Bearer <token>'."}), 401

        current_user = AuthService.verify_auth_token(token)

        if not current_user:
            return jsonify({"message": "Token tidak valid atau kadaluwarsa"}), 401

        g.current_user = current_user
        return f(*args, **kwargs)
    return decorated

# --- Decorator untuk otorisasi peran ---
def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({"message": "Pengguna tidak terotentikasi"}), 401
            
            if g.current_user.role != required_role:
                return jsonify({"message": "Tidak diizinkan. Peran tidak sesuai."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@users_bp.route('/profile', methods=['GET'])
@token_required
def get_user_profile():
    """
    Endpoint untuk mendapatkan profil pengguna yang sedang login.
    Membutuhkan token otentikasi.
    """
    user_data = user_schema.dump(g.current_user)
    ActivityService.log_user_activity(g.current_user.id, 'view_profile')
    return jsonify(user_data), 200

# --- ENDPOINT BARU UNTUK MENGGANTI USERNAME ---
@users_bp.route('/profile/username', methods=['PUT']) # <-- Ubah URL dan metode
@token_required
def update_username():
    """
    Endpoint untuk memperbarui username (nama pengguna) yang sedang login.
    Membutuhkan token otentikasi.
    Menerima JSON body dengan field 'name'.
    """
    data = request.get_json()
    new_name = data.get('name')

    if not new_name or not isinstance(new_name, str) or len(new_name.strip()) == 0:
        return jsonify({"message": "Nama pengguna baru tidak valid."}), 400

    try:
        user = g.current_user # Ambil objek user dari g
        user.name = new_name.strip() # Perbarui nama
        db.session.commit()

        ActivityService.log_user_activity(user.id, 'update_username', details={'old_name': user.name, 'new_name': new_name.strip()})
        
        # Serialisasi ulang user untuk respons
        response_data = user_schema.dump(user)
        return jsonify({"message": "Nama pengguna berhasil diperbarui.", "user": response_data}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal memperbarui username untuk user {g.current_user.id}: {e}")
        return jsonify({"message": "Gagal memperbarui nama pengguna."}), 500


@users_bp.route('/history', methods=['GET'])
@token_required
def get_purchase_history():
    """
    Endpoint untuk mendapatkan riwayat belanja pengguna.
    Membutuhkan token otentikasi.
    """
    ActivityService.log_user_activity(g.current_user.id, 'view_purchase_history')
    return jsonify({"message": f"Ini adalah riwayat belanja untuk {g.current_user.email}", "history": []}), 200

@users_bp.route('/activities', methods=['GET'])
@token_required
def get_user_activities():
    """
    Endpoint untuk mendapatkan daftar aktivitas pengguna yang sedang login dengan pagination.
    Mendukung filter berdasarkan 'type'.
    Parameter query: page (int), per_page (int), type (str)
    """
    user_id = g.current_user.id
    activity_filter_type = request.args.get('type')

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', current_app.config['DEFAULT_PAGE_SIZE'], type=int)

    if per_page > current_app.config['MAX_PAGE_SIZE']:
        per_page = current_app.config['MAX_PAGE_SIZE']
    elif per_page < 1:
        per_page = 1

    query = UserActivity.query.filter_by(user_id=user_id)

    if activity_filter_type:
        query = query.filter_by(activity_type=activity_filter_type)
    
    activities_pagination = query.order_by(UserActivity.timestamp.desc())\
                                .paginate(page=page, per_page=per_page, error_out=False)

    formatted_activities = []
    for activity in activities_pagination.items:
        display_text = "Aktivitas tidak dikenal"
        related_object_name = None

        if activity.activity_type == 'login':
            display_text = "Login ke akun"
        elif activity.activity_type == 'view_profile':
            display_text = "Melihat profil akun"
        elif activity.activity_type == 'view_product' and activity.related_type == 'product' and activity.related_id:
            product = Product.query.get(activity.related_id)
            if product:
                related_object_name = product.name
                display_text = f"Melihat produk '{product.name}'"
            else:
                display_text = f"Melihat produk (ID: {activity.related_id})"
        elif activity.activity_type == 'add_to_cart' and activity.related_type == 'product' and activity.related_id:
            product = Product.query.get(activity.related_id)
            quantity = activity.details.get('quantity', 1) if activity.details else 1
            if product:
                related_object_name = product.name
                display_text = f"Menambah {quantity}x produk '{product.name}' ke keranjang"
            else:
                display_text = f"Menambah {quantity}x produk (ID: {activity.related_id}) ke keranjang"

        formatted_activities.append({
            "id": activity.id,
            "type": activity.activity_type,
            "display_text": display_text,
            "timestamp": activity.timestamp.isoformat(),
            "related_id": activity.related_id,
            "related_type": activity.related_type,
            "related_object_name": related_object_name,
            "details": activity.details
        })

    return jsonify({
        "activities": formatted_activities,
        "total_items": activities_pagination.total,
        "total_pages": activities_pagination.pages,
        "current_page": activities_pagination.page,
        "per_page": activities_pagination.per_page,
        "has_next": activities_pagination.has_next,
        "has_prev": activities_pagination.has_prev
    }), 200
