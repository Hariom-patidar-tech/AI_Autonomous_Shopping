const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const context = { Intl };
context.window = context;
const elements = new Map();
context.document = {
  addEventListener() {},
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, { innerHTML: "", textContent: "", value: "", addEventListener() {} });
    return elements.get(id);
  },
};
vm.createContext(context);
vm.runInContext(
  fs.readFileSync(path.join(__dirname, "..", "js", "components.js"), "utf8"),
  context,
);
vm.runInContext(
  fs.readFileSync(path.join(__dirname, "..", "js", "app.js"), "utf8"),
  context,
);

const product = {
  product_name: "Sony WF-C700N Earbuds",
  brand: "Sony",
  model: "WF-C700N",
  price: 99,
  currency: "USD",
  source: "Amazon",
  url: "https://www.amazon.com/dp/B0ABCDE123",
  image_url: "https://m.media-amazon.com/images/sony.jpg",
  availability: true,
  observed_at: "2026-10-05T12:00:00Z",
  last_verified_at: "2026-10-05T12:00:00Z",
  offers: [
    {
      platform: "Amazon",
      price: 99,
      currency: "USD",
      url: "https://www.amazon.com/dp/B0ABCDE123",
      image_url: "https://m.media-amazon.com/images/sony.jpg",
    },
    {
      platform: "Flipkart",
      price: 7000,
      currency: "INR",
      url: "https://www.flipkart.com/p/sony-wf-c700n",
      image_url: "https://rukminim2.flixcart.com/image/sony.jpg",
    },
  ],
};

test("Buy Now uses the exact URL belonging to each retailer offer", () => {
  const html = context.Components.renderProductCard(product);

  assert.match(html, /href="https:\/\/www\.amazon\.com\/dp\/B0ABCDE123"[^>]*class="btn-sm btn-buy"/);
  assert.match(html, /href="https:\/\/www\.flipkart\.com\/p\/sony-wf-c700n"[^>]*class="btn-sm btn-buy"/);
  assert.ok(html.includes('src="https://rukminim2.flixcart.com/image/sony.jpg"'));
});

test("the best-deal marker does not compare prices across currencies", () => {
  const html = context.Components.renderProductCard(product);

  assert.equal((html.match(/BEST DEAL/g) || []).length, 1);
  assert.ok(html.includes("Lowest comparable price (USD)"));
});

test("a valid backend product response reaches the rendered product card", () => {
  const apiProduct = {
    ...product,
    product_name: "Sony WF-C700N True Wireless Earbuds",
    source: "Amazon",
    url: "https://www.amazon.com/dp/B0ABCDE123",
    image_url: "https://m.media-amazon.com/images/sony.jpg",
  };
  const response = {
    search_status: "success",
    verified_results: 1,
    products: [apiProduct],
    alternatives: [],
    comparison_summary: null,
    platform_comparison: null,
  };

  const count = context.App.consumeSearchResponse(response);
  context.App.applyClientFiltersAndSort();

  assert.equal(count, 1);
  assert.ok(elements.get("products-grid").innerHTML.includes(apiProduct.product_name));
  assert.ok(elements.get("products-grid").innerHTML.includes(`src="${apiProduct.image_url}"`));
  assert.ok(elements.get("products-grid").innerHTML.includes(`href="${apiProduct.offers[0].url}"`));
});

test("the exact backend verification reason is shown when no offers remain", () => {
  const reason = "Retailer page was missing a current price and product thumbnail.";

  context.App.renderEmpty(reason, {
    title: "No verified offers found",
    countLabel: "0 verified offers",
  });

  assert.equal(elements.get("results-count-label").textContent, "0 verified offers");
  assert.ok(elements.get("products-grid").innerHTML.includes(reason));
});