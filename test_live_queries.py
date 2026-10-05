import asyncio
import sys
from backend.agent.shopping_pipeline import ShoppingPipeline

sys.stdout.reconfigure(encoding="utf-8")

QUERIES = [
    "Redmi Note 10S",
    "cat logo t-shirt",
    "laptop under 60000 for coding",
    "55 inch 4K TV under 50000",
    "Nike running shoes",
    "wireless headphones",
    "smartwatch",
]


async def run_live_tests():
    pipeline = ShoppingPipeline()
    print("=================== RUNNING LIVE PIPELINE TESTS ===================")

    for q in QUERIES:
        print(f"\n--- Testing Query: '{q}' ---")
        res = await pipeline.run(query=q)
        print(f"Status: {res.search_status} | Data Source: {res.data_source}")
        print(f"Sources Used: {res.sources}")
        print(f"Verified Products: {len(res.products)} | Alternatives: {len(res.alternatives)}")

        if res.comparison_summary:
            print(f"Comparison: Lowest ₹{res.comparison_summary.lowest_price} on {res.comparison_summary.best_price_platform}")
            print(f"Spread: ₹{res.comparison_summary.price_spread} | Rec: {res.comparison_summary.recommendation}")

        for i, p in enumerate(res.products[:2], 1):
            print(f"  [{i}] {p.product_name}")
            print(f"      Price: ₹{p.price} | Source: {p.source} | Status: {p.verification_status}")
            print(f"      Verified URL: {p.url[:80]}...")
            print(f"      Offers: {len(p.offers)} offers across platforms")

    print("\n=================== LIVE TESTS FINISHED SUCCESSFULLY ===================")


if __name__ == "__main__":
    asyncio.run(run_live_tests())
