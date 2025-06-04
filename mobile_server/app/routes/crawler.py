from flask import Blueprint, request, jsonify
from app.services.crawler_service import CrawlerService
from app.routes.users import token_required, role_required
import threading
import logging

crawler_bp = Blueprint('crawler', __name__)
logger = logging.getLogger(__name__)

@crawler_bp.route('/start-jakmall-selenium', methods=['POST'])
@token_required
@role_required('admin')
def start_jakmall_scraping():
    """
    Endpoint untuk memicu proses scraping Jakmall menggunakan Selenium.
    """
    data = request.get_json()
    seed_url = data.get('seed_url', "https://www.jakmall.com/search?q=aksesoris+tangan+gelang")
    crawling_limit = data.get('crawling_limit', 50)

    if not seed_url:
        return jsonify({"message": "seed_url wajib diisi."}), 400
    
    threading.Thread(
        target=CrawlerService.start_jakmall_scraping_selenium,
        args=(seed_url, crawling_limit)
    ).start()

    return jsonify({"message": "Proses scraping Jakmall dimulai di background."}), 202

@crawler_bp.route('/export', methods=['GET'])
@token_required
@role_required('admin')
def export_data():
    """
    Endpoint untuk mengekspor data hasil scraping ke CSV atau JSON.
    """
    format_type = request.args.get('format', 'csv').lower()
    file_path = f"product_staging.{format_type}"

    success = False
    if format_type == 'csv':
        success = CrawlerService.export_data_to_csv(file_path)
    elif format_type == 'json':
        success = CrawlerService.export_data_to_json(file_path)
    else:
        return jsonify({"message": "Format ekspor tidak didukung. Gunakan 'csv' atau 'json'."}), 400

    if success:
        return jsonify({"message": f"Data berhasil diekspor ke {file_path}"}), 200
    else:
        return jsonify({"message": "Gagal mengekspor data."}), 500