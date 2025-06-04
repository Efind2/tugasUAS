import logging
from datetime import datetime, timezone
from app import db
from app.models.user import UserActivity

logger = logging.getLogger(__name__)

class ActivityService:
    @staticmethod
    def log_user_activity(user_id, activity_type, related_type=None, related_id=None, details=None):
        """
        Mencatat aktivitas pengguna ke database.
        Args:
            user_id (int): ID pengguna yang melakukan aktivitas.
            activity_type (str): Jenis aktivitas (misal: 'login', 'view_product', 'add_to_cart', 'purchase').
            related_type (str, optional): Jenis objek terkait (misal: 'product', 'order'). Default None.
            related_id (int, optional): ID objek terkait. Default None.
            details (dict, optional): Detail tambahan dalam format JSON (misal: {'quantity': 2, 'price': 150000}). Default None.
        """
        try:
            new_activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                related_type=related_type,
                related_id=related_id,
                details=details,
                timestamp=datetime.now(timezone.utc)
            )
            db.session.add(new_activity)
            db.session.commit()
            logger.info(f"Aktivitas dicatat: User {user_id} - {activity_type}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Gagal mencatat aktivitas untuk user {user_id}: {e}")