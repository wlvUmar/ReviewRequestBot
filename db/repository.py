# db/repository.py — All SQL queries. Services call this. Never write SQL elsewhere.
from db.connection import get_connection


class BotRepository:

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def upsert_user(self, telegram_id: int, username: str, first_name: str) -> None:
        """Insert or update a bot user. Called on /start."""
        sql = """
            INSERT INTO bot_users (telegram_id, username, first_name)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                username    = VALUES(username),
                first_name  = VALUES(first_name),
                last_seen   = NOW()
        """
        self._execute(sql, (telegram_id, username, first_name))

    def get_user(self, telegram_id: int) -> dict | None:
        rows = self._fetchall(
            "SELECT * FROM bot_users WHERE telegram_id = %s LIMIT 1",
            (telegram_id,)
        )
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

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
                (request_id, telegram_id, tg_file_id, description, status)
            VALUES (%s, %s, %s, %s, 'pending')
            ON DUPLICATE KEY UPDATE
                tg_file_id  = VALUES(tg_file_id),
                description = VALUES(description)
        """
        self._execute(sql, (request_id, telegram_id, file_id, description))

    def get_request(self, request_id: int) -> dict | None:
        rows = self._fetchall(
            "SELECT * FROM bot_request_mappings WHERE request_id = %s LIMIT 1",
            (request_id,)
        )
        return rows[0] if rows else None

    def mark_request_notified(self, request_id: int) -> None:
        self._execute(
            "UPDATE bot_request_mappings SET status = 'notified', notified_at = NOW() WHERE request_id = %s",
            (request_id,)
        )

    def get_pending_unnotified(self) -> list[dict]:
        """Fetch requests that have a result but haven't been notified yet (safety net)."""
        return self._fetchall(
            "SELECT * FROM bot_request_mappings WHERE status IN ('approved','rejected') AND notified_at IS NULL"
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _execute(self, sql: str, params: tuple = ()) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
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