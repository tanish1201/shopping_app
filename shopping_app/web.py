"""Local HTTP interface for the shopping app browser frontend."""

import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from threading import RLock
from urllib.parse import parse_qs, unquote, urlsplit

from .backend import ShoppingBackend

FRONTEND_DIRECTORY = Path(__file__).with_name("web")
MAX_REQUEST_SIZE = 64 * 1024


class ShoppingHTTPServer(ThreadingHTTPServer):
    def __init__(self, address, database_path):
        super().__init__(address, ShoppingRequestHandler)
        self.database_path = database_path
        self.sessions = {}
        self.sessions_lock = RLock()


class ShoppingRequestHandler(BaseHTTPRequestHandler):
    server: ShoppingHTTPServer

    def do_GET(self):
        parsed_path = urlsplit(self.path)
        path = parsed_path.path
        if path.startswith("/api/"):
            self._handle_api_get(path, parsed_path.query)
        else:
            self._serve_frontend(path)

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            body = self._read_json()
            if path == "/api/register":
                self._register(body)
            elif path == "/api/login":
                self._login(body)
            elif path == "/api/logout":
                self._logout()
            elif path == "/api/cart":
                store = self._require_store()
                store.add_to_cart(body.get("product_id"), body.get("quantity", 1))
                self._send_json(200, {"cart": store.get_cart()})
            elif path == "/api/checkout":
                store = self._require_store()
                order = store.checkout(body.get("region", ""))
                self._send_json(201, {"order": order})
            else:
                self._send_json(404, {"error": "API route not found"})
        except PermissionError as error:
            self._send_json(401, {"error": str(error)})
        except (ValueError, KeyError, RuntimeError) as error:
            self._send_json(400, {"error": str(error)})

    def do_DELETE(self):
        path = urlsplit(self.path).path
        prefix = "/api/cart/"
        if not path.startswith(prefix):
            self._send_json(404, {"error": "API route not found"})
            return
        try:
            product_id = int(unquote(path[len(prefix):]))
            store = self._require_store()
            store.remove_from_cart(product_id)
            self._send_json(200, {"cart": store.get_cart()})
        except PermissionError as error:
            self._send_json(401, {"error": str(error)})
        except (ValueError, KeyError, RuntimeError) as error:
            self._send_json(400, {"error": str(error)})

    def _handle_api_get(self, path, query=""):
        try:
            if path == "/api/products":
                store = self._require_store()
                parameters = parse_qs(query)
                category = parameters.get("category", [None])[0]
                self._send_json(
                    200, {"products": store.list_products(category=category)}
                )
            elif path == "/api/me":
                store = self._require_store()
                self._send_json(200, {"username": self._username(store)})
            elif path == "/api/cart":
                self._send_json(200, {"cart": self._require_store().get_cart()})
            elif path == "/api/orders":
                self._send_json(200, {"orders": self._require_store().get_order_history()})
            elif path == "/api/activity":
                self._send_json(
                    200, {"activity": self._require_store().get_activity()}
                )
            elif path == "/api/analytics/sales-by-price":
                store = self._require_store()
                rows = store.sales_by_price().to_dict(orient="records")
                self._send_json(200, {"sales": rows})
            elif path == "/api/analytics/sales-by-category":
                store = self._require_store()
                rows = store.sales_by_category().to_dict(orient="records")
                self._send_json(200, {"sales": rows})
            else:
                self._send_json(404, {"error": "API route not found"})
        except PermissionError as error:
            self._send_json(401, {"error": str(error)})
        except (ValueError, KeyError, RuntimeError) as error:
            self._send_json(400, {"error": str(error)})

    def _register(self, body):
        store = ShoppingBackend(self.server.database_path)
        username = body.get("username")
        password = body.get("password")
        store.register(username, password)
        store.login(username, password)
        self._start_session(store, status=201)

    def _login(self, body):
        store = ShoppingBackend(self.server.database_path)
        store.login(body.get("username"), body.get("password"))
        self._start_session(store)

    def _logout(self):
        token = self._session_token()
        if token is not None:
            with self.server.sessions_lock:
                store = self.server.sessions.pop(token, None)
            if store is not None:
                store.logout()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Set-Cookie",
            "shopping_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
        )
        self.send_header("Content-Length", str(len(b'{"ok":true}')))
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def _start_session(self, store, status=200):
        token = secrets.token_urlsafe(32)
        with self.server.sessions_lock:
            self.server.sessions[token] = store
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Set-Cookie",
            f"shopping_session={token}; Path=/; HttpOnly; SameSite=Lax",
        )
        body = json.dumps({"username": self._username(store)}).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _session_token(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get("shopping_session")
        return morsel.value if morsel is not None else None

    def _require_store(self):
        token = self._session_token()
        if token is None:
            raise PermissionError("Please log in")
        with self.server.sessions_lock:
            store = self.server.sessions.get(token)
        if store is None:
            raise PermissionError("Your session has expired. Please log in again.")
        return store

    @staticmethod
    def _username(store):
        with store._connection() as connection:
            row = connection.execute(
                "SELECT username FROM users WHERE user_id = ?",
                (store.active_user_id,),
            ).fetchone()
        return row["username"]

    def _read_json(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request length") from error
        if content_length < 0 or content_length > MAX_REQUEST_SIZE:
            raise ValueError("Request body is too large")
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("Request body must be valid JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_frontend(self, path):
        relative_path = "index.html" if path in {"/", ""} else path.lstrip("/")
        if relative_path not in {"index.html", "app.js", "style.css"}:
            self.send_error(404)
            return
        file_path = FRONTEND_DIRECTORY / relative_path
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
        }[file_path.suffix]
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Run the shopping app web frontend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", default="shopping_app.db")
    args = parser.parse_args()

    server = ShoppingHTTPServer((args.host, args.port), args.database)
    print(f"Shopping app running at http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping shopping app.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
