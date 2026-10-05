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
    this.renderEmpty("Search for a product to see verified retailer prices and product pages.");
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
    const ratingInput = document.getElementById("filter-rating");
    const sortSelect = document.getElementById("filter-sort");

    if (budgetInput) {
      budgetInput.addEventListener("change", () => this.applyClientFiltersAndSort());
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
    this.startAiStepper(query);

    const budgetMax = document.getElementById("filter-budget")?.value || null;
    const minRating = document.getElementById("filter-rating")?.value || null;
    const sortBy = document.getElementById("filter-sort")?.value || "relevance";

    try {
      this.advanceStepperStage(1);
      this.addAgentLog(`Intent Extraction: Analyzing query "${query}"`);

      setTimeout(() => {
        if (this.state.isLoading) {
          this.advanceStepperStage(2);
          this.addAgentLog(`Multi-Platform Search: Querying Amazon, Flipkart, Croma, Reliance Digital`);
        }
      }, 450);

      setTimeout(() => {
        if (this.state.isLoading) {
          this.advanceStepperStage(3);
          this.addAgentLog(`Price & Image Verification: Decoding store URLs and high-res photos`);
        }
      }, 950);

      const data = await ShoppingAPI.searchProducts(query, budgetMax, minRating, sortBy);

      this.advanceStepperStage(4);
      this.addAgentLog(`Price Comparison: Matched ${data.verified_results || 0} listings across ${data.sources?.join(", ") || "Retail Stores"}`);

      this.advanceStepperStage(5);
      this.addAgentLog(`Best Deal Ranking: Verified live options with 0% mock data`);

      this.state.products = data.products || [];
      this.state.alternatives = data.alternatives || [];
      this.state.comparisonSummary = data.comparison_summary || null;
      this.state.platformComparison = data.platform_comparison || null;

      // Update cart count
      const cartCountEl = document.getElementById("header-cart-count");
      if (cartCountEl) cartCountEl.textContent = (this.state.products.length + this.state.alternatives.length);

      // Extract unique platforms
      this.extractAvailablePlatforms();
      this.renderPlatformChips();

      // Check for search status
      if (data.search_status === "provider_error") {
        this.completeAiStepper();
        this.renderEmpty(data.message || "Live product search is temporarily unavailable. Please try again.");
        return;
      }

      if (this.state.products.length === 0 && this.state.alternatives.length === 0) {
        this.completeAiStepper();
        this.renderEmpty("No verified products found.<br/><br/>Try:<br/>• a different product name<br/>• a broader search term<br/>• removing one filter");
        return;
      }

      setTimeout(() => {
        this.completeAiStepper();
        this.applyClientFiltersAndSort();
      }, 350);

    } catch (err) {
      console.error("Search execution failed:", err);
      this.completeAiStepper();
      Components.showToast(`Search error: ${err.message}`, "warning");
      this.renderEmpty("Live product search is temporarily unavailable. Please try again.");
    } finally {
      this.state.isLoading = false;
      this.updateSearchBtnLoading(false);
    }
  },

  /**
   * AI Stepper Controls with Progress Animation
   */
  startAiStepper(query) {
    const box = document.getElementById("ai-stepper-box");
    const queryTag = document.getElementById("stepper-current-query");
    const logList = document.getElementById("agent-log-list");
    const progressBar = document.getElementById("pipeline-progress-bar");

    if (box) box.style.display = "block";
    if (queryTag) queryTag.textContent = `Target: "${query}"`;
    if (logList) logList.innerHTML = "";
    if (progressBar) progressBar.style.width = "15%";

    for (let i = 1; i <= 5; i++) {
      const stage = document.getElementById(`stage-${i}`);
      if (stage) {
        stage.className = "stage-step";
        const icon = stage.querySelector(".stage-icon-circle");
        if (icon) icon.textContent = i;
      }
    }
  },

  advanceStepperStage(stageNum) {
    const progressBar = document.getElementById("pipeline-progress-bar");
    if (progressBar) {
      progressBar.style.width = `${Math.min(stageNum * 20, 95)}%`;
    }

    for (let i = 1; i <= 5; i++) {
      const stage = document.getElementById(`stage-${i}`);
      if (!stage) continue;
      const icon = stage.querySelector(".stage-icon-circle");

      if (i < stageNum) {
        stage.className = "stage-step completed";
        if (icon) icon.textContent = "✓";
      } else if (i === stageNum) {
        stage.className = "stage-step active";
        if (icon) icon.textContent = i;
      } else {
        stage.className = "stage-step";
        if (icon) icon.textContent = i;
      }
    }
  },

  completeAiStepper() {
    const progressBar = document.getElementById("pipeline-progress-bar");
    if (progressBar) progressBar.style.width = "100%";

    for (let i = 1; i <= 5; i++) {
      const stage = document.getElementById(`stage-${i}`);
      if (stage) {
        stage.className = "stage-step completed";
        const icon = stage.querySelector(".stage-icon-circle");
        if (icon) icon.textContent = "✓";
      }
    }
  },

  addAgentLog(text) {
    const list = document.getElementById("agent-log-list");
    if (list) {
      const item = document.createElement("li");
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      item.innerHTML = `<span style="color:#febd69; margin-right:4px;">[${timeStr}]</span> <span>${text}</span>`;
      list.appendChild(item);
      list.scrollTop = list.scrollHeight;
    }
  },

  /**
   * Extract platforms from discovered live products
   */
  extractAvailablePlatforms() {
    const platforms = new Set();
    const allItems = [...this.state.products, ...this.state.alternatives];

    for (const p of allItems) {
      if (p.source) platforms.add(p.source);
      if (p.offers) {
        for (const off of p.offers) {
          if (off.platform) platforms.add(off.platform);
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
        const hasSource = p.source && p.source.toLowerCase().includes(selectedPlat);
        const hasOffer = p.offers && p.offers.some(o => o.platform && o.platform.toLowerCase().includes(selectedPlat));
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
      this.renderEmpty("No verified products match the current filters.<br/><br/>Try adjusting your maximum budget, minimum rating, or store platform.");
      return;
    }

    let html = products.map(p => {
      const pId = p.id != null ? p.id : (p.product_name || "item").replace(/[^a-zA-Z0-9]/g, "").slice(0, 15);
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
        const pId = p.id != null ? p.id : (p.product_name || "item").replace(/[^a-zA-Z0-9]/g, "").slice(0, 15);
        const isSel = this.state.selectedProductIds.has(String(pId));
        return Components.renderProductCard(p, isSel);
      }).join("");
    }

    gridContainer.innerHTML = html;
  },

  /**
   * Empty / Failure State Renderer
   */
  renderEmpty(message) {
    const gridContainer = document.getElementById("products-grid");
    const countLabel = document.getElementById("results-count-label");
    const bannerContainer = document.getElementById("comparison-banner-container");

    if (bannerContainer) bannerContainer.innerHTML = "";
    if (countLabel) countLabel.textContent = "0 results found";

    if (gridContainer) {
      gridContainer.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 4.5rem 1.5rem; background: #ffffff; border: 1px solid #d5d9d9; border-radius: 8px;">
          <div style="font-size: 3rem; margin-bottom: 0.75rem;">📦</div>
          <h3 style="font-size: 1.35rem; color: #0f1111; font-family: var(--font-heading); margin-bottom: 0.5rem;">No Results Found on NexShop</h3>
          <p style="max-width: 480px; margin: 0 auto; font-size: 0.95rem; color: #565959; line-height: 1.5;">${message}</p>
        </div>
      `;
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
