"""Interactive terminal interface for the shopping app."""

from .backend import ShoppingBackend


def _read_integer(prompt, minimum=None):
    """Prompt until the user enters an integer within the optional lower bound."""
    while True:
        value = input(prompt).strip()
        try:
            number = int(value)
        except ValueError:
            print("Enter a whole number.")
            continue
        if minimum is not None and number < minimum:
            print(f"Enter a number greater than or equal to {minimum}.")
            continue
        return number


def _authenticate(store):
    """Prompt for login or registration until authentication succeeds."""
    while store.active_user_id is None:
        print("\nWelcome to the shopping app")
        print("1. Log in")
        print("2. Register")
        print("0. Exit")
        choice = input("Choose an option: ").strip()
        if choice == "0":
            return False
        if choice not in {"1", "2"}:
            print("Choose 1, 2, or 0.")
            continue

        username = input("Username: ").strip()
        password = input("Password: ")
        try:
            if choice == "2":
                store.register(username, password)
                print("Account created.")
            print(f"Welcome, {store.login(username, password)}!")
        except ValueError as error:
            print(error)
    return True


def _show_products_and_add(store):
    products = store.list_products()
    print("\nProduct catalogue")
    for product in products:
        print(
            f"{product['product_id']}. {product['product_name']} "
            f"| {product['category']} | ${product['price']:.2f} "
            f"| Stock: {product['stock_count']}"
        )
    print("Enter a product ID to add it to your cart, or 0 to return.")
    product_id = _read_integer("Product ID: ", minimum=0)
    if product_id == 0:
        return
    quantity = _read_integer("Quantity: ", minimum=1)
    try:
        store.add_to_cart(product_id, quantity)
    except (KeyError, ValueError) as error:
        print(error)
    else:
        print("Added to cart.")


def _show_cart(store):
    cart = store.get_cart()
    if not cart:
        print("\nYour cart is empty.")
        return
    print("\nYour cart")
    for item in cart:
        print(
            f"{item['product_name']} x {item['quantity']} "
            f"@ ${item['price']:.2f} = ${item['line_total']:.2f}"
        )
    print(f"Subtotal: ${sum(item['line_total'] for item in cart):.2f}")


def _remove_cart_item(store):
    if not store.get_cart():
        print("\nYour cart is empty.")
        return
    _show_cart(store)
    product_id = _read_integer("Product ID to remove (0 to cancel): ", minimum=0)
    if product_id == 0:
        return
    quantity_text = input("Quantity to remove, or Enter to remove all: ").strip()
    try:
        quantity = int(quantity_text) if quantity_text else None
        store.remove_from_cart(product_id, quantity)
    except (KeyError, ValueError) as error:
        print(error)
    else:
        print("Cart updated.")


def _checkout(store):
    print("\nShipping regions")
    for region, price in store.shipping_rates.items():
        print(f"- {region}: ${price:.2f}")
    region = input("Shipping region: ").strip().casefold()
    try:
        order = store.checkout(region)
    except ValueError as error:
        print(error)
        return
    print(f"Order #{order['order_id']} placed.")
    print(f"Subtotal: ${order['subtotal']:.2f}")
    print(f"Shipping: ${order['shipping']:.2f}")
    print(f"Total: ${order['total']:.2f}")


def _show_purchase_frequency(store):
    purchases = store.sales_by_price()
    if purchases.empty:
        print("\nNo completed purchases yet.")
        return
    print("\nPurchase frequency by unit price")
    purchases = purchases.rename(
        columns={
            "unit_price": "Unit price",
            "order_count": "Orders",
            "purchased_quantity": "Items purchased",
            "revenue": "Revenue",
        }
    )
    print(
        purchases.to_string(
            index=False,
            formatters={
                "Unit price": "${:.2f}".format,
                "Revenue": "${:.2f}".format,
            },
        )
    )
    if input("Show purchase-frequency chart? (y/n): ").strip().casefold() == "y":
        try:
            store.plot_purchase_frequency_by_price()
        except ImportError as error:
            print(f"Chart dependencies are missing: {error}")


def run_interactive_app(database_path="shopping_app.db"):
    """Run the shopping app's interactive terminal interface."""
    store = ShoppingBackend(database_path)
    try:
        if not _authenticate(store):
            return

        while store.active_user_id is not None:
            print("\nShopping menu")
            print("1. Browse products / add to cart")
            print("2. View cart")
            print("3. Remove from cart")
            print("4. Checkout")
            print("5. Purchase frequency by price")
            print("6. Order history")
            print("7. Account activity")
            print("0. Log out and exit")
            choice = input("Choose an option: ").strip()

            if choice == "1":
                _show_products_and_add(store)
            elif choice == "2":
                _show_cart(store)
            elif choice == "3":
                _remove_cart_item(store)
            elif choice == "4":
                _checkout(store)
            elif choice == "5":
                _show_purchase_frequency(store)
            elif choice == "6":
                print(store.get_order_history())
            elif choice == "7":
                for event in store.get_activity():
                    print(
                        f"{event['created_at']} | {event['action']}: "
                        f"{event['details']}"
                    )
            elif choice == "0":
                store.logout()
                print("Logged out. Goodbye!")
            else:
                print("Choose one of the listed options.")
    except (EOFError, KeyboardInterrupt):
        if store.active_user_id is not None:
            store.logout()
        print("\nGoodbye!")
