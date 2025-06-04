import os
import sys
import logging
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
import random # <-- Impor modul random

# Tambahkan direktori root proyek ke Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import create_app, db
from app.models.product import Product, Category, Brand, ProductImage, Inventory # Impor Inventory

# Konfigurasi logging untuk script ini
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def import_products_from_csv(csv_file_path):
    logger.info(f"Memulai impor produk dari CSV: {csv_file_path}")

    app = create_app()

    with app.app_context():
        try:
            df = pd.read_csv(csv_file_path)
            logger.info(f"Berhasil membaca {len(df)} baris dari CSV.")

            processed_count = 0
            skipped_count = 0

            for index, row in df.iterrows():
                try:
                    product_source_url = row.get('Link Produk') or row.get('source_url')
                    product_image_url = row.get('Link Gambar') or row.get('image_url')
                    product_brand_name = row.get('Nama Toko') or row.get('brand') 
                    
                    lokasi_csv = row.get('Lokasi') 
                    rating_csv = row.get('Rating')
                    review_csv = row.get('Review')

                    product_name = row.get('Nama Produk') or row.get('name')
                    product_price_str = str(row.get('Harga')) 
                    
                    product_description = row.get('description') or "" 
                    # Jika CSV memiliki kolom 'Kategori', gunakan itu. Jika tidak, default ke "Umum".
                    product_category_name = row.get('Kategori') or "Umum" 

                    if not product_name or not product_price_str:
                        logger.warning(f"Melewatkan baris {index + 1}: Nama produk atau harga tidak ditemukan.")
                        skipped_count += 1
                        continue
                    
                    try:
                        cleaned_price_str = product_price_str.replace('Rp', '').replace(' ', '').replace('.', '').replace(',', '.')
                        product_price = float(cleaned_price_str)
                    except ValueError:
                        logger.error(f"Melewatkan baris {index + 1}: Gagal mengonversi harga '{product_price_str}' menjadi angka.")
                        skipped_count += 1
                        continue

                    # --- Proses Kategori (Tetap dipertahankan untuk CSV) ---
                    category_id = None
                    if product_category_name:
                        category = Category.query.filter_by(name=product_category_name).first()
                        if not category:
                            category = Category(name=product_category_name, created_at=datetime.now(timezone.utc))
                            db.session.add(category)
                            db.session.flush()
                            logger.info(f"Kategori baru dibuat: {product_category_name}")
                        category_id = category.id

                    # --- Proses Merek (Tetap dipertahankan untuk CSV) ---
                    brand_id = None
                    if product_brand_name:
                        brand = Brand.query.filter_by(name=product_brand_name).first()
                        if not brand:
                            brand = Brand(name=product_brand_name, created_at=datetime.now(timezone.utc))
                            db.session.add(brand)
                            db.session.flush()
                            logger.info(f"Merek baru dibuat: {product_brand_name}")
                        brand_id = brand.id

                    existing_product = None
                    if product_source_url:
                        existing_product = Product.query.filter_by(source_url=product_source_url).first() 
                    
                    if existing_product:
                        logger.warning(f"Melewatkan produk duplikat: {product_name} (ID: {existing_product.id})")
                        skipped_count += 1
                        continue

                    new_product = Product(
                        name=product_name,
                        description=product_description,
                        price=product_price,
                        category_id=category_id,
                        brand_id=brand_id,
                        source_url=product_source_url, # Simpan source_url dari CSV
                        created_at=datetime.now(timezone.utc)
                    )
                    db.session.add(new_product)
                    db.session.flush()

                    if product_image_url:
                        new_image = ProductImage(
                            product_id=new_product.id,
                            image_url=product_image_url,
                            is_main=True,
                            created_at=datetime.now(timezone.utc)
                        )
                        db.session.add(new_image)
                    
                    # Acak nilai stok awal untuk produk dari CSV
                    initial_stock = random.randint(app.config['MIN_STOCK_RANDOM'], app.config['MAX_STOCK_RANDOM'])
                    
                    new_inventory = Inventory(
                        product_id=new_product.id,
                        quantity=initial_stock,
                        last_updated=datetime.now(timezone.utc)
                    )
                    db.session.add(new_inventory)

                    db.session.commit()
                    processed_count += 1
                    logger.info(f"Produk '{product_name}' berhasil diimpor.")

                except IntegrityError as ie:
                    db.session.rollback()
                    logger.error(f"Error integritas database saat memproses baris {index + 1} ({product_name}): {ie}. Baris dilewati.")
                    skipped_count += 1
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error tak terduga saat memproses baris {index + 1} ({product_name}): {e}. Baris dilewati.")
                    skipped_count += 1
            
            logger.info(f"Impor selesai. Total produk diproses: {processed_count}, dilewati: {skipped_count}.")

        except FileNotFoundError:
            logger.error(f"File CSV tidak ditemukan: {csv_file_path}")
        except pd.errors.EmptyDataError:
            logger.warning(f"File CSV kosong: {csv_file_path}")
        except Exception as e:
            logger.error(f"Terjadi kesalahan saat membaca atau memproses CSV: {e}")

if __name__ == '__main__':
    csv_path = 'jack.csv' # Sesuaikan dengan nama file CSV Anda

    if not os.path.exists(csv_path):
        logger.error(f"File CSV tidak ditemukan di: {csv_path}. Harap sesuaikan 'csv_path'.")
    else:
        import_products_from_csv(csv_path)

