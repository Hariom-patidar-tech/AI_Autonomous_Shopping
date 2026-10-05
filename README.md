# Universal AI Shopping & Price Comparison Agent

A production-grade, agentic AI shopping and real-time price comparison system engineered to discover, evaluate, compare, and prepare checkouts for **any purchasable product on the open web**.

Built strictly on the principle of **Real Web Data > LLM Data**, ensuring **zero fabricated products, zero hallucinated prices, and zero fake retailer URLs**.

---

## 🌟 Key Capabilities & Architectural Pillars

1. **Universal Web Discovery (No Predefined Catalog)**:
   - Does not rely on hardcoded category branches or static inventories.
   - Discovers any purchasable product (e.g. *Redmi Note 10S*, *iPhone 17 Pro*, *HP i5 Laptop*, *Nike running shoes*, *Cat logo t-shirt*, or custom artisanal goods).

2. **Dual-Engine Live Search Orchestration & High Availability**:
   - **Tier 1 (Primary)**: Google Search Grounding with Gemini for authoritative real-time e-commerce discovery.
   - **Tier 2 (Secondary Web Provider)**: Autonomous multi-engine live web search scraper for discovery redundancy.
   - **Zero-Mock Policy**: If both live providers yield zero results or fail, the system honestly reports `"no_verified_results"` or `"provider_error"` with `data_source: "live"`. No mock or fallback data is ever injected into production.

3. **Multi-Lingual Query Understanding (English, Hindi, Hinglish)**:
   - Understands natural intent and budget constraints in English (*"laptop under 60000 for coding"*) and Hindi/Hinglish (*"mujhe 50000 ke andar 55 inch 4K TV chahiye"*, *"redmi ka sasta phone batao"*).
   - Deterministic NLP parser fallback ensures zero failure even when LLM services encounter rate limits.

4. **Deterministic Hard Constraint Filtering**:
   - Budget ceilings, minimum customer ratings, and in-stock conditions are evaluated deterministically in Python—never left to LLM estimation.
   - **Unknown Data Integrity**: Missing fields are preserved as `null`/`None` rather than fabricated or hallucinated.

5. **Category Mismatch Protection & Clean Alternative Separation**:
   - Prevents category contamination (e.g. searching for a t-shirt will never return TVs or laptops).
   - Distinguishes **Exact Matches** (matching requested brand & model) from **Alternatives & Variants** (same category or alternative specs) to prevent catalog confusion.

6. **Variant-Aware Deduplication & Cross-Platform Price Comparison**:
   - Preserves genuine hardware/color variants (e.g. 64GB vs 128GB) as distinct products.
   - Aggregates cross-platform offers (Amazon, Flipkart, Croma, Ajio, Myntra) under the same product card.
   - Calculates the price spread, highlights the lowest price platform, and computes maximum user savings.

7. **Source-Backed Review & Defect Synthesis**:
   - Extracts consensus sentiment, positive highlights, critical defects, and value-for-money metrics strictly grounded in source review evidence.

8. **Human Payment Control & Safe Cart Handoff**:
   - **Mode A / Mode B Cart Addition**: Automated carting with fallback to direct verified retailer deep-links.
   - **Payment Safety Barrier**: The agent strictly terminates before checkout authorization. It is permanently prohibited from handling financial secrets, CVV, OTP, or banking credentials.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    User([User Query / Hindi / Hinglish]) --> QU[Query Understander]
    QU --> QG[Dynamic Query Generator]
    QG --> SO[Search Orchestrator]
    
    SO -->|Primary| GGround[Google Search Grounding]
    SO -->|Secondary| WebP[Secondary Web Provider]
    
    GGround & WebP --> UV[URL & Image Verifier]
    UV --> Extractor[Metadata & Offer Extractor]
    Extractor --> RE[Relevance Engine & Category Protection]
    RE --> HF[Deterministic Hard Filter Engine]
    HF --> Dedupe[Variant-Aware Deduplicator]
    Dedupe --> Rank[Multi-Factor Ranking Engine]
    Comp --> API[FastAPI REST Endpoints]
    API --> UI[Glassmorphic Dark Mode Web UI]
    API --> DB[(PostgreSQL / SQLite Database)]
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.11+** installed.
- **PostgreSQL** running locally on port 5432 (or let the app automatically fallback to SQLite).
- A valid Google Gemini API key or live search connection for real-time web discovery.

### 2. Environment Configuration
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```ini
APP_NAME=Universal AI Shopping & Price Comparison Agent
APP_ENV=production
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# PostgreSQL Database (automatically falls back to SQLite if unreachable)
DATABASE_URL=postgresql://postgres:mypostgresql@localhost:5432/shopping_agent
FALLBACK_SQLITE_URL=sqlite:///shopping_agent.db
```

### 3. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 4. Run Automated Test Suite
Verify that all 24 unit and integration tests pass:
```bash
python -m pytest -v
```

### 5. Launch the Application
Start the FastAPI server with Uvicorn:
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser at **[http://localhost:8000/](http://localhost:8000/)**.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | `GET` | System health check and database connectivity verification |
| `/api/products/search` | `GET` / `POST` | Universal product search with natural language & filters |
| `/api/products/{id}` | `GET` | Detailed product view with verified multi-platform offers |
| `/api/comparison` | `POST` | Cross-platform price comparison & savings analysis |
| `/api/reviews/analyze` | `POST` | Source-backed review synthesis & defect extraction |
| `/api/cart/add` | `POST` | Mode A/B cart addition with manual handoff fallback |
| `/api/cart/checkout` | `POST` | Human-controlled checkout handoff barrier |
| `/api/history` | `GET` | User search history and discovered product counts |
| `/api/history/audit` | `GET` | Agent audit logs for compliance and safety |

---

## 🔒 Security & Safety Guarantees

1. **Anti-Hallucination Policy**: Every product, offer, price, seller, and URL returned must come directly from verified live search grounding or live web scraping. The system will **never invent a product, retailer URL, or price**, and never falls back to mock or dummy data.
2. **Zero Financial Secret Handling**: Under no circumstances does the agent store, request, or manipulate payment card CVVs, one-time passwords (OTPs), or online banking credentials.
3. **Verified Link Out**: All checkout actions redirect the user directly to the official merchant domain with `rel="noopener noreferrer"`.
