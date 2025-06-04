import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'kunci_rahasia_yang_sangat_kuat_dan_acak_di_produksi'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                            'postgresql://postgres:1@localhost:5432/server_mobile'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STATIC_SALT = os.environ.get('STATIC_SALT') or 'ini_adalah_static_salt_anda_yang_super_panjang_dan_rahasia_di_dev'

    MOBILE_TOKEN_EXPIRY_DAYS = 90

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

      # Konfigurasi Rentang Stok Acak
    MIN_STOCK_RANDOM = 10  # Stok minimum saat diacak
    MAX_STOCK_RANDOM = 100 # Stok maksimum saat diacak
