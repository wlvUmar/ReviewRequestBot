# db/repository.py — All SQL queries (async). Services call this. Never write SQL elsewhere.
import aiomysql
from db.connection import get_connection
from utils.logger import log_msg


class BotRepository:
    async def upsert_user(self, telegram_id: int, username: str, first_name: str) -> None:
        sql = """
            INSERT INTO bot_users (telegram_id, username, first_name)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                username    = VALUES(username),
                first_name  = VALUES(first_name)
        """
        await self._execute(sql, (telegram_id, username, first_name))

    async def get_user(self, telegram_id: int) -> dict | None:
        rows = await self._fetchall(
            "SELECT * FROM bot_users WHERE telegram_id = %s LIMIT 1",
            (telegram_id,)
        )
        return rows[0] if rows else None

    async def save_request(
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
        await self._execute(sql, (request_id, telegram_id))

    async def get_request(self, request_id: int) -> dict | None:
        rows = await self._fetchall(
            "SELECT * FROM bot_request_mappings WHERE request_id = %s LIMIT 1",
            (request_id,)
        )
        return rows[0] if rows else None

    async def mark_request_notified(self, request_id: int) -> None:
        await self._execute(
            "UPDATE bot_request_mappings SET notification_sent = 1 WHERE request_id = %s",
            (request_id,)
        )

    async def claim_request_notification(self, request_id: int) -> bool:
        conn = await get_connection()
        if conn is None:
            return False
        try:
            conn.autocommit(False)
            cursor = await conn.cursor(aiomysql.DictCursor)
            await cursor.execute(
                "SELECT notification_sent FROM bot_request_mappings WHERE request_id = %s LIMIT 1 FOR UPDATE",
                (request_id,)
            )
            row = await cursor.fetchone()
            if not row:
                await conn.rollback()
                log_msg(f"[repo] claim missing request_id={request_id}")
                return False

            state = row.get("notification_sent")
            if state in (1, 2):
                await conn.rollback()
                log_msg(f"[repo] claim already handled request_id={request_id} state={state}")
                return True

            await cursor.execute(
                "UPDATE bot_request_mappings SET notification_sent = 2 WHERE request_id = %s",
                (request_id,)
            )
            await conn.commit()
            log_msg(f"[repo] claim acquired request_id={request_id}")
            return True
        except Exception as e:
            await conn.rollback()
            log_msg(f"[repo] claim error request_id={request_id}: {e}")
            raise
        finally:
            conn.close()

    async def release_request_notification(self, request_id: int) -> None:
        conn = await get_connection()
        if conn is None:
            return
        try:
            conn.autocommit(False)
            cursor = await conn.cursor()
            await cursor.execute(
                "UPDATE bot_request_mappings SET notification_sent = 0 WHERE request_id = %s AND notification_sent = 2",
                (request_id,)
            )
            await conn.commit()
        finally:
            conn.close()

    async def get_pending_unnotified(self) -> list[dict]:
        return await self._fetchall(
            "SELECT * FROM bot_request_mappings WHERE notification_sent = 0"
        )

    async def _execute(self, sql: str, params: tuple = ()) -> None:
        conn = await get_connection()
        if conn is None:
            return
        try:
            cursor = await conn.cursor()
            await cursor.execute(sql, params)
            await conn.commit()
        finally:
            conn.close()

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = await get_connection()
        if conn is None:
            return []
        try:
            cursor = await conn.cursor(aiomysql.DictCursor)
            await cursor.execute(sql, params)
            return await cursor.fetchall()
        finally:
            conn.close()
