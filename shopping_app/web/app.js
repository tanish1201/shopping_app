const authView = document.querySelector("#auth-view");
const shopView = document.querySelector("#shop-view");
const authForm = document.querySelector("#auth-form");
const authTitle = document.querySelector("#auth-title");
const authDescription = document.querySelector("#auth-description");
const authSubmit = document.querySelector("#auth-submit");
const authError = document.querySelector("#auth-error");
const authSwitchCopy = document.querySelector("#auth-switch-copy");
const authModeButton = document.querySelector("#auth-mode-button");
const accountBar = document.querySelector("#account-bar");
const accountName = document.querySelector("#account-name");
const productGrid = document.querySelector("#product-grid");
const categoryFilter = document.querySelector("#category-filter");
const cartCount = document.querySelector("#cart-count");
const toast = document.querySelector("#toast");

let authMode = "login";
let products = [];
let knownCategories = [];
let catalogueRequestId = 0;
let toastTimer;

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Something went wrong. Please try again.");
  }
  return payload;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("visible"), 2800);
}

function setAuthenticated(username) {
  accountName.textContent = username;
  accountBar.hidden = false;
  authView.hidden = true;
  shopView.hidden = false;
  loadProducts();
  loadCartCount();
}

function setSignedOut() {
  accountBar.hidden = true;
  shopView.hidden = true;
  authView.hidden = false;
  document.querySelector("#password").value = "";
}

function setAuthMode(mode) {
  authMode = mode;
  const registering = mode === "register";
  authTitle.textContent = registering ? "Make yourself at home" : "Welcome back";
  authDescription.textContent = registering
    ? "Create an account to save your basket and orders."
    : "Sign in to pick up where you left off.";
  authSubmit.textContent = registering ? "Create account →" : "Sign in →";
  authSwitchCopy.textContent = registering ? "Already have an account?" : "New around here?";
  authModeButton.textContent = registering ? "Sign in instead" : "Create an account";
  document.querySelector("#password").autocomplete = registering
    ? "new-password"
    : "current-password";
  authError.hidden = true;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

function formatMoney(value) {
  return `$${Number(value).toFixed(2)}`;
}

async function loadProducts(category = "") {
  const requestId = ++catalogueRequestId;
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  try {
    const result = await request(`/api/products${query}`);
    if (requestId !== catalogueRequestId) {
      return;
    }
    products = result.products;
    renderProducts(products);
    if (!category || !knownCategories.length) {
      knownCategories = [...new Set(products.map((item) => item.category))].sort();
      updateCategoryOptions(knownCategories);
    }
    document.querySelector("#catalogue-message").textContent = "";
  } catch (error) {
    if (requestId === catalogueRequestId) {
      document.querySelector("#catalogue-message").textContent = error.message;
    }
  }
}

function updateCategoryOptions(categories) {
  const currentValue = categoryFilter.value;
  const allOption = categoryFilter.options[0];
  categoryFilter.replaceChildren(allOption);
  for (const category of categories) {
    const option = element("option", "", category);
    option.value = category;
    categoryFilter.append(option);
  }
  categoryFilter.value = categories.includes(currentValue) ? currentValue : "";
}

function renderProducts(items) {
  productGrid.replaceChildren();
  if (!items.length) {
    productGrid.append(element("p", "empty-state", "No products in this category."));
    return;
  }
  for (const product of items) {
    const card = element("article", "product-card");
    const art = element("div", `product-art tone-${product.product_id}`);
    art.setAttribute("aria-hidden", "true");
    const icon = element("span", "", productIcon(product.product_id));
    art.append(icon);

    const info = element("div", "product-info");
    info.append(element("p", "product-category", product.category));
    info.append(element("h3", "product-name", product.product_name));
    const bottom = element("div", "product-bottom");
    bottom.append(element("span", "product-price", formatMoney(product.price)));
    const addButton = element("button", "add-button", "+");
    addButton.type = "button";
    addButton.setAttribute("aria-label", `Add ${product.product_name} to bag`);
    addButton.disabled = product.stock_count < 1;
    addButton.addEventListener("click", () => addProduct(product.product_id));
    bottom.append(addButton);
    info.append(bottom);
    const stockText = product.stock_count
      ? `${product.stock_count} available`
      : "Out of stock";
    const stockClass = product.stock_count ? "stock-label" : "stock-label out";
    info.append(element("p", stockClass, stockText));
    card.append(art, info);
    productGrid.append(card);
  }
}

function productIcon(productId) {
  const icons = {
    1: "♫",
    2: "◈",
    3: "◉",
    4: "⌁",
  };
  return icons[productId] || "✳";
}

async function addProduct(productId) {
  try {
    await request("/api/cart", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, quantity: 1 }),
    });
    await loadCartCount();
    showToast("Added to your bag.");
  } catch (error) {
    showToast(error.message);
  }
}

async function loadCartCount() {
  try {
    const result = await request("/api/cart");
    cartCount.textContent = result.cart.reduce((sum, item) => sum + item.quantity, 0);
  } catch (error) {
    showToast(error.message);
  }
}

async function loadCart() {
  const container = document.querySelector("#cart-content");
  container.replaceChildren();
  try {
    const { cart } = await request("/api/cart");
    cartCount.textContent = cart.reduce((sum, item) => sum + item.quantity, 0);
    if (!cart.length) {
      container.replaceChildren(
        element("p", "empty-state", "Your bag is empty. Find something lovely in the shop."),
      );
      return;
    }

    const layout = element("div", "cart-layout");
    const list = element("div", "cart-list");
    for (const item of cart) {
      const row = element("div", "cart-row");
      const description = element("div");
      description.append(element("p", "cart-product-name", item.product_name));
      description.append(
        element(
          "span",
          "cart-product-meta",
          `${item.quantity} × ${formatMoney(item.price)}`,
        ),
      );
      row.append(description);
      row.append(element("span", "cart-line-total", formatMoney(item.line_total)));
      const removeButton = element("button", "remove-button", "Remove");
      removeButton.type = "button";
      removeButton.addEventListener("click", () => removeProduct(item.product_id));
      row.append(removeButton);
      list.append(row);
    }

    const subtotal = cart.reduce((sum, item) => sum + item.line_total, 0);
    const summary = element("form", "summary-card");
    summary.id = "checkout-form";
    summary.append(element("h3", "", "Order summary"));
    summary.append(summaryLine("Subtotal", formatMoney(subtotal)));

    const shippingLabel = element("label", "muted", "Shipping");
    shippingLabel.htmlFor = "checkout-region";
    summary.append(shippingLabel);
    const region = element("select", "checkout-region");
    region.id = "checkout-region";
    region.name = "region";
    for (const [name, price] of [
      ["local", 5],
      ["national", 10],
      ["international", 25],
    ]) {
      const option = element("option", "", `${name[0].toUpperCase()}${name.slice(1)} — ${formatMoney(price)}`);
      option.value = name;
      region.append(option);
    }
    summary.append(region);
    const shippingLine = summaryLine("Shipping", formatMoney(5));
    const totalLine = summaryLine("Estimated total", formatMoney(subtotal + 5), true);
    region.addEventListener("change", () => {
      const shippingPrices = { local: 5, national: 10, international: 25 };
      const shipping = shippingPrices[region.value];
      shippingLine.lastElementChild.textContent = formatMoney(shipping);
      totalLine.lastElementChild.textContent = formatMoney(subtotal + shipping);
    });
    summary.append(shippingLine, totalLine);
    const checkoutButton = element("button", "button button-dark", "Place order →");
    checkoutButton.type = "submit";
    summary.append(checkoutButton);
    summary.addEventListener("submit", checkout);
    layout.append(list, summary);
    container.replaceChildren(layout);
  } catch (error) {
    container.replaceChildren(element("p", "empty-state", error.message));
  }
}

function summaryLine(label, value, isTotal = false) {
  const line = element("div", isTotal ? "summary-line summary-total" : "summary-line");
  line.append(element("span", "", label), element("span", "", value));
  return line;
}

async function removeProduct(productId) {
  try {
    await request(`/api/cart/${productId}`, { method: "DELETE" });
    await loadCart();
    showToast("Removed from your bag.");
  } catch (error) {
    showToast(error.message);
  }
}

async function checkout(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const region = event.currentTarget.elements.region.value;
    const result = await request("/api/checkout", {
      method: "POST",
      body: JSON.stringify({ region }),
    });
    showToast(`Order placed. Total: ${formatMoney(result.order.total)}`);
    await loadCartCount();
    await showPanel("orders-panel");
  } catch (error) {
    showToast(error.message);
    button.disabled = false;
  }
}

async function loadOrders() {
  const container = document.querySelector("#orders-content");
  container.replaceChildren();
  try {
    const { orders } = await request("/api/orders");
    if (!orders.length) {
      container.replaceChildren(
        element("p", "empty-state", "Your completed orders will show up here."),
      );
      return;
    }
    const list = element("div", "order-list");
    for (const order of orders) {
      const card = element("article", "order-card");
      const top = element("div", "order-top");
      const details = element("div");
      details.append(element("p", "order-number", `Order #${order.order_id}`));
      const date = new Date(order.created_at).toLocaleString();
      details.append(element("p", "order-date", `${date} · ${order.region} delivery`));
      top.append(details, element("span", "order-total", formatMoney(order.total)));
      card.append(top);
      const itemDescriptions = order.items.map(
        (item) => `${item.product_name} × ${item.quantity} (${formatMoney(item.line_total)})`,
      );
      card.append(element("p", "order-items", itemDescriptions.join(" · ")));
      list.append(card);
    }
    container.replaceChildren(list);
  } catch (error) {
    container.replaceChildren(element("p", "empty-state", error.message));
  }
}

async function loadInsights() {
  const container = document.querySelector("#insights-content");
  container.replaceChildren();
  try {
    const [priceResult, categoryResult] = await Promise.all([
      request("/api/analytics/sales-by-price"),
      request("/api/analytics/sales-by-category"),
    ]);
    const priceSales = priceResult.sales;
    const categorySales = categoryResult.sales;
    if (!priceSales.length && !categorySales.length) {
      container.replaceChildren(
        element("p", "empty-state", "Purchase insights will appear after the first order."),
      );
      return;
    }
    const reports = document.createDocumentFragment();
    if (priceSales.length) {
      const report = createReport("Orders by product price", "All completed orders");
      const maxOrders = Math.max(...priceSales.map((row) => row.order_count));
      for (const row of priceSales) {
        report.append(
          reportRow(
            formatMoney(row.unit_price),
            row.order_count,
            maxOrders,
            `${row.order_count} ${row.order_count === 1 ? "order" : "orders"}`,
            formatMoney(row.revenue),
          ),
        );
      }
      reports.append(report);
    }
    if (categorySales.length) {
      const report = createReport("Sales by category", "Purchased items and revenue");
      const maxRevenue = Math.max(...categorySales.map((row) => row.revenue));
      for (const row of categorySales) {
        report.append(
          reportRow(
            row.category,
            row.revenue,
            maxRevenue,
            `${row.quantity} ${row.quantity === 1 ? "item" : "items"}`,
            formatMoney(row.revenue),
          ),
        );
      }
      reports.append(report);
    }
    container.replaceChildren(reports);
  } catch (error) {
    container.replaceChildren(element("p", "empty-state", error.message));
  }
}

function createReport(title, caption) {
  const report = element("section", "report-card");
  report.classList.add("report-section");
  const heading = element("div", "report-heading");
  heading.append(element("h3", "", title), element("span", "", caption));
  report.append(heading);
  return report;
}

function reportRow(label, amount, maxAmount, metric, revenue) {
  const line = element("div", "report-row");
  line.append(element("span", "report-price", label));
  const track = element("div", "bar-track");
  const bar = element("div", "bar-fill");
  bar.style.width = `${Math.max(4, (amount / maxAmount) * 100)}%`;
  track.append(bar);
  line.append(track);
  line.append(element("span", "report-orders", metric));
  line.append(element("span", "report-revenue", revenue));
  return line;
}

async function loadActivity() {
  const container = document.querySelector("#activity-content");
  container.replaceChildren();
  try {
    const { activity } = await request("/api/activity");
    if (!activity.length) {
      container.replaceChildren(
        element("p", "empty-state", "Your account activity will appear here."),
      );
      return;
    }
    const list = element("div", "activity-list");
    for (const item of activity.reverse()) {
      const row = element("div", "activity-row");
      row.append(
        element("span", "activity-date", new Date(item.created_at).toLocaleString()),
        element("span", "activity-action", item.action.replaceAll("_", " ")),
        element("span", "activity-details", item.details),
      );
      list.append(row);
    }
    container.replaceChildren(list);
  } catch (error) {
    container.replaceChildren(element("p", "empty-state", error.message));
  }
}

async function showPanel(panelId) {
  for (const panel of document.querySelectorAll(".content-panel")) {
    panel.hidden = panel.id !== panelId;
  }
  for (const button of document.querySelectorAll(".nav-button")) {
    const isActive = button.dataset.panel === panelId;
    button.classList.toggle("active", isActive);
    if (isActive) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  }
  if (panelId === "products-panel") {
    await loadProducts(categoryFilter.value);
  } else if (panelId === "cart-panel") {
    await loadCart();
  } else if (panelId === "orders-panel") {
    await loadOrders();
  } else if (panelId === "insights-panel") {
    await loadInsights();
  } else if (panelId === "activity-panel") {
    await loadActivity();
  }
}

authModeButton.addEventListener("click", () => {
  setAuthMode(authMode === "login" ? "register" : "login");
});

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authError.hidden = true;
  authSubmit.disabled = true;
  const formData = new FormData(authForm);
  const payload = {
    username: formData.get("username"),
    password: formData.get("password"),
  };
  try {
    const result = await request(`/api/${authMode}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    authForm.reset();
    setAuthenticated(result.username);
  } catch (error) {
    authError.textContent = error.message;
    authError.hidden = false;
  } finally {
    authSubmit.disabled = false;
  }
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  try {
    await request("/api/logout", { method: "POST", body: "{}" });
  } finally {
    setSignedOut();
    setAuthMode("login");
  }
});

for (const button of document.querySelectorAll(".nav-button")) {
  button.addEventListener("click", () => showPanel(button.dataset.panel));
}

categoryFilter.addEventListener("change", () => loadProducts(categoryFilter.value));

request("/api/me")
  .then((result) => setAuthenticated(result.username))
  .catch(() => setSignedOut());
