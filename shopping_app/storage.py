"""SQLite schema and connection management for the shopping app."""

from contextlib import contextmanager
import sqlite3

from .config import PRODUCTS_DB


class Database:
    def __init__(self, database_path):
        self.database_path = database_path
        self.initialize()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price REAL NOT NULL,
                    stock_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS carts (
                    user_id INTEGER NOT NULL REFERENCES users(user_id)
                        ON DELETE CASCADE,
                    product_id INTEGER NOT NULL REFERENCES products(product_id),
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    PRIMARY KEY (user_id, product_id)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    region TEXT NOT NULL,
                    subtotal REAL NOT NULL,
                    shipping REAL NOT NULL,
                    total REAL NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS order_items (
                    order_item_id INTEGER PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES orders(order_id),
                    product_id INTEGER NOT NULL REFERENCES products(product_id),
                    product_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    unit_price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    line_total REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity (
                    activity_id INTEGER PRIMARY KEY,
                    user_id INTEGER REFERENCES users(user_id)
                        ON DELETE SET NULL,
                    username TEXT,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO products
                    (product_id, product_name, category, price, stock_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["product_id"],
                        item["product_name"],
                        item["category"],
                        item["price"],
                        item["stock_count"],
                    )
                    for item in PRODUCTS_DB.values()
                ],
            )
