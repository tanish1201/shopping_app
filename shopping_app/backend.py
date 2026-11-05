"""Accounts, catalogue, carts, orders, and activity tracking."""

from datetime import datetime, timezone
import hashlib
import hmac
import secrets
import sqlite3

from .config import PASSWORD_HASH_ITERATIONS, SHIPPING_DB
from .storage import Database


class ShoppingBackend:
    """Provide persistent shopping features backed by SQLite."""

    def __init__(self, database_path="shopping_app.db"):
        self.database_path = database_path
        self.database = Database(database_path)
        self.shipping_rates = SHIPPING_DB.copy()
        self.active_user_id = None

    def _connection(self):
        return self.database.connection()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _require_login(self):
        if self.active_user_id is None:
            raise RuntimeError("Please log in to use this feature")
        return self.active_user_id

    @staticmethod
    def _password_hash(password, salt):
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
        )

    def _log(self, action, details="", connection=None, username=None):
        user_id = self.active_user_id
        if username is None and user_id is not None:
            if connection is None:
                with self._connection() as lookup_connection:
                    row = lookup_connection.execute(
                        "SELECT username FROM users WHERE user_id = ?", (user_id,)
                    ).fetchone()
            else:
                row = connection.execute(
                    "SELECT username FROM users WHERE user_id = ?", (user_id,)
                ).fetchone()
            username = row["username"] if row is not None else None

        query = """
            INSERT INTO activity (user_id, username, action, details, created_at)
            VALUES (?, ?, ?, ?, ?)
        """
        values = (user_id, username, action, details, self._now())
        if connection is None:
            with self._connection() as log_connection:
                log_connection.execute(query, values)
        else:
            connection.execute(query, values)

    def register(self, username, password):
        """Create an account. Passwords are stored as salted hashes."""
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Username cannot be empty")
        if not isinstance(password, str) or not password:
            raise ValueError("Password cannot be empty")

        username = username.strip()
        salt = secrets.token_bytes(16)
        password_hash = self._password_hash(password, salt)
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (username, salt, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, salt, password_hash, self._now()),
                )
                user_id = cursor.lastrowid
                connection.execute(
                    """
                    INSERT INTO activity
                        (user_id, username, action, details, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, username, "register", "Account created", self._now()),
                )
        except sqlite3.IntegrityError as error:
            if "users.username" in str(error):
                raise ValueError("That username is already registered") from error
            raise
        return user_id

    def login(self, username, password):
        """Authenticate a user and make that user's saved cart available."""
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError("Enter a valid username and password")
        if self.active_user_id is not None:
            self.logout()

        with self._connection() as connection:
            user = connection.execute(
                """
                SELECT user_id, username, salt, password_hash
                FROM users WHERE username = ?
                """,
                (username.strip(),),
            ).fetchone()

        valid = user is not None and hmac.compare_digest(
            self._password_hash(password, user["salt"]), user["password_hash"]
        )
        if not valid:
            self._log("login_failed", "Invalid username or password", username=username)
            raise ValueError("Invalid username or password")

        self.active_user_id = user["user_id"]
        self._log("login", "Login successful")
        return user["username"]

    def logout(self):
        """Log out without deleting the user's saved cart or history."""
        self._require_login()
        self._log("logout", "Logged out")
        self.active_user_id = None

    def list_products(self, category=None):
        """Return all products or filter the catalogue by category."""
        with self._connection() as connection:
            if category is None:
                rows = connection.execute(
                    "SELECT * FROM products ORDER BY product_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM products
                    WHERE category = ? COLLATE NOCASE ORDER BY product_id
                    """,
                    (category,),
                ).fetchall()
        self._log(
            "list_products",
            f"category={category}" if category is not None else "all categories",
        )
        return [dict(row) for row in rows]

    def get_product(self, product_id):
        """Return one product by ID."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown product ID: {product_id}")
        self._log("view_product", f"product_id={product_id}")
        return dict(row)

    @staticmethod
    def _validate_quantity(quantity):
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Quantity must be a positive whole number")

    def add_to_cart(self, product_id, quantity=1):
        """Add an available product to the logged-in user's saved cart."""
        user_id = self._require_login()
        self._validate_quantity(quantity)
        with self._connection() as connection:
            product = connection.execute(
                "SELECT product_name, stock_count FROM products WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            if product is None:
                raise KeyError(f"Unknown product ID: {product_id}")
            row = connection.execute(
                "SELECT quantity FROM carts WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            ).fetchone()
            current_quantity = row["quantity"] if row is not None else 0
            new_quantity = current_quantity + quantity
            if new_quantity > product["stock_count"]:
                raise ValueError(f"Not enough stock for {product['product_name']}")
            connection.execute(
                """
                INSERT INTO carts (user_id, product_id, quantity) VALUES (?, ?, ?)
                ON CONFLICT(user_id, product_id)
                DO UPDATE SET quantity = excluded.quantity
                """,
                (user_id, product_id, new_quantity),
            )
            self._log(
                "add_to_cart",
                f"product_id={product_id}, quantity={quantity}",
                connection=connection,
            )

    def remove_from_cart(self, product_id, quantity=None):
        """Remove a quantity or the entire product line from the cart."""
        user_id = self._require_login()
        if quantity is not None:
            self._validate_quantity(quantity)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT quantity FROM carts WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"Product {product_id} is not in the cart")
            if quantity is None or quantity >= row["quantity"]:
                connection.execute(
                    "DELETE FROM carts WHERE user_id = ? AND product_id = ?",
                    (user_id, product_id),
                )
            else:
                connection.execute(
                    "UPDATE carts SET quantity = ? WHERE user_id = ? AND product_id = ?",
                    (row["quantity"] - quantity, user_id, product_id),
                )
            self._log(
                "remove_from_cart",
                f"product_id={product_id}, quantity={quantity or 'all'}",
                connection=connection,
            )

    def get_cart(self):
        """Return this user's saved cart and line totals."""
        user_id = self._require_login()
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT p.product_id, p.product_name, p.category, p.price,
                       p.stock_count, c.quantity, p.price * c.quantity AS line_total
                FROM carts AS c JOIN products AS p ON p.product_id = c.product_id
                WHERE c.user_id = ? ORDER BY p.product_id
                """,
                (user_id,),
            ).fetchall()
        self._log("view_cart", "Viewed saved cart")
        return [dict(row) for row in rows]

    def cart_subtotal(self):
        return sum(item["line_total"] for item in self.get_cart())

    def calculate_shipping(self, region):
        try:
            shipping = self.shipping_rates[region]
        except KeyError:
            raise ValueError(f"Unknown shipping region: {region}") from None
        self._log("calculate_shipping", f"region={region}")
        return shipping

    def checkout(self, region):
        """Save the order and update stock/cart in one database transaction."""
        user_id = self._require_login()
        shipping = self.calculate_shipping(region)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT p.product_id, p.product_name, p.category, p.price,
                       p.stock_count, c.quantity
                FROM carts AS c JOIN products AS p ON p.product_id = c.product_id
                WHERE c.user_id = ?
                """,
                (user_id,),
            ).fetchall()
            if not rows:
                raise ValueError("Cannot check out with an empty cart")

            items = []
            subtotal = 0.0
            for row in rows:
                if row["quantity"] > row["stock_count"]:
                    raise ValueError(f"Not enough stock for {row['product_name']}")
                item = dict(row)
                item["line_total"] = item["price"] * item["quantity"]
                subtotal += item["line_total"]
                items.append(item)

            total = subtotal + shipping
            created_at = self._now()
            cursor = connection.execute(
                """
                INSERT INTO orders (user_id, region, subtotal, shipping, total, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, region, subtotal, shipping, total, created_at),
            )
            order_id = cursor.lastrowid
            for item in items:
                updated = connection.execute(
                    """
                    UPDATE products SET stock_count = stock_count - ?
                    WHERE product_id = ? AND stock_count >= ?
                    """,
                    (item["quantity"], item["product_id"], item["quantity"]),
                )
                if updated.rowcount != 1:
                    raise ValueError(f"Not enough stock for {item['product_name']}")
                connection.execute(
                    """
                    INSERT INTO order_items
                        (order_id, product_id, product_name, category,
                         unit_price, quantity, line_total)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        item["product_id"],
                        item["product_name"],
                        item["category"],
                        item["price"],
                        item["quantity"],
                        item["line_total"],
                    ),
                )
            connection.execute("DELETE FROM carts WHERE user_id = ?", (user_id,))
            self._log(
                "checkout",
                f"order_id={order_id}, total={total:.2f}",
                connection=connection,
            )

        return {
            "order_id": order_id,
            "items": items,
            "subtotal": subtotal,
            "shipping": shipping,
            "total": total,
            "created_at": created_at,
        }

    def get_order_history(self):
        """Return this user's saved orders and their items."""
        user_id = self._require_login()
        with self._connection() as connection:
            orders = connection.execute(
                """
                SELECT order_id, region, subtotal, shipping, total, created_at
                FROM orders WHERE user_id = ? ORDER BY order_id DESC
                """,
                (user_id,),
            ).fetchall()
            result = []
            for order in orders:
                data = dict(order)
                data["items"] = [
                    dict(item)
                    for item in connection.execute(
                        """
                        SELECT product_name, category, unit_price, quantity, line_total
                        FROM order_items WHERE order_id = ?
                        """,
                        (order["order_id"],),
                    ).fetchall()
                ]
                result.append(data)
        self._log("view_order_history", "Viewed order history")
        return result

    def get_activity(self):
        """Return activity recorded for the currently logged-in user."""
        user_id = self._require_login()
        self._log("view_activity", "Viewed account activity")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT action, details, created_at FROM activity
                WHERE user_id = ? ORDER BY activity_id
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_sales_data(self):
        from .analytics import get_sales_data

        return get_sales_data(self)

    def sales_by_category(self):
        from .analytics import sales_by_category

        return sales_by_category(self)

    def sales_by_customer_and_category(self):
        from .analytics import sales_by_customer_and_category

        return sales_by_customer_and_category(self)

    def sales_by_price(self):
        from .analytics import sales_by_price

        return sales_by_price(self)

    def plot_purchase_frequency_by_price(self, show=True):
        from .analytics import plot_purchase_frequency_by_price

        return plot_purchase_frequency_by_price(self, show)

    def plot_sales_trends(self, show=True):
        from .analytics import plot_sales_trends

        return plot_sales_trends(self, show)
