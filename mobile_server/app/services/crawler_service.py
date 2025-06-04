import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser 
import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime, timezone
import json
import random 
from flask import current_app 

from app import db
from app.models.crawler import CrawlQueue
from app.models.product import ProductStaging, Product, Category, Brand, ProductImage, Inventory 
from sqlalchemy.exc import IntegrityError 


logger = logging.getLogger(__name__)

ROBOTS_PARSERS = {}

class CrawlerService:
    @staticmethod
    def _get_robot_parser(url):
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        if base_url not in ROBOTS_PARSERS:
            rp = RobotFileParser()
            try:
                rp.set_url(urljoin(base_url, "/robots.txt"))
                rp.read()
                ROBOTS_PARSERS[base_url] = rp
                logger.info(f"Berhasil membaca robots.txt dari {base_url}")
            except Exception as e:
                logger.warning(f"Gagal membaca robots.txt dari {base_url}: {e}. Melanjutkan tanpa robots.txt.")
                ROBOTS_PARSERS[base_url] = None
        return ROBOTS_PARSERS[base_url]

    @staticmethod
    def is_url_allowed_by_robots(url, user_agent="*"):
        rp = CrawlerService._get_robot_parser(url)
        if rp:
            return rp.can_fetch(user_agent, url)
        return True

    @staticmethod
    def fetch_html(url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Gagal mengambil HTML dari {url}: {e}")
            return None

    @staticmethod
    def _clean_price_string(price_text):
        if not price_text:
            return None
        cleaned_text = price_text.replace('Rp', '').replace(' ', '').replace('.', '').replace(',', '.')
        try:
            return float(cleaned_text)
        except ValueError:
            logger.warning(f"Gagal mengonversi harga '{price_text}' menjadi angka.")
            return None

    @staticmethod
    def scrape_jakmall_product_list_page(html_content, base_url):
        soup = BeautifulSoup(html_content, 'html.parser')
        products_data = []

        for item in soup.find_all('div', class_='pi__core'):
            try:
                link_tag = item.find('div', class_='pi__header').find('a')
                img_tag = item.find('span', class_='pi__image').find('img')
                nama_toko_tag = item.find('a', class_='link link--normal')
                lokasi_tag = item.find('div', class_='pi__seller__location')
                nama_tag = item.find('a', class_='pi__name link link--normal')
                harga_tag = item.find('div', class_='pi__price')
                rating_tag = item.find('article', class_='rating__stars')

                link = urljoin(base_url, link_tag['href']) if link_tag and link_tag.has_attr('href') else None
                img = img_tag['src'] if img_tag and img_tag.has_attr('src') else None
                nama_toko = nama_toko_tag.get_text(strip=True) if nama_toko_tag else None
                lokasi = lokasi_tag.get_text(strip=True) if lokasi_tag else None
                nama = nama_tag.get_text(strip=True) if nama_tag else None
                harga_text = harga_tag.get_text(strip=True) if harga_tag else None
                harga = CrawlerService._clean_price_string(harga_text)

                rating_total = 0.0
                review_count = 0
                if rating_tag:
                    stars = rating_tag.find_all('i', string='star')
                    half_stars = rating_tag.find_all('i', string='star_half')
                    review_span = rating_tag.find('span')
                    if review_span:
                        review_text = review_span.get_text(strip=True)
                        try:
                            review_count = int(review_text.strip('()'))
                        except ValueError:
                            review_count = 0
                    rating_total = len(stars) + 0.5 * len(half_stars)
                
                if not link or not nama or harga is None:
                    logger.warning(f"Melewatkan produk karena data tidak lengkap: {nama} - {harga_text} - {link}")
                    continue

                products_data.append({
                    'source_url': link,
                    'name': nama,
                    'description': None,
                    'price': harga,
                    'image_url': img,
                    'category': None,
                    'brand': nama_toko,
                    'status': 'raw',
                    'error_message': None,
                    'additional_data': {
                        'nama_toko': nama_toko,
                        'lokasi': lokasi,
                        'rating': rating_total,
                        'review_count': review_count,
                    }
                })
            except Exception as e:
                logger.error(f"Error saat scraping item produk di halaman Jakmall: {e}")
                continue
        return products_data

    @staticmethod
    def _extract_jakmall_pagination_links(html_content, current_url):
        soup = BeautifulSoup(html_content, 'html.parser')
        pagination_links = set()

        for a_tag in soup.select('div.paging a.paging--number, a.paging--next'):
            if a_tag.has_attr('href'):
                full_url = urljoin(current_url, a_tag['href'])
                
                parsed_current = urlparse(current_url)
                parsed_full = urlparse(full_url)
                
                if parsed_full.netloc == parsed_current.netloc and \
                   parsed_full.path == parsed_current.path:
                    
                    pagination_links.add(full_url)
        return list(pagination_links)

    @staticmethod
    def save_scraped_data(product_data):
        """
        Menyimpan data produk yang diekstrak ke tabel product_staging.
        Ini tetap per produk karena staging adalah tempat mentah.
        """
        if product_data:
            existing_product_staging = ProductStaging.query.filter_by(source_url=product_data['source_url']).first()
            
            additional_data = product_data.pop('additional_data', None)

            if existing_product_staging:
                for key, value in product_data.items():
                    setattr(existing_product_staging, key, value)
                existing_product_staging.extracted_at = datetime.now(timezone.utc)
                existing_product_staging.additional_data = additional_data
                db.session.add(existing_product_staging)
                logger.debug(f"Memperbarui data produk dari {product_data['source_url']} di product_staging.")
            else:
                new_product_staging = ProductStaging(**product_data)
                new_product_staging.additional_data = additional_data
                db.session.add(new_product_staging)
                logger.debug(f"Menyimpan data produk baru dari {product_data['source_url']} ke product_staging.")
        else:
            pass
        
        # COMMIT TIDAK LAGI DI SINI, AKAN DILAKUKAN PER SESI DI start_jakmall_scraping_selenium
        # try:
        #     db.session.commit()
        # except Exception as e:
        #     db.session.rollback()
        #     logger.error(f"Gagal menyimpan/memperbarui data staging untuk {product_data.get('source_url', 'N/A')}: {e}")

    @staticmethod
    def _ingest_staging_to_main_products(staging_product_data, min_stock, max_stock): # <-- Tambahkan min_stock, max_stock
        """
        Logika untuk memindahkan/memproses data dari staging ke tabel products utama dan Inventory.
        Ini akan menambahkan produk ke sesi DB, tetapi commit akan dilakukan di akhir sesi.
        """
        product_name = staging_product_data['name']
        product_price = staging_product_data['price']
        product_image_url = staging_product_data['image_url']
        product_brand_name = staging_product_data.get('brand')
        product_description = staging_product_data.get('description')
        source_url = staging_product_data['source_url']
        
        initial_stock = random.randint(min_stock, max_stock) # <-- Gunakan min_stock, max_stock dari argumen

        category_id = None 

        brand_id = None
        if product_brand_name:
            brand = Brand.query.filter_by(name=product_brand_name).first()
            if not brand:
                brand = Brand(name=product_brand_name, created_at=datetime.now(timezone.utc))
                db.session.add(brand)
                db.session.flush() # Flush untuk mendapatkan ID merek baru
                logger.debug(f"Merek baru dibuat: {product_brand_name}")
            brand_id = brand.id

        existing_product = Product.query.filter_by(source_url=source_url).first()
        
        if existing_product:
            logger.warning(f"Produk '{product_name}' dari URL '{source_url}' sudah ada di katalog utama. Memperbarui stok.")
            existing_inventory = Inventory.query.filter_by(product_id=existing_product.id).first()
            if existing_inventory:
                existing_inventory.quantity = initial_stock 
            else:
                new_inventory = Inventory(product_id=existing_product.id, quantity=initial_stock, last_updated=datetime.now(timezone.utc))
                db.session.add(new_inventory)
            # Commit tidak di sini, akan dilakukan per sesi
            return existing_product

        new_product = Product(
            name=product_name,
            description=product_description,
            price=product_price,
            category_id=category_id, 
            brand_id=brand_id,
            source_url=source_url,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(new_product)
        db.session.flush() # Flush untuk mendapatkan ID produk baru

        if product_image_url:
            new_image = ProductImage(
                product_id=new_product.id,
                image_url=product_image_url,
                is_main=True,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(new_image)
        else:
            logger.warning(f"DEBUG: No image URL provided for new product '{product_name}' from '{source_url}'. ProductImage entry will not be created.")
        
        new_inventory = Inventory(
            product_id=new_product.id,
            quantity=initial_stock, 
            last_updated=datetime.now(timezone.utc)
        )
        db.session.add(new_inventory)

        # Commit tidak di sini, akan dilakukan per sesi
        logger.debug(f"Produk '{product_name}' ditambahkan ke sesi DB. Akan di-commit nanti.")
        return new_product

    @staticmethod
    def _notify_mobile_client(new_products_data_list): # Menerima daftar produk
        """
        Mengirim POST request ke endpoint lokal di mobile client
        untuk memberitahu/mengirim data produk baru (batch).
        """
        mobile_client_endpoint = "http://10.0.2.2:8080/api/new_product_batch" # Endpoint bisa berbeda untuk batch

        if not new_products_data_list:
            return

        # Siapkan payload untuk batch
        batch_payload = []
        for product_data in new_products_data_list:
            payload_item = {
                "product_id": product_data.id,
                "product_name": product_data.name,
                "product_price": str(product_data.price),
                "image_url": next((img.image_url for img in product_data.images if img.is_main), None),
                "stock": product_data.inventory.quantity if product_data.inventory else 0
            }
            batch_payload.append(payload_item)

        try:
            response = requests.post(mobile_client_endpoint, json=batch_payload, timeout=10) # Tingkatkan timeout
            response.raise_for_status()
            logger.info(f"Notifikasi {len(new_products_data_list)} produk baru berhasil dikirim ke mobile.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Gagal mengirim notifikasi batch produk baru ke mobile ({mobile_client_endpoint}): {e}")
        except Exception as e:
            logger.error(f"Error tak terduga saat menyiapkan/mengirim notifikasi batch ke mobile: {e}")

    @staticmethod
    def start_jakmall_scraping_selenium(seed_url_query_param, crawling_limit=50):
        logger.info(f"Memulai scraping Jakmall dari {seed_url_query_param} dengan batas {crawling_limit} URL.")

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        driver = None
        processed_urls_count = 0 
        total_products_ingested = 0
        all_new_products_in_session = [] 

        try:
            driver = webdriver.Chrome(options=chrome_options)
            
            existing_seed_entry = CrawlQueue.query.get(seed_url_query_param)
            if not existing_seed_entry:
                db.session.add(CrawlQueue(url=seed_url_query_param, status='pending', added_at=datetime.now(timezone.utc)))
                logger.info(f"Seed URL '{seed_url_query_param}' ditambahkan ke antrian.")
            else:
                logger.info(f"Seed URL '{seed_url_query_param}' sudah ada di antrian (status: {existing_seed_entry.status}).")
                if existing_seed_entry.status == 'failed':
                    existing_seed_entry.status = 'pending'
            
            try:
                db.session.commit() 
            except Exception as e:
                db.session.rollback()
                logger.error(f"Gagal meng-commit seed URL awal: {e}")

            # Ambil nilai min_stock dan max_stock dari konfigurasi aplikasi
            min_stock_config = current_app.config['MIN_STOCK_RANDOM']
            max_stock_config = current_app.config['MAX_STOCK_RANDOM']


            while processed_urls_count < crawling_limit:
                current_queue_entry = CrawlQueue.query.filter_by(status='pending').order_by(CrawlQueue.added_at.asc()).first()
                if not current_queue_entry:
                    logger.info("Antrian crawling kosong. Selesai.")
                    break
                
                current_url = current_queue_entry.url
                
                current_queue_entry.status = 'in_progress'
                db.session.commit()

                logger.info(f"Memproses URL: {current_url}")
                
                if not CrawlerService.is_url_allowed_by_robots(current_url):
                    logger.info(f"Melewatkan URL {current_url} karena dilarang oleh robots.txt.")
                    current_queue_entry.status = 'failed'
                    current_queue_entry.error_message = 'Dilarang oleh robots.txt' 
                    db.session.commit()
                    continue
                
                time.sleep(3)

                try:
                    driver.get(current_url)
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "pi__core"))
                    )
                    html_content = driver.page_source
                except TimeoutException:
                    logger.warning(f"Timeout saat menunggu elemen di {current_url}. Melanjutkan ke URL berikutnya.")
                    current_queue_entry.status = 'failed'
                    current_queue_entry.error_message = 'Timeout saat memuat halaman'
                    db.session.commit()
                    continue
                except Exception as e:
                    logger.error(f"Gagal mengambil HTML dari {current_url} dengan Selenium: {e}")
                    current_queue_entry.status = 'failed'
                    current_queue_entry.error_message = f"Gagal mengambil HTML: {e}"
                    db.session.commit()
                    continue
                
                products_on_page = CrawlerService.scrape_jakmall_product_list_page(html_content, current_url)
                
                products_ingested_on_this_page = [] 
                for product_data in products_on_page:
                    CrawlerService.save_scraped_data(product_data) 

                    try:
                        # Teruskan min_stock_config dan max_stock_config ke _ingest_staging_to_main_products
                        new_product_main = CrawlerService._ingest_staging_to_main_products(
                            product_data, min_stock_config, max_stock_config # <-- Teruskan argumen stok
                        ) 
                        if new_product_main:
                            total_products_ingested += 1
                            products_ingested_on_this_page.append(new_product_main)
                            all_new_products_in_session.append(new_product_main)
                        
                    except IntegrityError as ie:
                        db.session.rollback()
                        logger.error(f"Produk '{product_data.get('name')}' gagal masuk katalog utama (IntegrityError): {ie}")
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"Produk '{product_data.get('name')}' gagal masuk katalog utama: {e}")
                
                logger.info(f"Selesai memproses {len(products_on_page)} produk dari {current_url}. {len(products_ingested_on_this_page)} produk baru/diperbarui masuk sesi DB dari halaman ini.")


                pagination_links = CrawlerService._extract_jakmall_pagination_links(html_content, current_url)
                for page_link in pagination_links:
                    if not CrawlQueue.query.get(page_link): 
                        db.session.add(CrawlQueue(url=page_link, status='pending', added_at=datetime.now(timezone.utc)))
                        try:
                            db.session.commit() 
                            logger.info(f"Link pagination baru ditambahkan ke antrian: {page_link}")
                        except IntegrityError:
                            db.session.rollback()
                            logger.debug(f"Link pagination '{page_link}' sudah ada di antrian. (IntegrityError)")
                        except Exception as e:
                            db.session.rollback()
                            logger.error(f"Gagal menambahkan link pagination '{page_link}' ke antrian: {e}")
                
                current_queue_entry.status = 'completed'
                db.session.commit()
                processed_urls_count += 1

            try:
                db.session.commit() 
                logger.info(f"Berhasil meng-commit {total_products_ingested} produk dan {processed_urls_count} URL ke katalog utama dan antrian.")
                CrawlerService._notify_mobile_client(all_new_products_in_session)
            except Exception as e:
                db.session.rollback()
                logger.error(f"Gagal meng-commit semua produk/URL dari sesi ini atau mengirim notifikasi: {e}")

            logger.info(f"Selesai scraping Jakmall. Total {processed_urls_count} URL diproses dalam sesi ini. Total {total_products_ingested} produk berhasil diimpor ke katalog utama.")
            return {"message": "Scraping Jakmall selesai", "total_urls_processed": processed_urls_count, "total_products_ingested": total_products_ingested}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error fatal saat menjalankan scraping Jakmall: {e}")
            return {"message": f"Scraping Jakmall gagal: {e}", "total_urls_processed": 0, "total_products_ingested": 0}
        finally:
            if driver:
                driver.quit()
                logger.info("ChromeDriver ditutup.")

    @staticmethod
    def export_data_to_csv(file_path='product_staging.csv'):
        products = ProductStaging.query.all()
        if not products:
            logger.info("Tidak ada data di product_staging untuk diekspor.")
            return False

        try:
            import csv
            
            fieldnames = [column.name for column in ProductStaging.__table__.columns]

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for product in products:
                    row = {
                        'id': product.id,
                        'source_url': product.source_url,
                        'name': product.name,
                        'description': product.description,
                        'price': float(product.price) if product.price is not None else None,
                        'image_url': product.image_url,
                        'category': product.category,
                        'brand': product.brand,
                        'extracted_at': product.extracted_at.isoformat() if product.extracted_at else None,
                        'status': product.status,
                        'error_message': product.error_message,
                        'additional_data': json.dumps(product.additional_data) if product.additional_data else None
                    }
                    writer.writerow(row)
            logger.info(f"Data staging berhasil diekspor ke {file_path}")
            return True
        except Exception as e:
            logger.error(f"Gagal mengekspor data ke CSV: {e}")
            return False

    @staticmethod
    def export_data_to_json(file_path='product_staging.json'):
        products = ProductStaging.query.all()
        if not products:
            logger.info("Tidak ada data di product_staging untuk diekspor.")
            return False

        data = []
        try:
            import json
            for product in products:
                product_dict = {
                    'id': product.id,
                    'source_url': product.source_url,
                    'name': product.name,
                    'description': product.description,
                    'price': float(product.price) if product.price is not None else None,
                    'image_url': product.image_url,
                    'category': product.category,
                    'brand': product.brand,
                    'extracted_at': product.extracted_at.isoformat() if product.extracted_at else None,
                    'status': product.status,
                    'error_message': product.error_message,
                    'additional_data': product.additional_data
                }
                data.append(product_dict)
            
            with open(file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, indent=4, ensure_ascii=False)
            logger.info(f"Data staging berhasil diekspor ke {file_path}")
            return True
        except Exception as e:
            logger.error(f"Gagal mengekspor data ke JSON: {e}")
            return False
