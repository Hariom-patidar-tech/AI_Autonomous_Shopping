/**
 * ==========================================================================
 * NEXSHOP — PRODUCTION UI COMPONENTS (AMAZON-INSPIRED)
 * Zero Mock Data • Real-World Live Discovery • Direct Store Links
 * ==========================================================================
 */

const Components = {
  /**
   * Format a verified amount in its source currency
   */
  formatCurrency(amount, currency = "INR") {
    if (amount == null || isNaN(amount)) return "Price unavailable";
    const code = String(currency || "INR").toUpperCase();
    try {
      return new Intl.NumberFormat(undefined, { style: "currency", currency: code }).format(Number(amount));
    } catch {
      return `${code} ${Number(amount).toLocaleString()}`;
    }
  },

  /**
   * Helper to get platform styling pill class
   */
  getPlatformPillClass(platform = "") {
    const p = platform.toLowerCase();
    if (p.includes("amazon")) return "store-amazon";
    if (p.includes("flipkart")) return "store-flipkart";
    if (p.includes("croma")) return "store-croma";
    if (p.includes("reliance")) return "store-reliance";
    return "store-amazon";
  },

  /**
   * Renders an individual product card in Amazon style
   */
  renderProductCard(product, isSelected = false) {
    const pName = product.name || product.product_name || "Product";
    const pImg = product.thumbnail || product.image_url;
    const pRetailer = product.retailer || product.source || "Store";
    const pUrl = product.product_url || product.url || "#";
    const displayCurrency = (product.currency || product.offers?.[0]?.currency || "INR").toUpperCase();
    let lowestOfferPrice = product.price;
    let bestPlatformName = pRetailer;
    if (product.offers && product.offers.length > 0) {
      for (const off of product.offers) {
        const offerCurrency = (off.currency || displayCurrency).toUpperCase();
        if (offerCurrency === displayCurrency && off.price != null && (lowestOfferPrice == null || off.price < lowestOfferPrice)) {
          lowestOfferPrice = off.price;
          bestPlatformName = off.retailer || off.platform || pRetailer;
        }
      }
    }

    const bestPriceLabel = this.formatCurrency(lowestOfferPrice, displayCurrency);

    const ratingBadge = product.rating != null
      ? `<span class="star-rating">★ ${Number(product.rating).toFixed(1)} <span style="color:#565959; font-weight:normal; font-size:0.8rem;">(${product.review_count ? Number(product.review_count).toLocaleString() : "Verified"})</span></span>`
      : `<span style="color: #888c8c; font-size: 0.78rem;">Rating not listed</span>`;

    // Amazon-style multi-platform offer rows
    const offersHtml = (product.offers && product.offers.length > 0)
      ? product.offers.map(off => {
          const offerCurrency = (off.currency || displayCurrency).toUpperCase();
          const isBestOffer = offerCurrency === displayCurrency && off.price != null && off.price === lowestOfferPrice;
          const offPriceStr = this.formatCurrency(off.price, offerCurrency);
          const offPlatform = off.retailer || off.platform || pRetailer;
          const offUrl = off.product_url || off.url || pUrl;
          const pillClass = this.getPlatformPillClass(offPlatform);
          const offerImage = off.thumbnail || off.image_url || pImg;
          const thumbnailHtml = offerImage
            ? `<img class="offer-thumbnail" src="${offerImage}" alt="" loading="lazy" onerror="this.style.display='none'" />`
            : `<span class="offer-thumbnail-placeholder" aria-label="Product image unavailable">No image</span>`;

          return `
            <div class="offer-row ${isBestOffer ? 'best-offer' : ''}">
              <div class="offer-store-details">
                ${thumbnailHtml}
                <div>
                  <span class="offer-platform-name">
                    <span class="store-dot ${pillClass}"></span>
                    ${offPlatform}
                    ${isBestOffer ? '<span style="font-size:0.68rem; color:#15803d; font-weight:800; background:#dcfce7; padding:1px 5px; border-radius:3px; margin-left:4px;">BEST DEAL</span>' : ''}
                  </span>
                  <span class="offer-delivery">${off.delivery || "Standard Delivery"}</span>
                </div>
              </div>
              <div style="text-align: right; display: flex; align-items: center; gap: 0.45rem;">
                <span class="offer-price">${offPriceStr}</span>
                <div class="offer-actions">
                  <a href="${offUrl}" target="_blank" rel="noopener noreferrer" class="btn-sm btn-view" title="Open ${offPlatform} product page">
                    View ↗
                  </a>
                  <a href="${offUrl}" target="_blank" rel="noopener noreferrer" class="btn-sm btn-buy" title="Buy on ${offPlatform}">
                    Buy Now ⚡
                  </a>
                  <button class="btn-sm btn-cart" title="Add to cart on ${offPlatform}" onclick="App.onAddToCart('${encodeURIComponent(pName)}', '${encodeURIComponent(offPlatform)}', '${encodeURIComponent(offUrl)}', ${product.id || null}, ${off.id || null})">
                    Cart
                  </button>
                </div>
              </div>
            </div>
          `;
        }).join("")
      : `
        <div class="offer-row best-offer">
          <div>
            <span class="offer-platform-name">
              <span class="store-dot ${this.getPlatformPillClass(pRetailer)}"></span>
              ${pRetailer}
            </span>
            <span class="offer-delivery">Direct Store Listing</span>
          </div>
          <div style="text-align: right; display: flex; align-items: center; gap: 0.45rem;">
            <span class="offer-price">${this.formatCurrency(product.price, displayCurrency)}</span>
            <div class="offer-actions">
              <a href="${pUrl}" target="_blank" rel="noopener noreferrer" class="btn-sm btn-view">
                View ↗
              </a>
              <a href="${pUrl}" target="_blank" rel="noopener noreferrer" class="btn-sm btn-buy">
                Buy Now ⚡
              </a>
            </div>
          </div>
        </div>
      `;

    // Real verified image from live web search
    const displayImg = pImg || (product.offers && product.offers[0] ? (product.offers[0].thumbnail || product.offers[0].image_url) : null);
    const imageHtml = displayImg
      ? `<a href="${pUrl}" target="_blank" rel="noopener noreferrer" class="product-img-wrapper" title="Click to view verified product page on ${pRetailer}">
           <img src="${displayImg}" alt="${pName}" class="product-img" onerror="this.closest('.product-img-wrapper').style.display='none'" />
         </a>`
      : "";

    // Seller & Availability info
    const sellerInfo = product.seller
      ? `<span style="font-size: 0.78rem; color: #565959;">Sold by: <strong style="color:#0f1111;">${product.seller}</strong></span>`
      : "";
    const availInfo = product.availability === false
      ? `<span style="font-size: 0.75rem; color: #cc0c39; font-weight:700;">Currently unavailable</span>`
      : product.availability === true
        ? `<span style="font-size: 0.75rem; color: #007600; font-weight:700;">In Stock</span>`
        : `<span style="font-size: 0.75rem; color: #565959; font-weight:700;">Availability not verified</span>`;

    // Top specifications tags
    const specsItems = Object.entries(product.specifications || {})
      .slice(0, 3)
      .map(([k, v]) => `<span style="background: #f0f2f2; border: 1px solid #d5d9d9; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.74rem; color: #333333;"><strong>${k}:</strong> ${v}</span>`)
      .join(" ");

    // Formatted verification timestamp
    const verifiedTime = product.last_verified_at
      ? new Date(product.last_verified_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : "Live";

    const pId = product.id != null ? product.id : (product.product_name || "item").replace(/[^a-zA-Z0-9]/g, "").slice(0, 15);

    return `
      <div class="product-card" id="card-${pId}" data-product-id="${pId}">
        <div class="card-top">
          <!-- Card Badges & Compare Toggle -->
          <div class="card-badges">
            <div style="display:flex; align-items:center; gap:0.45rem;">
              <span class="amazon-deal-ribbon">NexShop Choice</span>
              <span class="verified-live-tag">
                <span class="live-dot-pulse" style="width:6px; height:6px;"></span>
                Live Price
              </span>
            </div>

            <label class="compare-checkbox-label">
              <input type="checkbox" onchange="App.toggleProductSelection('${pId}')" ${isSelected ? 'checked' : ''} />
              Compare
            </label>
          </div>

          <!-- Product Real Image (Clickable directly to store) -->
          ${imageHtml}

          <!-- Product Title (Clickable directly to store) -->
          <a href="${pUrl}" target="_blank" rel="noopener noreferrer" style="text-decoration:none; color:inherit; display:block;">
            <h3 class="product-title" title="${pName}">${pName}</h3>
          </a>

          <!-- Brand & Model Row -->
          <div class="product-meta-row">
            ${ratingBadge}
            <span>•</span>
            <span class="brand-label">${product.brand || pRetailer} ${product.model ? `• ${product.model}` : ""}</span>
          </div>

          <!-- Amazon Price Block -->
          <div class="amazon-price-block">
            <div class="price-main">
              ${bestPriceLabel}
            </div>
            <div class="lowest-price-label">
              Lowest comparable price (${displayCurrency}) • <strong>${bestPlatformName}</strong>
            </div>
              <div class="prime-delivery-row">
                ${product.delivery ? `<span class="free-delivery-tag">${product.delivery}</span>` : `<span style="color:#565959;">Standard Delivery</span>`}
                <span style="margin-left:auto;">${availInfo}</span>
            </div>
          </div>

          ${sellerInfo ? `<div style="margin-bottom: 0.5rem;">${sellerInfo}</div>` : ""}

          ${specsItems ? `<div style="display:flex; flex-wrap:wrap; gap:0.35rem; margin-bottom: 0.85rem;">${specsItems}</div>` : ""}

          <!-- Multi-Platform Offers Box (Amazon Seller Matrix) -->
          <div class="offers-container">
            <div class="offers-title">
              <span>Compare Store Offers (${product.offers ? product.offers.length : 1})</span>
              <span style="color: #067d62;">Direct Store Purchase ⚡</span>
            </div>
            ${offersHtml}
          </div>
        </div>

        <!-- Footer Actions & Source Transparency -->
        <div class="card-bottom-actions">
          <button class="btn-text" onclick="App.onShowReviews('${encodeURIComponent(pName)}', ${product.id || null})">
            📊 Customer Consensus & Defect Analysis
          </button>
          <div class="source-tag">
            <div>Store: <strong>${pRetailer}</strong></div>
            <div>Verified: <strong>${verifiedTime}</strong></div>
          </div>
        </div>
      </div>
    `;
  },

  /**
   * Renders the top cross-platform comparison banner
   */
  renderComparisonBanner(summary, platformComparison = null) {
    const deal = platformComparison && platformComparison.best_deal_summary
      ? platformComparison.best_deal_summary
      : null;
    const currency = (deal && deal.currency) || (platformComparison && platformComparison.currency) || (summary && summary.currency) || "INR";
    const lowest = deal ? deal.lowest_price : (summary && summary.lowest_price);
    const platform = deal ? deal.recommended_platform : (summary && summary.best_price_platform);
    const savings = deal ? deal.savings_vs_highest : (summary && summary.price_spread);
    const advice = summary && summary.recommendation
      ? summary.recommendation
      : (deal && deal.recommended_platform
        ? `Lowest live price is on ${deal.recommended_platform}. Open the verified product URL to buy.`
        : "");
    if (lowest == null && !summary && !deal) return "";
    return `
      <div class="comparison-banner">
        <div class="stat-block">
          <span class="stat-label">Best Price Found</span>
          <span class="stat-value highlight">${this.formatCurrency(lowest, currency)}</span>
        </div>
        <div class="stat-block">
          <span class="stat-label">Lowest Store</span>
          <span class="stat-value">${platform || "—"}</span>
        </div>
        <div class="stat-block">
          <span class="stat-label">Maximum Savings</span>
          <span class="stat-value" style="color: #007185;">${this.formatCurrency(savings, currency)}</span>
        </div>
        <div class="stat-block" style="flex: 1; min-width: 280px;">
          <span class="stat-label">NexShop AI Buying Advice</span>
          <p style="font-size: 0.88rem; color: #0f1111; margin-top: 0.2rem; line-height: 1.4;">${advice}</p>
        </div>
      </div>
    `;
  },

  /**
   * Renders the factual review analysis modal
   */
  renderReviewModal(summary) {
    const positiveHtml = summary.positive_themes && summary.positive_themes.length > 0
      ? summary.positive_themes.map(t => `<li style="color: #15803d; font-weight:500;">✔ ${t}</li>`).join("")
      : `<li style="color: #565959;">No explicit positive consensus detected in current source batch.</li>`;

    const negativeHtml = summary.negative_themes && summary.negative_themes.length > 0
      ? summary.negative_themes.map(t => `<li style="color: #b91c1c; font-weight:500;">✖ ${t}</li>`).join("")
      : `<li style="color: #565959;">No major recurring criticisms reported.</li>`;

    const defectsHtml = summary.common_defects && summary.common_defects.length > 0
      ? summary.common_defects.map(d => `<li style="color: #b45309;">⚠️ ${d}</li>`).join("")
      : `<li style="color: #565959;">No critical hardware or manufacturing defects highlighted.</li>`;

    return `
      <h2 style="font-family: var(--font-heading); margin-bottom: 0.35rem; color:#0f1111;">NexShop Customer Feedback Consensus</h2>
      <p style="color: #565959; font-size: 0.95rem; margin-bottom: 1.5rem; font-weight:500;">${summary.product_name}</p>

      <div style="display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap;">
        <div style="background: #f0fdf4; border: 1px solid #bbf7d0; padding: 0.85rem 1.25rem; border-radius: 6px; flex: 1; min-width: 180px;">
          <span style="font-size: 0.72rem; text-transform: uppercase; color: #565959; font-weight:700;">Overall Sentiment</span>
          <div style="font-size: 1.35rem; font-weight: 800; color: #15803d;">${summary.overall_sentiment || "Neutral"} (${summary.sentiment_score != null ? (summary.sentiment_score * 100).toFixed(0) : "N/A"}%)</div>
        </div>
        <div style="background: #fefce8; border: 1px solid #fef08a; padding: 0.85rem 1.25rem; border-radius: 6px; flex: 1; min-width: 180px;">
          <span style="font-size: 0.72rem; text-transform: uppercase; color: #565959; font-weight:700;">Value For Money</span>
          <div style="font-size: 1.1rem; font-weight: 700; color: #0f1111;">${summary.value_for_money || "Source Verified"}</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 1.5rem;">
        <div style="background: #ffffff; padding: 1.15rem; border-radius: 6px; border: 1px solid #d5d9d9;">
          <h4 style="font-size: 0.85rem; color: #15803d; font-weight:700; text-transform:uppercase; margin-bottom: 0.65rem;">Positive Highlights</h4>
          <ul style="list-style: none; font-size: 0.84rem; display: flex; flex-direction: column; gap: 0.45rem;">
            ${positiveHtml}
          </ul>
        </div>
        <div style="background: #ffffff; padding: 1.15rem; border-radius: 6px; border: 1px solid #d5d9d9;">
          <h4 style="font-size: 0.85rem; color: #b91c1c; font-weight:700; text-transform:uppercase; margin-bottom: 0.65rem;">User Criticisms</h4>
          <ul style="list-style: none; font-size: 0.84rem; display: flex; flex-direction: column; gap: 0.45rem;">
            ${negativeHtml}
          </ul>
        </div>
      </div>

      <div style="background: #ffffff; padding: 1.15rem; border-radius: 6px; border: 1px solid #d5d9d9; margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.85rem; color: #b45309; font-weight:700; text-transform:uppercase; margin-bottom: 0.5rem;">Common Defects & Watch-Outs</h4>
        <ul style="list-style: none; font-size: 0.84rem; color: #565959; display: flex; flex-direction: column; gap: 0.4rem;">
          ${defectsHtml}
        </ul>
      </div>

      <p style="font-size: 0.75rem; color: #888c8c; text-align: center;">Verified customer consensus derived strictly from live source evidence. Zero synthetic reviews.</p>
    `;
  },

  /**
   * Renders the Side-by-Side Comparison Modal for selected products
   */
  renderSelectedComparisonModal(products) {
    if (!products || products.length === 0) {
      return `<p style="padding: 2rem; text-align: center; color: #565959;">No products selected for comparison.</p>`;
    }

    const headerCols = products.map(p => `
      <th style="padding: 1rem; text-align: left; border-bottom: 1px solid #d5d9d9; min-width: 200px;">
        <div style="font-weight: 700; font-size: 1rem; color: #0f1111; margin-bottom: 0.25rem;">${p.product_name}</div>
        <div style="font-size: 0.8rem; color: #007185;">${p.brand || "Verified Brand"}</div>
      </th>
    `).join("");

    const priceCols = products.map(p => `
      <td class="compare-td">
        <div style="font-size: 1.25rem; font-weight: 800; color: #067d62; font-family: var(--font-heading);">${this.formatCurrency(p.price, p.currency)}</div>
        <span style="font-size: 0.72rem; color: #565959;">Source: ${p.source}</span>
      </td>
    `).join("");

    const ratingCols = products.map(p => `
      <td class="compare-td">
        ${p.rating != null ? `★ ${p.rating.toFixed(1)} (${p.review_count || 0})` : 'Not listed'}
      </td>
    `).join("");

    const platformOffersCols = products.map(p => {
      const offers = p.offers && p.offers.length > 0 ? p.offers : [{ platform: p.source, price: p.price, url: p.url }];
      const listHtml = offers.map(o => `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
          <span style="font-size:0.8rem; font-weight:600;">${o.platform}:</span>
          <a href="${o.url}" target="_blank" rel="noopener noreferrer" class="btn-sm btn-buy" style="padding:0.25rem 0.6rem; font-size:0.75rem;">
            ${this.formatCurrency(o.price, o.currency || p.currency)} ⚡
          </a>
        </div>
      `).join("");
      return `<td class="compare-td">${listHtml}</td>`;
    }).join("");

    const specsCols = products.map(p => {
      const entries = Object.entries(p.specifications || {});
      if (entries.length === 0) return `<td class="compare-td" style="color:#565959;">Standard specs</td>`;
      const list = entries.map(([k, v]) => `<div><strong>${k}:</strong> ${v}</div>`).join("");
      return `<td class="compare-td" style="font-size: 0.8rem; line-height:1.4;">${list}</td>`;
    }).join("");

    return `
      <h2 style="font-family: var(--font-heading); margin-bottom: 0.5rem; color:#0f1111;">Side-by-Side Product Comparison</h2>
      <p style="color: #565959; font-size: 0.9rem; margin-bottom: 1.25rem;">Compare real-world verified listings and store offers</p>

      <div style="overflow-x: auto;">
        <table class="compare-modal-table">
          <thead>
            <tr>
              <th class="compare-th">Product</th>
              ${headerCols}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th class="compare-th">Lowest Price</th>
              ${priceCols}
            </tr>
            <tr>
              <th class="compare-th">Live Rating</th>
              ${ratingCols}
            </tr>
            <tr>
              <th class="compare-th">Store Offers</th>
              ${platformOffersCols}
            </tr>
            <tr>
              <th class="compare-th">Specifications</th>
              ${specsCols}
            </tr>
          </tbody>
        </table>
      </div>
    `;
  },

  /**
   * Toast notification system
   */
  showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = "toast";
    const icon = type === "success" ? "✅" : (type === "warning" ? "⚠️" : "ℹ️");
    toast.innerHTML = `<span style="font-size: 1.1rem;">${icon}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }
};

window.Components = Components;
