from __future__ import annotations
import datetime
import json
import logging
from typing import Optional, List
from google import genai
from google.genai import types
from backend.config import settings
from backend.schemas.review import ReviewItem, ReviewSummary

logger = logging.getLogger("shopping_agent.review_analyzer")


class ReviewAnalyzer:
    """
    Summarizes source-backed product reviews and user sentiments.
    Never invents fake reviews or fabricated quotes.
    Distinguishes AI analysis from source evidence snippets.
    """

    def __init__(self):
        self._client = None
        if settings.GEMINI_API_KEY:
            try:
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.error(f"GenAI init in ReviewAnalyzer failed: {e}")

        self._groq_client = None
        if settings.GROQ_API_KEY:
            try:
                import groq
                self._groq_client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)
            except Exception as e:
                logger.error(f"Groq init in ReviewAnalyzer failed: {e}")

    async def analyze(
        self,
        product_name: str,
        reviews: Optional[List[ReviewItem]] = None,
        product_id: Optional[int] = None,
    ) -> ReviewSummary:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        evidence_texts = [r.text for r in (reviews or []) if r.text]

        # 1. Try Groq if configured
        if self._groq_client and (evidence_texts or len(product_name) > 3):
            try:
                summary = await self._analyze_with_groq(product_name, evidence_texts, product_id, now_iso)
                if summary:
                    return summary
            except Exception as exc:
                logger.warning(f"Groq review analysis failed: {exc}. Trying secondary.")

        # 2. Try Gemini
        if self._client and (evidence_texts or len(product_name) > 3):
            try:
                summary = await self._analyze_with_llm(product_name, evidence_texts, product_id, now_iso)
                if summary:
                    return summary
            except Exception as exc:
                logger.warning(f"LLM review analysis failed: {exc}. Using deterministic summary.")

        # 3. Deterministic summary strictly from available evidence
        return self._generate_deterministic_summary(product_name, evidence_texts, product_id, now_iso)

    def _build_prompt(self, product_name: str, evidence: List[str]) -> str:
        evidence_block = "\n".join(f"- {e}" for e in evidence[:10]) if evidence else "No direct customer quotes provided; summarize verified web consensus."
        return (
            f"You are a factual e-commerce review analysis engine. Analyze the verified feedback for: \"{product_name}\".\n\n"
            f"Verified Review Evidence:\n{evidence_block}\n\n"
            "Return JSON matching ONLY this schema:\n"
            "{\n"
            '  "overall_sentiment": "Positive | Mixed | Negative",\n'
            '  "sentiment_score": 0.85,\n'
            '  "positive_themes": ["theme1", "theme2"],\n'
            '  "negative_themes": ["theme1", "theme2"],\n'
            '  "common_defects": ["defect1"],\n'
            '  "value_for_money": "summary of price vs performance or null",\n'
            '  "delivery_issues": "delivery feedback or null"\n'
            "}\n"
            "DO NOT fabricate fake buyer quotes. Stick strictly to truthful product consensus."
        )

    def _parse_json_to_summary(
        self,
        product_name: str,
        evidence: List[str],
        product_id: Optional[int],
        timestamp: str,
        data: dict,
    ) -> ReviewSummary:
        sentiment_score = None
        if data.get("sentiment_score") is not None:
            try:
                sentiment_score = float(data["sentiment_score"])
            except Exception:
                sentiment_score = None

        return ReviewSummary(
            product_id=product_id,
            product_name=product_name,
            overall_sentiment=data.get("overall_sentiment", "Positive"),
            sentiment_score=sentiment_score,
            positive_themes=data.get("positive_themes") or [],
            negative_themes=data.get("negative_themes") or [],
            common_defects=data.get("common_defects") or [],
            value_for_money=data.get("value_for_money"),
            delivery_issues=data.get("delivery_issues"),
            reviews_analyzed_count=len(evidence),
            evidence_snippets=evidence[:3],
            generated_at=timestamp,
        )

    async def _analyze_with_groq(
        self,
        product_name: str,
        evidence: List[str],
        product_id: Optional[int],
        timestamp: str,
    ) -> Optional[ReviewSummary]:
        prompt = self._build_prompt(product_name, evidence)
        response = await self._groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a factual e-commerce review analysis engine. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content.strip())
        return self._parse_json_to_summary(product_name, evidence, product_id, timestamp, data)

    async def _analyze_with_llm(
        self,
        product_name: str,
        evidence: List[str],
        product_id: Optional[int],
        timestamp: str,
    ) -> Optional[ReviewSummary]:
        prompt = self._build_prompt(product_name, evidence)
        response = self._client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text.strip())
        return self._parse_json_to_summary(product_name, evidence, product_id, timestamp, data)

    def _generate_deterministic_summary(
        self,
        product_name: str,
        evidence: List[str],
        product_id: Optional[int],
        timestamp: str,
    ) -> ReviewSummary:
        if not evidence:
            return ReviewSummary(
                product_id=product_id,
                product_name=product_name,
                overall_sentiment="No verified reviews available",
                sentiment_score=None,
                positive_themes=[],
                negative_themes=[],
                common_defects=[],
                value_for_money=None,
                delivery_issues=None,
                reviews_analyzed_count=0,
                evidence_snippets=[],
                generated_at=timestamp,
            )

        # Basic sentiment extraction strictly from real evidence snippets
        lower_evidence = " ".join(evidence).lower()
        pos_words = ["good", "great", "excellent", "fast", "durable", "clear", "quality", "love", "recommend"]
        neg_words = ["bad", "poor", "slow", "broken", "defective", "worst", "heating", "lag", "cheap", "delay"]

        pos_count = sum(1 for w in pos_words if w in lower_evidence)
        neg_count = sum(1 for w in neg_words if w in lower_evidence)

        if pos_count > neg_count:
            sentiment = "Positive"
            score = 0.80
        elif neg_count > pos_count:
            sentiment = "Negative"
            score = 0.35
        else:
            sentiment = "Mixed"
            score = 0.50

        pos_themes = [f"Mentioned in buyer feedback: '{e[:60]}...'" for e in evidence if any(w in e.lower() for w in pos_words)][:3]
        neg_themes = [f"Criticism in buyer feedback: '{e[:60]}...'" for e in evidence if any(w in e.lower() for w in neg_words)][:3]

        return ReviewSummary(
            product_id=product_id,
            product_name=product_name,
            overall_sentiment=sentiment,
            sentiment_score=score,
            positive_themes=pos_themes,
            negative_themes=neg_themes,
            common_defects=[],
            value_for_money=None,
            delivery_issues=None,
            reviews_analyzed_count=len(evidence),
            evidence_snippets=evidence[:3],
            generated_at=timestamp,
        )
