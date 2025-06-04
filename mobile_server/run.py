from app import create_app, db
from app.services.crawler_service import CrawlerService
import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = create_app()

def scheduled_crawl_job():
    print(f"[{datetime.now(timezone.utc)}] -- DEBUG: Fungsi scheduled_crawl_job dipanggil! --")

    with app.app_context():
        logger.info(f"[{datetime.now(timezone.utc)}] Memulai job crawling terjadwal...")
        
        seed_url_default = "https://www.jakmall.com/search?q=aksesoris%20fashion"
        crawling_limit_per_run = 1

        try:
            CrawlerService.start_jakmall_scraping_selenium(seed_url_default, crawling_limit_per_run)
            logger.info(f"[{datetime.now(timezone.utc)}] Job crawling terjadwal selesai.")
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Job crawling terjadwal gagal: {e}")

scheduler = BackgroundScheduler()

# --- Tambahkan job ini untuk eksekusi SEGERA saat startup ---
scheduler.add_job(scheduled_crawl_job, 'date', run_date=datetime.now(timezone.utc), id='initial_crawl_job') # <-- Job pertama, jalankan sekarang

# --- Job ini untuk eksekusi berulang SETELAH itu ---
scheduler.add_job(scheduled_crawl_job, 'interval', hours=1, id='recurring_crawl_job') # <-- Job berulang

if __name__ == '__main__':
    logger.info("Memulai aplikasi Flask dan scheduler...")

    scheduler.start()

    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)