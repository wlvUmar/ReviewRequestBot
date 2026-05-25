import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from config import Config
from utils.logger import log_msg

_pool: MySQLConnectionPool | None = None

def get_pool() -> MySQLConnectionPool:
    global _pool
    log_msg("get_pool")
    if _pool is None:
        try:
            _pool = MySQLConnectionPool(
                pool_name="bot_pool",
                pool_size=5,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                autocommit=True,
                charset="utf8mb4",
            )
        except Exception as e:
            _pool = None
            log_msg(f"Pool Error {e}")

    return _pool

def get_connection():
    try:
        conn = get_pool().get_connection()
    except Exception as e:
        log_msg(f"Connection Error {e}")
        conn = None
    return conn