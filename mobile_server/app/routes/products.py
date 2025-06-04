from flask import Blueprint, request, jsonify, g, current_app
from app.models.product import Product, Category, Brand, ProductImage, Inventory
from app.routes.users import token_required, role_required
from app.services.activity_service import ActivityService
from app.schemas.product_schema import product_schema, products_schema
from app import db
from sqlalchemy import desc, asc
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone # <-- Correct import for datetime and timezone

products_bp = Blueprint('products', __name__)

@products_bp.route('/', methods=['GET'])
def list_products():
    """
    Endpoint untuk menampilkan daftar produk dengan pagination, sorting, dan multi-filter.
    Parameter query:
    - page (int): Nomor halaman. Default 1.
    - per_page (int): Jumlah item per halaman. Default dari config.
    - category_id (int): Filter berdasarkan ID kategori.
    - brand_id (int): Filter berdasarkan ID merek.
    - min_price (float): Filter harga minimal.
    - max_price (float): Filter harga maksimal.
    - search (str): Pencarian berdasarkan nama atau deskripsi produk (case-insensitive).
    - sort_by (str): Kolom untuk sorting (contoh: 'name', 'price', 'created_at', 'stock'). Bisa multiple, dipisahkan koma.
    - sort_order (str): Urutan sorting ('asc' atau 'desc'). Bisa multiple, dipisahkan koma, sesuai dengan sort_by.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', current_app.config['DEFAULT_PAGE_SIZE'], type=int)

    if per_page > current_app.config['MAX_PAGE_SIZE']:
        per_page = current_app.config['MAX_PAGE_SIZE']
    elif per_page < 1:
        per_page = 1

    query = Product.query

    category_id = request.args.get('category_id', type=int)
    brand_id = request.args.get('brand_id', type=int)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    search_term = request.args.get('search', type=str)

    if category_id:
        query = query.filter_by(category_id=category_id)
    if brand_id:
        query = query.filter_by(brand_id=brand_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if search_term:
        search_pattern = f"%{search_term}%"
        query = query.filter(
            (Product.name.ilike(search_pattern)) |
            (Product.description.ilike(search_pattern))
        )

    sort_by_param = request.args.get('sort_by', 'created_at')
    sort_order_param = request.args.get('sort_order', 'desc')

    ALLOWED_SORT_COLUMNS = {
        'name': Product.name,
        'price': Product.price,
        'created_at': Product.created_at,
        'stock': Inventory.quantity
    }
    ALLOWED_SORT_ORDERS = {'asc': asc, 'desc': desc}

    sort_columns = [col.strip() for col in sort_by_param.split(',')]
    sort_orders = [order.strip() for order in sort_order_param.split(',')]

    if len(sort_columns) != len(sort_orders) and len(sort_orders) == 1:
        sort_orders = [sort_orders[0]] * len(sort_columns)
    elif len(sort_columns) != len(sort_orders):
        return jsonify({"message": "Jumlah kolom sort_by dan sort_order tidak cocok."}), 400

    order_by_clauses = []
    for i, col_name in enumerate(sort_columns):
        if col_name in ALLOWED_SORT_COLUMNS:
            order_func = ALLOWED_SORT_ORDERS.get(sort_orders[i].lower(), desc)
            order_by_clauses.append(order_func(ALLOWED_SORT_COLUMNS[col_name]))
        else:
            return jsonify({"message": f"Kolom sorting '{col_name}' tidak valid."}), 400
    
    if 'stock' in sort_columns or any(col in ALLOWED_SORT_COLUMNS for col in sort_columns if ALLOWED_SORT_COLUMNS[col] == Inventory.quantity):
        query = query.join(Inventory, Product.id == Inventory.product_id)

    if order_by_clauses:
        query = query.order_by(*order_by_clauses)

    query = query.options(
        joinedload(Product.category),
        joinedload(Product.brand),
        joinedload(Product.images),
        joinedload(Product.inventory)
    )

    products_pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    products_list = products_schema.dump(products_pagination.items)
    
    return jsonify({
        "products": products_list,
        "total_items": products_pagination.total,
        "total_pages": products_pagination.pages,
        "current_page": products_pagination.page,
        "per_page": products_pagination.per_page,
        "has_next": products_pagination.has_next,
        "has_prev": products_pagination.has_prev
    }), 200

@products_bp.route('/<int:product_id>', methods=['GET'])
@token_required
def get_product_detail(product_id):
    """
    Endpoint untuk mendapatkan detail produk berdasarkan ID.
    """
    product = Product.query.options(
        joinedload(Product.category),
        joinedload(Product.brand),
        joinedload(Product.images),
        joinedload(Product.inventory)
    ).get(product_id)

    if not product:
        return jsonify({"message": "Produk tidak ditemukan"}), 404
    
    if hasattr(g, 'current_user'):
        ActivityService.log_user_activity(
            user_id=g.current_user.id,
            activity_type='view_product',
            related_type='product',
            related_id=product.id
        )

    response_data = product_schema.dump(product)
    
    return jsonify(response_data), 200