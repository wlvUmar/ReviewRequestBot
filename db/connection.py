import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from config import Config

_pool: MySQLConnectionPool | None = None

def get_pool() -> MySQLConnectionPool:
    global _pool
    if _pool is None:
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
    return _pool

def get_connection():
    return get_pool().get_connection()