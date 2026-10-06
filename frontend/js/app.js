/**
 * ==========================================================================
 * NEXSHOP — PRODUCTION APP CONTROLLER (AMAZON-INSPIRED)
 * Zero Mock Data • Real-World Live Discovery • Direct Store Links
 * ==========================================================================
 */

const App = {
  state: {
    currentQuery: "",
    products: [],
    alternatives: [],
    comparisonSummary: null,
    platformComparison: null,
    selectedPlatform: "all",
    selectedProductIds: new Set(),
    isLoading: false,
    availablePlatforms: new Set(),
  },

  init() {
    this.bindEvents();
    this.renderEmpty("Search for a product to see verified retailer prices and product pages.", {
      title: "Ready to search",
      countLabel: "Search ready",
    });
  },

  bindEvents() {
    const searchForm = document.getElementById("search-form");
    const searchInput = document.getElementById("search-input");
    const clearBtn = document.getElementById("clear-search-btn");

    if (searchForm) {
      searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const q = searchInput ? searchInput.value.trim() : "";
        if (q) {
          this.executeSearch(q);
        }
      });
    }

    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        if (clearBtn) {
          clearBtn.style.display = e.target.value.trim() ? "flex" : "none";
        }
      });
    }

    // Filter event listeners
    const budgetInput = document.getElementById("filter-budget");
    const budgetCurrency = document.getElementById("filter-currency");
    const ratingInput = document.getElementById("filter-rating");
    const sortSelect = document.getElementById("filter-sort");

    if (budgetInput) {
      budgetInput.addEventListener("change", () => this.executeSearch(this.state.currentQuery));
    }
    if (budgetCurrency) {
      budgetCurrency.addEventListener("change", () => this.executeSearch(this.state.currentQuery));
    }
    if (ratingInput) {
      ratingInput.addEventListener("change", () => this.applyClientFiltersAndSort());
    }
    if (sortSelect) {
      sortSelect.addEventListener("change", () => this.applyClientFiltersAndSort());
    }

    // Modal background close
    const modal = document.getElementById("main-modal");
    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) this.closeModal();
      });
    }

    // Escape key modal close
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") this.closeModal();
    });
  },

  /**
   * Universal Product Search Execution
   */
  async executeSearch(query) {
    if (!query || this.state.isLoading) return;

    this.state.isLoading = true;
    this.state.currentQuery = query;
    this.state.selectedProductIds.clear();
    this.updateSelectionCompareBar();

    const input = document.getElementById("search-input");
    if (input) {
      input.value = query;
      const clearBtn = document.getElementById("clear-search-btn");
      if (clearBtn) clearBtn.style.display = "flex";
    }

    this.updateSearchBtnLoading(true);

    const gridContainer = document.getElementById("products-grid");
    const countLabel = document.getElementById("results-count-label");
    const bannerContainer = document.getElementById("comparison-banner-container");
    if (bannerContainer) bannerContainer.innerHTML = "";
    if (countLabel) countLabel.textContent = `Searching for "${query}"...`;
    if (gridContainer) {
      gridContainer.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1.5rem; background: #ffffff; border: 1px solid #d5d9d9; border-radius: 8px;">
          <div class="spinner" style="width: 36px; height: 36px; border: 3px solid #f3f3f3; border-top: 3px solid #f08804; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 1rem;"></div>
          <h3 style="font-size: 1.15rem; color: #0f1111; font-weight: 600; margin-bottom: 0.35rem;">Searching stores for "${query}"</h3>
          <p style="font-size: 0.88rem; color: #565959;">Finding real products and comparing prices...</p>
        </div>
      `;
    }

    const budgetMax = document.getElementById("filter-budget")?.value || null;
    const budgetCurrency = document.getElementById("filter-currency")?.value || "INR";
    const minRating = document.getElementById("filter-rating")?.value || null;
    const sortBy = document.getElementById("filter-sort")?.value || "relevance";

    try {
      const data = await ShoppingAPI.searchProducts(query, budgetMax, budgetCurrency, minRating, sortBy);

      this.consumeSearchResponse(data);

      // Check for search status
      if (data.search_status === "provider_error") {
        this.renderEmpty(data.message || "The live search provider is unavailable. Check its quota and try again.", {
          title: "Live search unavailable",
          countLabel: "Search unavailable",
          retry: true,
        });
        return;
      }

      if (this.state.products.length === 0 && this.state.alternatives.length === 0) {
        this.renderEmpty(data.message || "No products found", {
          title: "No products found",
          countLabel: "0 products found",
        });
        return;
      }

      this.applyClientFiltersAndSort();

    } catch (err) {
      console.error("Search execution failed:", err);
      Components.showToast(`Search error: ${err.message}`, "warning");
      this.renderEmpty(`Live search request failed: ${err.message}`, {
        title: "Search request failed",
        countLabel: "Search unavailable",
        retry: true,
      });
    } finally {
      this.state.isLoading = false;
      this.updateSearchBtnLoading(false);
    }
  },

  consumeSearchResponse(data) {
    this.state.products = Array.isArray(data?.products) ? data.products : [];
    this.state.alternatives = Array.isArray(data?.alternatives) ? data.alternatives : [];
    this.state.comparisonSummary = data?.comparison_summary || null;
    this.state.platformComparison = data?.platform_comparison || null;

    const cartCountEl = document.getElementById("header-cart-count");
    if (cartCountEl) cartCountEl.textContent = this.state.products.length + this.state.alternatives.length;

    this.extractAvailablePlatforms();
    this.renderPlatformChips();
    return this.state.products.length + this.state.alternatives.length;
  },

  // Stepper helper stubs (stepper UI removed)
  startAiStepper(query) {},
  advanceStepperStage(stageNum) {},
  completeAiStepper() {},
  addAgentLog(text) {},

  /**
   * Extract platforms from discovered live products
   */
  extractAvailablePlatforms() {
    const platforms = new Set();
    const allItems = [...this.state.products, ...this.state.alternatives];

    for (const p of allItems) {
      const plat = p.retailer || p.source;
      if (plat) platforms.add(plat);
      if (p.offers) {
        for (const off of p.offers) {
          const offPlat = off.retailer || off.platform;
          if (offPlat) platforms.add(offPlat);
        }
      }
    }
    this.state.availablePlatforms = platforms;
  },

  /**
   * Render dynamic platform selector chips
   */
  renderPlatformChips() {
    const container = document.getElementById("platform-chips-container");
    if (!container) return;

    let html = `
      <button class="amazon-tab-btn ${this.state.selectedPlatform === 'all' ? 'active' : ''}" data-platform="all" onclick="App.filterByPlatform('all')">
        All Stores
      </button>
    `;

    this.state.availablePlatforms.forEach(plat => {
      const isActive = this.state.selectedPlatform.toLowerCase() === plat.toLowerCase();
      html += `
        <button class="amazon-tab-btn ${isActive ? 'active' : ''}" data-platform="${plat}" onclick="App.filterByPlatform('${plat}')">
          ${plat}
        </button>
      `;
    });

    container.innerHTML = html;
  },

  filterByPlatform(platform) {
    this.state.selectedPlatform = platform;
    this.renderPlatformChips();
    this.applyClientFiltersAndSort();
  },

  /**
   * Apply Client-side Filtering & Sorting
   */
  applyClientFiltersAndSort() {
    const budgetMax = parseFloat(document.getElementById("filter-budget")?.value) || null;
    const minRating = parseFloat(document.getElementById("filter-rating")?.value) || null;
    const sortBy = document.getElementById("filter-sort")?.value || "relevance";
    const selectedPlat = this.state.selectedPlatform.toLowerCase();

    const filterItem = (p) => {
      // Platform check
      if (selectedPlat !== "all") {
        const plat = (p.retailer || p.source || "").toLowerCase();
        const hasSource = plat.includes(selectedPlat);
        const hasOffer = p.offers && p.offers.some(o => (o.retailer || o.platform || "").toLowerCase().includes(selectedPlat));
        if (!hasSource && !hasOffer) return false;
      }
      // Budget check
      if (budgetMax != null && p.price != null && p.price > budgetMax) {
        return false;
      }
      // Rating check
      if (minRating != null && p.rating != null && p.rating < minRating) {
        return false;
      }
      return true;
    };

    let filteredProducts = this.state.products.filter(filterItem);
    let filteredAlternatives = this.state.alternatives.filter(filterItem);

    // Sorting
    const sortFn = (a, b) => {
      if (sortBy === "price_asc") {
        return (a.price || 9999999) - (b.price || 9999999);
      } else if (sortBy === "price_desc") {
        return (b.price || 0) - (a.price || 0);
      } else if (sortBy === "rating") {
        return (b.rating || 0) - (a.rating || 0);
      } else if (sortBy === "savings") {
        const savingsA = a.offers && a.offers.length > 1 ? Math.max(...a.offers.map(o => o.price)) - Math.min(...a.offers.map(o => o.price)) : 0;
        const savingsB = b.offers && b.offers.length > 1 ? Math.max(...b.offers.map(o => o.price)) - Math.min(...b.offers.map(o => o.price)) : 0;
        return savingsB - savingsA;
      }
      return 0; // Featured / Relevance default
    };

    filteredProducts.sort(sortFn);
    filteredAlternatives.sort(sortFn);

    this.renderProductsList(filteredProducts, filteredAlternatives);
  },

  /**
   * Render filtered products in the grid
   */
  renderProductsList(products, alternatives) {
    const bannerContainer = document.getElementById("comparison-banner-container");
    const gridContainer = document.getElementById("products-grid");
    const countLabel = document.getElementById("results-count-label");

    if (bannerContainer) {
      bannerContainer.innerHTML = Components.renderComparisonBanner(
        this.state.comparisonSummary,
        this.state.platformComparison
      );
    }

    if (!gridContainer) return;

    const totalCount = products.length + alternatives.length;
    if (countLabel) {
      countLabel.textContent = `Showing 1-${totalCount} of ${totalCount} results for "${this.state.currentQuery}"`;
    }

    if (totalCount === 0) {
      this.renderEmpty("Try adjusting the budget, rating, or store filters.", {
        title: "No offers match these filters",
        countLabel: "0 matching offers",
      });
      return;
    }

    let html = products.map(p => {
      const pId = p.product_id != null ? p.product_id : (p.id != null ? p.id : (p.name || p.product_name || "item").replace(/[^a-zA-Z0-9]/g, "").slice(0, 15));
      const isSel = this.state.selectedProductIds.has(String(pId));
      return Components.renderProductCard(p, isSel);
    }).join("");

    if (alternatives.length > 0) {
      html += `
        <div style="grid-column: 1 / -1; margin-top: 1.5rem; margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 2px solid #e7e7e7;">
          <h3 style="font-family: var(--font-heading); color: var(--text-primary); font-size: 1.35rem; font-weight:700;">
            Related Live Alternatives & Variants
          </h3>
          <p style="font-size: 0.85rem; color: #565959;">Verified products discovered with related specifications</p>
        </div>
      `;
      html += alternatives.map(p => {
        const pId = p.product_id != null ? p.product_id : (p.id != null ? p.id : (p.name || p.product_name || "item").replace(/[^a-zA-Z0-9]/g, "").slice(0, 15));
        const isSel = this.state.selectedProductIds.has(String(pId));
        return Components.renderProductCard(p, isSel);
      }).join("");
    }

    gridContainer.innerHTML = html;
  },

  /**
   * Empty / Failure State Renderer
   */
  renderEmpty(message, options = {}) {
    const gridContainer = document.getElementById("products-grid");
    const countLabel = document.getElementById("results-count-label");
    const bannerContainer = document.getElementById("comparison-banner-container");
    const title = options.title || "No verified products found";

    if (bannerContainer) bannerContainer.innerHTML = "";
    if (countLabel) countLabel.textContent = options.countLabel || "0 verified offers";

    if (gridContainer) {
      gridContainer.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 4.5rem 1.5rem; background: #ffffff; border: 1px solid #d5d9d9; border-radius: 8px;">
          <div style="font-size: 3rem; margin-bottom: 0.75rem;">📦</div>
          <h3 style="font-size: 1.35rem; color: #0f1111; font-family: var(--font-heading); margin-bottom: 0.5rem;">${title}</h3>
          <p style="max-width: 480px; margin: 0 auto; font-size: 0.95rem; color: #565959; line-height: 1.5;">${message}</p>
          ${options.retry ? `<button type="button" id="retry-search-btn" class="btn-sm btn-view" style="margin-top:1rem;">Retry search</button>` : ""}
        </div>
      `;
      const retryButton = document.getElementById("retry-search-btn");
      if (retryButton) {
        retryButton.addEventListener("click", () => {
          if (this.state.currentQuery) this.executeSearch(this.state.currentQuery);
        });
      }
    }
  },

  /**
   * Direct Buy Now & View Navigation ("Buy pr click kru to vohi product page open hona chahiye")
   */
  onBuyNow(productName, platform, productUrl, price, productId = null) {
    const pName = decodeURIComponent(productName);
    const plat = decodeURIComponent(platform);
    const url = decodeURIComponent(productUrl);

    Components.showToast(`Opening verified ${plat} listing for ${pName}... ⚡`, "success");
    // Direct navigation to the actual product page on the store platform!
    window.open(url, "_blank", "noopener,noreferrer");
  },

  /**
   * Add To Cart Handoff
   */
  async onAddToCart(productName, platform, productUrl, productId = null, offerId = null) {
    const pName = decodeURIComponent(productName);
    const plat = decodeURIComponent(platform);
    const url = decodeURIComponent(productUrl);

    try {
      Components.showToast(`Checking cart support for ${plat}...`, "info");
      const res = await ShoppingAPI.addToCart(pName, plat, url, productId, offerId);

      if (res.status === "manual_action_required") {
        Components.showToast(`Opening ${plat} product page to add to your personal cart.`, "warning");
        setTimeout(() => window.open(url, "_blank", "noopener,noreferrer"), 800);
      } else {
        Components.showToast(res.message, "success");
      }
    } catch (err) {
      Components.showToast(`Cart assistance unavailable: ${err.message}. Opening product page.`, "warning");
      window.open(url, "_blank", "noopener,noreferrer");
    }
  },

  /**
   * AI Consensus & Review Inspection
   */
  async onShowReviews(productName, productId = null) {
    const pName = decodeURIComponent(productName);
    this.openModal(`
      <div style="text-align: center; padding: 2.5rem 1rem;">
        <div class="spinner"></div>
        <p style="margin-top: 1rem; color: #565959; font-size: 0.9rem;">Analyzing live customer reviews for "${pName}"...</p>
      </div>
    `);

    try {
      const summary = await ShoppingAPI.analyzeReviews(pName, productId);
      this.openModal(Components.renderReviewModal(summary));
    } catch (err) {
      this.openModal(`
        <div style="padding: 1.5rem;">
          <h3 style="color: #cc0c39; margin-bottom: 0.5rem;">Review Analysis Error</h3>
          <p style="color: #565959; font-size:0.9rem;">${err.message || "Failed to load live review consensus."}</p>
        </div>
      `);
    }
  },

  /**
   * Side-by-Side Product Comparison Selection
   */
  toggleProductSelection(pId) {
    const idStr = String(pId);
    if (this.state.selectedProductIds.has(idStr)) {
      this.state.selectedProductIds.delete(idStr);
    } else {
      if (this.state.selectedProductIds.size >= 4) {
        Components.showToast("Maximum 4 products can be compared side-by-side.", "warning");
        return;
      }
      this.state.selectedProductIds.add(idStr);
    }
    this.updateSelectionCompareBar();
  },

  updateSelectionCompareBar() {
    const bar = document.getElementById("selection-compare-bar");
    const countSpan = document.getElementById("selected-compare-count");
    if (!bar || !countSpan) return;

    const count = this.state.selectedProductIds.size;
    if (count > 0) {
      bar.style.display = "flex";
      countSpan.textContent = `${count} item${count > 1 ? 's' : ''} selected`;
    } else {
      bar.style.display = "none";
    }
  },

  openSelectedComparisonModal() {
    const allItems = [...this.state.products, ...this.state.alternatives];
    const selected = allItems.filter(p => {
      const pId = p.id != null ? p.id : (p.product_name || "item").replace(/[^a-zA-Z0-9]/g, "").slice(0, 15);
      return this.state.selectedProductIds.has(String(pId));
    });

    if (selected.length === 0) {
      Components.showToast("Please select at least one product using the 'Compare' checkbox.", "warning");
      return;
    }

    this.openModal(Components.renderSelectedComparisonModal(selected));
  },

  setQuery(text) {
    const input = document.getElementById("search-input");
    if (input) {
      input.value = text;
      this.executeSearch(text);
    }
  },

  clearSearch() {
    const input = document.getElementById("search-input");
    const clearBtn = document.getElementById("clear-search-btn");
    if (input) input.value = "";
    if (clearBtn) clearBtn.style.display = "none";
  },

  openModal(htmlContent) {
    const modal = document.getElementById("main-modal");
    const container = document.getElementById("modal-body-container");
    if (modal && container) {
      container.innerHTML = htmlContent;
      modal.style.display = "flex";
      document.body.style.overflow = "hidden";
    }
  },

  closeModal() {
    const modal = document.getElementById("main-modal");
    if (modal) {
      modal.style.display = "none";
      document.body.style.overflow = "";
    }
  },

  updateSearchBtnLoading(isLoading) {
    const btn = document.getElementById("search-submit-btn");
    if (btn) {
      btn.innerHTML = isLoading
        ? `<div class="spinner"></div>`
        : `<span class="search-mag-icon">🔍</span>`;
      btn.disabled = isLoading;
    }
  }
};

window.App = App;
document.addEventListener("DOMContentLoaded", () => App.init());
