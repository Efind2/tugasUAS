from app import ma
from app.models.product import Product, Category, Brand, ProductImage, Inventory
from datetime import datetime, timezone # Pastikan ini diimpor jika ada field datetime di skema

# Skema untuk Category
class CategorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Category
        load_instance = True
        fields = ("id", "name", "description") # Bidang yang ingin diekspos/diizinkan

# Skema untuk Brand
class BrandSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Brand
        load_instance = True
        fields = ("id", "name", "description") # Bidang yang ingin diekspos/diizinkan

# Skema untuk ProductImage
class ProductImageSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ProductImage
        load_instance = True
        fields = ("id", "image_url", "is_main") # Bidang yang ingin diekspos/diizinkan

# Skema untuk Inventory
class InventorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Inventory
        load_instance = True
        fields = ("quantity", "last_updated") # Hanya quantity dan last_updated dari Inventory

# Skema Utama untuk Product
class ProductSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Product
        load_instance = True # Memungkinkan .load() mengembalikan instance model jika diperlukan

        # Bidang yang diekspos/diizinkan untuk input/output.
        fields = (
            "id", "name", "description", "price", "source_url",
            "category_id", # <-- Sekarang akan dideklarasikan secara eksplisit di bawah
            "brand_id",    # <-- Sekarang akan dideklarasikan secara eksplisit di bawah
            "created_at",
            "updated_at",
            "category",
            "brand",
            "images",
            "stock",
            "main_image_url_input",
            "initial_stock_input"
        )
        
        # Bidang yang hanya untuk output (tidak bisa di-input klien)
        dump_only = (
            "id", "created_at", "updated_at",
            "category", "brand", "images", "stock" # Stock dan relasi bersarang hanya output dari model
        )

        # Bidang yang hanya untuk input (tidak akan muncul di output)
        load_only = ("main_image_url_input", "initial_stock_input")

    # Deklarasikan category_id dan brand_id secara eksplisit
    category_id = ma.Integer(required=False, allow_none=True) # required=False untuk PUT, allow_none=True untuk SET NULL
    brand_id = ma.Integer(required=False, allow_none=True) # required=False untuk PUT, allow_none=True untuk SET NULL

    # Relasi bersarang (hanya untuk dump/output)
    category = ma.Nested(CategorySchema, dump_only=True)
    brand = ma.Nested(BrandSchema, dump_only=True)
    images = ma.List(ma.Nested(ProductImageSchema), dump_only=True)
    
    # Custom field untuk stock dari tabel Inventory (hanya untuk dump/output)
    stock = ma.Method("get_stock_quantity", dump_only=True)

    def get_stock_quantity(self, obj):
        if obj.inventory:
            return obj.inventory.quantity
        return 0
    
    # Field virtual untuk menerima input URL gambar utama
    main_image_url_input = ma.String(required=False, allow_none=True, load_only=True)

    # Field virtual untuk menerima input stok awal (untuk POST) atau update stok (untuk PUT)
    initial_stock_input = ma.Integer(required=False, allow_none=True, load_only=True)


# Instance skema untuk digunakan di rute
product_schema = ProductSchema()
products_schema = ProductSchema(many=True) # Untuk serialisasi daftar produk
