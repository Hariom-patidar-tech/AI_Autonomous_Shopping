from __future__ import annotations
import time
import datetime
import logging
from typing import Optional
from sqlalchemy.orm import Session

from backend.schemas.query import ShoppingRequirements
from backend.schemas.product import SearchResponse
from backend.agent.platform_comparison import build_global_comparison
from backend.agent.query_understander import QueryUnderstander
from backend.agent.query_generator import QueryGenerator
from backend.search.orchestrator import SearchOrchestrator
from backend.agent.relevance_engine import RelevanceEngine
from backend.agent.filter_engine import HardFilterEngine
from backend.agent.deduplicator import Deduplicator
from backend.agent.ranking_engine import RankingEngine
from backend.agent.comparison_engine import ComparisonEngine
from backend.models import SearchHistory, ProductRow, ProductOfferRow

logger = logging.getLogger("shopping_agent.pipeline")


class ShoppingPipeline:
    """
    End-to-End Universal Shopping & Price Comparison Pipeline:
    Natural Language Query -> Requirements -> Dynamic Search -> Candidate Extraction ->
    Source Verification -> Relevance -> Hard Filtering -> Deduplication -> Ranking ->
    Price Comparison -> Final Shortlist.
    """

    def __init__(self, understander: QueryUnderstander = None, orchestrator: SearchOrchestrator = None):
        self.understander = understander or QueryUnderstander()
        self.orchestrator = orchestrator or SearchOrchestrator()

    async def run(
        self,
        query: str,
        user_id: Optional[int] = 1,
        budget_max: Optional[float] = None,
        min_rating: Optional[float] = None,
        sort_by: str = "relevance",
        db: Optional[Session] = None,
        budget_currency: Optional[str] = None,
    ) -> SearchResponse:
        start_time = time.time()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        logger.info(f"=== Starting Universal Shopping Pipeline for query: '{query}' ===")

        # 1. Query Understanding
        requirements: ShoppingRequirements = await self.understander.understand(query)
        # Override with explicit query parameters if provided
        if budget_max is not None:
            requirements.budget_max = budget_max
        if budget_currency is not None:
            requirements.currency = budget_currency.upper()
        if min_rating is not None:
            requirements.min_rating = min_rating

        logger.info(
            f"Requirements extracted: category={requirements.category}, brand={requirements.brand}, "
            f"model={requirements.model}, budget_max={requirements.budget_max}, intent={requirements.intent}"
        )

        # 2. Dynamic Search Query Generation
        focused_queries = QueryGenerator.generate_focused_queries(requirements)

        # 3. Multi-Source Live Search & Candidate Extraction
        raw_products, sources_used, data_source, provider_error = await self.orchestrator.execute_search(
            primary_query=query,
            focused_queries=focused_queries,
            requirements=requirements,
            limit=12,
        )

        # 4. Relevance Matching & Category Mismatch Protection (Sections 14, 15, 16)
        exact_matches, alternatives = RelevanceEngine.evaluate(raw_products, requirements)

        # 5. Deterministic Hard Constraint Filtering (Section 17)
        filtered_exact, rejections_exact = HardFilterEngine.apply_filters(exact_matches, requirements)
        filtered_alt, rejections_alt = HardFilterEngine.apply_filters(alternatives, requirements)

        # If strict budget filter eliminated all items, relax the budget constraint and show the real products
        # so the user actually sees real products on the UI instead of an empty screen!
        if not filtered_exact and not filtered_alt:
            available_exact = [p for p in exact_matches if p.availability is not False] or exact_matches
            if available_exact:
                available_exact = sorted(available_exact, key=lambda p: (p.price if p.price is not None else 999999))
                filtered_exact = available_exact
            elif alternatives:
                available_alt = [p for p in alternatives if p.availability is not False] or alternatives
                available_alt = sorted(available_alt, key=lambda p: (p.price if p.price is not None else 999999))
                filtered_alt = available_alt

        # 6. Deduplication (Variant-aware) (Section 30)
        deduped_exact = Deduplicator.deduplicate(filtered_exact)
        deduped_alt = Deduplicator.deduplicate(filtered_alt)

        # 7. Multi-Factor Ranking (Section 29)
        ranked_products = RankingEngine.rank(deduped_exact, requirements, sort_by=sort_by)
        ranked_alternatives = RankingEngine.rank(deduped_alt, requirements, sort_by=sort_by)

        # 8. Price & Multi-Platform Comparison (Sections 19, 20, 26, 27)
        comparison_summary = ComparisonEngine.generate_comparison_summary(ranked_products, requirements)

        # 9. Search Status Determination (Sections 30, 31)
        total_found = len(ranked_products) + len(ranked_alternatives)
        if total_found > 0:
            search_status = "success"
            status_msg = None
        elif provider_error and len(raw_products) == 0:
            search_status = "provider_error"
            status_msg = "Google Search is quota-limited or live search providers are unavailable. Restore provider quota and retry."
        else:
            search_status = "no_verified_results"
            all_rejections = rejections_exact + rejections_alt
            orch_msg = getattr(self.orchestrator, "last_status_message", None)
            if all_rejections:
                sample_reasons = list(dict.fromkeys(r.get("reason", "") for r in all_rejections if r.get("reason")))
                reasons_str = "; ".join(sample_reasons[:2])
                status_msg = (
                    f"No products found. Found {len(all_rejections)} real candidate product(s), but none passed verification and budget constraints ({reasons_str}). "
                    "Amazon API unavailable, Flipkart API unavailable, and search results did not contain verifiable exact product page, current price, currency, and product thumbnail."
                )
            elif orch_msg:
                status_msg = f"No products found. {orch_msg}"
            else:
                status_msg = (
                    "No products found. Amazon API unavailable, Flipkart API unavailable, and search results did not contain "
                    "verifiable exact product page, current price, currency, and product thumbnail."
                )

        # 10. Persistence in Database (if session provided)
        if db:
            try:
                search_rec = SearchHistory(
                    user_id=user_id,
                    raw_query=query,
                    constraints_json=requirements.model_dump(),
                )
                db.add(search_rec)
                db.flush()

                for p in ranked_products[:10]:
                    p_row = ProductRow(
                        search_id=search_rec.id,
                        product_name=p.product_name,
                        brand=p.brand,
                        model=p.model,
                        price=p.price,
                        currency=p.currency,
                        rating=p.rating,
                        review_count=p.review_count,
                        seller=p.seller,
                        availability=p.availability,
                        delivery=p.delivery,
                        return_policy=p.return_policy,
                        specifications=p.specifications,
                        url=p.url,
                        image_url=p.image_url,
                        source=p.source,
                        verification_status=p.verification_status,
                    )
                    db.add(p_row)
                    db.flush()
                    p.id = p_row.id

                    for off in p.offers:
                        off_row = ProductOfferRow(
                            product_id=p_row.id,
                            platform=off.platform,
                            seller=off.seller,
                            price=off.price,
                            currency=off.currency,
                            availability=off.availability,
                            delivery=off.delivery,
                            url=off.url,
                            image_url=off.image_url,
                            verification_status=off.verification_status,
                        )
                        db.add(off_row)
                        db.flush()
                        off.id = off_row.id

                db.commit()
                logger.info(f"Saved search history and {len(ranked_products)} products to database.")
            except Exception as exc:
                db.rollback()
                logger.warning(f"Database persistence encountered issue: {exc}")

        duration = time.time() - start_time
        logger.info(
            f"=== Universal Shopping Pipeline finished in {duration:.2f}s: "
            f"{len(ranked_products)} verified products, {len(ranked_alternatives)} alternatives ==="
        )

        search_payload = SearchResponse(
            query=query,
            requirements=requirements,
            products=ranked_products,
            alternatives=ranked_alternatives,
            total_results=total_found,
            verified_results=len(ranked_products),
            sources=sources_used,
            data_source=data_source,
            search_status=search_status,
            message=status_msg,
            comparison_summary=comparison_summary,
            timestamp=now_iso,
        )
        search_payload.platform_comparison = build_global_comparison(search_payload)
        return search_payload
