# db/repository.py — All SQL queries. Services call this. Never write SQL elsewhere.
from db.connection import get_connection
from utils.logger import log_msg
 

class BotRepository:
    def upsert_user(self, telegram_id: int, username: str, first_name: str) -> None:
        sql = """
            INSERT INTO bot_users (telegram_id, username, first_name)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                username    = VALUES(username),
                first_name  = VALUES(first_name)
        """
        self._execute(sql, (telegram_id, username, first_name))

    def get_user(self, telegram_id: int) -> dict | None:
        rows = self._fetchall(
            "SELECT * FROM bot_users WHERE telegram_id = %s LIMIT 1",
            (telegram_id,)
        )
        return rows[0] if rows else None

    def save_request(
        self,
        request_id: int,
        telegram_id: int,
        file_id: str,
        description: str,
    ) -> None:
        """Store the mapping between a PHP request_id and a Telegram user."""
        sql = """
            INSERT INTO bot_request_mappings
                (request_id, telegram_id, notification_sent)
            VALUES (%s, %s, 0)
        """
        self._execute(sql, (request_id, telegram_id))

    def get_request(self, request_id: int) -> dict | None:
        rows = self._fetchall(
            "SELECT * FROM bot_request_mappings WHERE request_id = %s LIMIT 1",
            (request_id,)
        )
        return rows[0] if rows else None

    def mark_request_notified(self, request_id: int) -> None:
        self._execute(
            "UPDATE bot_request_mappings SET notification_sent = 1 WHERE request_id = %s",
            (request_id,)
        )

    def claim_request_notification(self, request_id: int) -> bool:
        conn = get_connection()
        try:
            conn.start_transaction()
            cursor = conn.cursor(buffered=True, dictionary=True)
            cursor.execute(
                "SELECT notification_sent FROM bot_request_mappings WHERE request_id = %s LIMIT 1 FOR UPDATE",
                (request_id,)
            )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                log_msg(f"[repo] claim missing request_id={request_id}")
                return False

            state = row.get("notification_sent")
            if state in (1, 2):
                conn.rollback()
                log_msg(f"[repo] claim already handled request_id={request_id} state={state}")
                return True

            cursor.execute(
                "UPDATE bot_request_mappings SET notification_sent = 2 WHERE request_id = %s",
                (request_id,)
            )
            conn.commit()
            log_msg(f"[repo] claim acquired request_id={request_id}")
            return True
        except Exception as e:
            conn.rollback()
            log_msg(f"[repo] claim error request_id={request_id}: {e}")
            raise
        finally:
            conn.close()

    def release_request_notification(self, request_id: int) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE bot_request_mappings SET notification_sent = 0 WHERE request_id = %s AND notification_sent = 2",
                (request_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def get_pending_unnotified(self) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM bot_request_mappings WHERE notification_sent = 0"
        )

    def _execute(self, sql: str, params: tuple = ()) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            conn.close()
