from datetime import datetime, timezone
from app import db

class CrawlQueue(db.Model):
    __tablename__ = 'crawl_queue_cukup'

    url = db.Column(db.String(255), primary_key=True)
    status = db.Column(db.String(50), default='pending')
    added_at = db.Column(db.TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))

    def __repr__(self):
        return f"<CrawlQueue {self.url} - {self.status}>"