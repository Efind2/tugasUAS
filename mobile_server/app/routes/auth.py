from flask import Blueprint, request, jsonify
from app.services.auth_service import AuthService
from app.schemas.user_schema import UserSchema
from app import db 

auth_bp = Blueprint('auth', __name__)
user_schema = UserSchema()

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Endpoint untuk registrasi pengguna baru.
    Menerima password plain-text melalui HTTPS.
    """
    try:
        user_data = user_schema.load(request.get_json())
        email = user_data['email']
        password = user_data['password']
        name = user_data.get('name')

        user, error_message = AuthService.register_user(email, password, name)

        if user:
            return jsonify({"message": "Registrasi berhasil"}), 201
        else:
            return jsonify({"message": error_message}), 409

    except Exception as e:
        return jsonify({"message": str(e)}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Endpoint untuk login pengguna.
    Menerima password plain-text melalui HTTPS dan mengembalikan token mobile.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    client_type = data.get('client_type', 'mobile')

    if not email or not password:
        return jsonify({"message": "Email dan password wajib diisi"}), 400

    if client_type not in ["mobile"]:
        return jsonify({"message": "Jenis klien tidak valid atau tidak didukung"}), 400

    auth_result, error_message = AuthService.login_user(email, password, client_type)

    if auth_result:
        return jsonify({
            "message": "Login berhasil",
            "user_role": auth_result['role'],
            "auth_token": auth_result['token']
        }), 200
    else:
        return jsonify({"message": error_message}), 401