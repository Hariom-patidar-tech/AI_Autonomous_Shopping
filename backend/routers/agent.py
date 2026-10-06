from __future__ import annotations
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.agent.shopping_pipeline import ShoppingPipeline
from backend.agent.cart_service import CartService
from backend.agent.review_analyzer import ReviewAnalyzer
from backend.schemas.cart import AddToCartRequest

router = APIRouter(prefix="/api/agent", tags=["Agent"])
pipeline = ShoppingPipeline()
analyzer = ReviewAnalyzer()


class AgentRunRequest(BaseModel):
    command: str
    user_id: Optional[int] = 1
    parameters: Optional[Dict[str, Any]] = None


class AgentRunResponse(BaseModel):
    action_taken: str
    message: str
    data: Dict[str, Any]


@router.post("/run", response_model=AgentRunResponse)
async def run_agent_workflow(
    req: AgentRunRequest,
    db: Session = Depends(get_db),
):
    """
    Unified Agent execution endpoint for conversational natural language interactions.
    Handles product search, reviews, or cart routing.
    """
    cmd = req.command.strip()
    cmd_lower = cmd.lower()

    # 1. Check if command is review analysis
    if "review" in cmd_lower or "reviews" in cmd_lower:
        summary = await analyzer.analyze(product_name=cmd)
        return AgentRunResponse(
            action_taken="review_analysis",
            message=f"Analyzed customer feedback for: {summary.product_name}",
            data=summary.model_dump(),
        )

    # 2. Check if command is add-to-cart
    if "add to cart" in cmd_lower:
        params = req.parameters or {}
        cart_req = AddToCartRequest(
            product_name=params.get("product_name", cmd),
            platform=params.get("platform", "Verified Store"),
            product_url=params.get("product_url", "https://amazon.in"),
            user_id=req.user_id,
        )
        cart_res = await CartService.add_to_cart(cart_req, db=db)
        return AgentRunResponse(
            action_taken="cart_addition",
            message=cart_res.message,
            data=cart_res.model_dump(),
        )

    # 3. Default: Execute universal shopping search
    search_res = await pipeline.run(
        query=cmd,
        user_id=req.user_id,
        db=db,
    )
    logger.info("Final normalized JSON response: %s", search_res.model_dump_json())
    return AgentRunResponse(
        action_taken="product_search",
        message=f"Found {search_res.total_results} matching products from {len(search_res.sources)} live web sources.",
        data=search_res.model_dump(),
    )
