from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from .config import Config
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db = SQLAlchemy()
ma = Marshmallow()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    ma.init_app(app)

    from .models.user import User, Session, UserActivity
    from .models.product import Product, ProductStaging, Category, Brand, ProductImage, Inventory
    from .models.crawler import CrawlQueue
    
    # Import skema produk di sini juga (atau melalui __init__.py di schemas/)
    # Ini memastikan Marshmallow tahu tentang skema-skema tersebut
    from .schemas.user_schema import UserSchema # UserSchema diimpor di sini
    from .schemas.product_schema import ProductSchema # <-- Penting: Impor ProductSchema agar terdaftar

    from .routes.auth import auth_bp
    from .routes.users import users_bp
    from .routes.products import products_bp
    from .routes.crawler import crawler_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(products_bp, url_prefix='/api/products')
    app.register_blueprint(crawler_bp, url_prefix='/api/crawler')

    with app.app_context():
        db.create_all()
        logger.info("Tabel database telah dibuat (jika belum ada).")
    
    return app