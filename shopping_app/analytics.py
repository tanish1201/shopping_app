"""Sales summaries and charts."""


def get_sales_data(store):
    """Read completed purchases into a pandas DataFrame."""
    import pandas as pd

    with store._connection() as connection:
        rows = connection.execute(
            """
            SELECT o.user_id, u.username, o.order_id, o.created_at,
                   i.product_name, i.category, i.unit_price,
                   i.quantity, i.line_total
            FROM order_items AS i
            JOIN orders AS o ON o.order_id = i.order_id
            JOIN users AS u ON u.user_id = o.user_id
            ORDER BY o.created_at
            """
        ).fetchall()
    columns = [
        "user_id",
        "username",
        "order_id",
        "created_at",
        "product_name",
        "category",
        "unit_price",
        "quantity",
        "line_total",
    ]
    return pd.DataFrame([dict(row) for row in rows], columns=columns)


def sales_by_category(store):
    """Summarize purchased quantity and revenue per category."""
    return get_sales_data(store).groupby("category", as_index=False).agg(
        quantity=("quantity", "sum"),
        revenue=("line_total", "sum"),
    )


def sales_by_customer_and_category(store):
    """Summarize each customer's purchases by category."""
    return get_sales_data(store).groupby(
        ["username", "category"], as_index=False
    ).agg(quantity=("quantity", "sum"), revenue=("line_total", "sum"))


def sales_by_price(store):
    """Summarize order frequency, quantity, and revenue by unit price."""
    sales = get_sales_data(store)
    return sales.groupby("unit_price", as_index=False).agg(
        order_count=("order_id", "nunique"),
        purchased_quantity=("quantity", "sum"),
        revenue=("line_total", "sum"),
    ).sort_values("unit_price")


def plot_purchase_frequency_by_price(store, show=True):
    """Plot how often items at each unit price have been purchased."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    summary = sales_by_price(store)
    if summary.empty:
        raise ValueError("There are no completed sales to plot yet")

    figure, axis = plt.subplots(figsize=(8, 5))
    sns.barplot(
        data=summary,
        x="unit_price",
        y="order_count",
        color="steelblue",
        ax=axis,
    )
    axis.set_title("Purchase frequency by product price")
    axis.set_xlabel("Unit price")
    axis.set_ylabel("Number of orders containing products at this price")
    figure.tight_layout()
    if show:
        plt.show()
    return figure, axis


def plot_sales_trends(store, show=True):
    """Plot category revenue, customer preferences, and daily sales."""
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns

    sales = get_sales_data(store)
    if sales.empty:
        raise ValueError("There are no completed sales to plot yet")

    category_sales = sales_by_category(store)
    customer_category = sales.pivot_table(
        index="username",
        columns="category",
        values="line_total",
        aggfunc="sum",
        fill_value=0,
    )
    sales["date"] = pd.to_datetime(sales["created_at"], utc=True).dt.date
    daily_sales = sales.groupby("date", as_index=False)["line_total"].sum()
    daily_sales = daily_sales.rename(columns={"line_total": "revenue"})

    figure, axes = plt.subplots(1, 3, figsize=(18, 5))
    sns.barplot(data=category_sales, x="category", y="revenue", ax=axes[0])
    axes[0].set_title("Sales by product category")
    axes[0].set_ylabel("Revenue")
    axes[0].tick_params(axis="x", rotation=25)

    sns.heatmap(
        customer_category, annot=True, fmt=".2f", cmap="Blues", ax=axes[1]
    )
    axes[1].set_title("Customer purchases by category")
    axes[1].set_xlabel("Category")
    axes[1].set_ylabel("Customer")

    sns.lineplot(
        data=daily_sales, x="date", y="revenue", marker="o", ax=axes[2]
    )
    axes[2].set_title("Daily sales revenue")
    axes[2].set_ylabel("Revenue")
    axes[2].tick_params(axis="x", rotation=25)

    figure.tight_layout()
    if show:
        plt.show()
    return figure, axes
