import aiomysql
from config import Config
from utils.logger import log_msg

_pool: aiomysql.Pool | None = None

async def get_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        try:
            _pool = await aiomysql.create_pool(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                db=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                autocommit=True,
                charset="utf8mb4",
                minsize=2,
                maxsize=5,
            )
        except Exception as e:
            _pool = None
            log_msg(f"Pool Error {e}", level="ERROR")

    return _pool

async def get_connection():
    try:
        pool = await get_pool()
        conn = await pool.acquire()
    except Exception as e:
        log_msg(f"Connection Error {e}", level="ERROR")
        conn = None
    return conn

async def release_connection(conn) -> None:
    """Return a connection to the pool instead of destroying it."""
    if conn is None:
        return
    try:
        pool = await get_pool()
        pool.release(conn)
    except Exception as e:
        log_msg(f"Release Error {e}", level="ERROR")