from datetime import datetime, timezone
from app import db
from sqlalchemy.dialects.postgresql import JSONB

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"

class Brand(db.Model):
    __tablename__ = 'brands'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    products = db.relationship('Product', backref='brand', lazy=True)

    def __repr__(self):
        return f"<Brand {self.name}>"

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    is_main = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))

    def __repr__(self):
        return f"<ProductImage {self.image_url} for Product {self.product_id}>"

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), unique=True, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    last_updated = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Inventory Product {self.product_id} - Qty: {self.quantity}>"

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(15, 2), nullable=False)
    source_url = db.Column(db.String(255), unique=True, nullable=True) # <-- TAMBAHKAN INI, nullable=True jika tidak semua produk dari scraping
    
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.id', ondelete='SET NULL'), nullable=True)

    created_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    images = db.relationship('ProductImage', backref='product', lazy=True, cascade="all, delete-orphan")
    inventory = db.relationship('Inventory', backref='product', lazy=True, uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product {self.name}>"

class ProductStaging(db.Model):
    __tablename__ = 'product_staging'

    id = db.Column(db.Integer, primary_key=True)
    source_url = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(15, 2), nullable=False)
    image_url = db.Column(db.String(255))
    category = db.Column(db.String(100))
    brand = db.Column(db.String(100))
    extracted_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))
    status = db.Column(db.String(50), nullable=False, default='raw')
    error_message = db.Column(db.Text)
    additional_data = db.Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<ProductStaging {self.name} from {self.source_url}>"
