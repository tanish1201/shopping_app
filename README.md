# Shopping App

A small interactive shopping backend using Python, SQLite, pandas, matplotlib,
and seaborn.

## Run

Install the analytics dependencies, then start the terminal app:

```powershell
python -m pip install -r requirements.txt
python test.py
```

You can also run it as a package with `python -m shopping_app`.

The app prompts you to log in or register, then offers product browsing,
per-user carts, checkout, order history, activity history, and purchase
frequency reports. SQLite stores accounts, inventory, carts, orders, and
activity in `shopping_app.db` in the current working directory.

## Browser frontend

Start the browser app from the project folder:

```powershell
python run_web.py
```

Then open `http://127.0.0.1:8000`. The browser frontend supports account
registration and login, product browsing and filtering, saved carts, checkout,
order history, activity history, and sales insights by unit price and product
category. The standard-library HTTP server uses the same SQLite backend and
serves the frontend locally. Stop it with `Ctrl+C`.

To use a separate database, pass its path:

```powershell
python run_web.py --database shopping_web_demo.db --port 8001
```

## Modules

- `shopping_app/config.py` — manually defined product catalogue and shipping
  rates.
- `shopping_app/storage.py` — SQLite schema, seed products, and connections.
- `shopping_app/backend.py` — accounts, catalogue, carts, checkout, and
  activity tracking.
- `shopping_app/analytics.py` — pandas sales summaries and charts.
- `shopping_app/cli.py` — interactive terminal user interface.
- `shopping_app/web.py` — local HTTP server and JSON API.
- `shopping_app/web/` — browser interface (HTML, CSS, and JavaScript).
- `test.py` and `checking.py` — compatibility launchers.
- `run_web.py` — browser app launcher.

Passwords are stored as salted PBKDF2 hashes, not as plain text.
