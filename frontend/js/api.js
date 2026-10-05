/**
 * Backend API Client for Universal AI Shopping Agent
 */
const API_BASE = "";

const ShoppingAPI = {
  async searchProducts(query, budgetMax = null, minRating = null, sortBy = "relevance") {
    const params = new URLSearchParams({ query, sort_by: sortBy });
    if (budgetMax) params.append("budget_max", budgetMax);
    if (minRating) params.append("min_rating", minRating);

    const res = await fetch(`${API_BASE}/api/products/search?${params.toString()}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Search request failed" }));
      throw new Error(err.detail || "Search request failed");
    }
    return await res.json();
  },

  async comparePlatforms(query) {
    const params = new URLSearchParams({ query });
    const res = await fetch(`${API_BASE}/api/products/compare-platforms?${params.toString()}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Platform comparison failed" }));
      throw new Error(err.detail || "Platform comparison failed");
    }
    return await res.json();
  },

  async getProductDetails(productId) {
    const res = await fetch(`${API_BASE}/api/products/${productId}`);
    if (!res.ok) throw new Error("Failed to load product details");
    return await res.json();
  },

  async compareProducts(productIds) {
    const res = await fetch(`${API_BASE}/api/comparison`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_ids: productIds }),
    });
    if (!res.ok) throw new Error("Comparison failed");
    return await res.json();
  },

  async analyzeReviews(productName, productId = null) {
    const res = await fetch(`${API_BASE}/api/reviews/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_name: productName, product_id: productId }),
    });
    if (!res.ok) throw new Error("Review analysis failed");
    return await res.json();
  },

  async addToCart(productName, platform, productUrl, productId = null, offerId = null) {
    const res = await fetch(`${API_BASE}/api/cart/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_name: productName,
        platform: platform,
        product_url: productUrl,
        product_id: productId,
        offer_id: offerId,
        user_id: 1,
      }),
    });
    if (!res.ok) throw new Error("Cart addition request failed");
    return await res.json();
  },

  async approveCheckout(productName, platform, productUrl, totalAmount = null, productId = null) {
    const res = await fetch(`${API_BASE}/api/cart/checkout/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_name: productName,
        platform: platform,
        product_url: productUrl,
        total_amount: totalAmount,
        product_id: productId,
        user_id: 1,
      }),
    });
    if (!res.ok) throw new Error("Checkout handoff failed");
    return await res.json();
  },

  async getHistory() {
    const res = await fetch(`${API_BASE}/api/history?user_id=1`);
    if (!res.ok) return { searches: [] };
    return await res.json();
  },
};

window.ShoppingAPI = ShoppingAPI;
