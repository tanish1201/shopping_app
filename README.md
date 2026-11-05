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

## Modules

- `shopping_app/config.py` — manually defined product catalogue and shipping
  rates.
- `shopping_app/storage.py` — SQLite schema, seed products, and connections.
- `shopping_app/backend.py` — accounts, catalogue, carts, checkout, and
  activity tracking.
- `shopping_app/analytics.py` — pandas sales summaries and charts.
- `shopping_app/cli.py` — interactive terminal user interface.
- `test.py` and `checking.py` — compatibility launchers.

Passwords are stored as salted PBKDF2 hashes, not as plain text.
