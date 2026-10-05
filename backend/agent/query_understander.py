from __future__ import annotations
import re
import json
import logging
from typing import Optional, List
from google import genai
from google.genai import types
from backend.config import settings
from backend.schemas.query import ShoppingRequirements

logger = logging.getLogger("shopping_agent.query_understander")

# Hindi / Hinglish translation keywords
HINGLISH_BUDGET_REGEX = r"(?:ke andar|under|tak|me|mein|below|less than)\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:k|lakh)?)"
HINDI_KEYWORDS = ["chahiye", "kaha", "sasta", "milega", "batao", "wali", "wala", "kharidna", "dikhaye", "accha", "badhiya"]


class QueryUnderstander:
    """
    Extracts structured requirements from natural language queries in English and Hindi/Hinglish.
    Combines LLM intelligence with deterministic NLP parsing fallback.
    """

    def __init__(self):
        self._client = None
        if settings.GEMINI_API_KEY:
            try:
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.error(f"Failed to init GenAI client in QueryUnderstander: {e}")

        self._groq_client = None
        if settings.GROQ_API_KEY:
            try:
                import groq
                self._groq_client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)
            except Exception as e:
                logger.error(f"Failed to init Groq client in QueryUnderstander: {e}")

    _quota_exhausted: bool = False
    _groq_exhausted: bool = False

    async def understand(self, query: str) -> ShoppingRequirements:
        """Parse natural language into ShoppingRequirements."""
        cleaned_query = query.strip()
        is_hindi = self._detect_hindi(cleaned_query)

        # 1. Try Groq LLM extraction (fast & dedicated for structured extraction)
        if self._groq_client and not QueryUnderstander._groq_exhausted:
            try:
                groq_reqs = await self._extract_with_groq(cleaned_query, is_hindi)
                if groq_reqs:
                    return groq_reqs
            except Exception as e:
                logger.warning(f"Groq query understanding failed: {e}. Trying secondary LLM.")
                if "429" in str(e) or "quota" in str(e).lower():
                    QueryUnderstander._groq_exhausted = True

        # 2. Try Gemini LLM extraction for deep semantic understanding
        if self._client and not QueryUnderstander._quota_exhausted:
            try:
                llm_requirements = await self._extract_with_llm(cleaned_query, is_hindi)
                if llm_requirements:
                    return llm_requirements
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
                    QueryUnderstander._quota_exhausted = True
                    logger.warning("QueryUnderstander quota exhausted (429). Using deterministic parser.")
                else:
                    logger.warning(f"LLM query understanding failed: {e}. Using deterministic parser.")

        # 3. Fallback to deterministic NLP parser
        return self._extract_deterministic(cleaned_query, is_hindi)

    def _detect_hindi(self, text: str) -> bool:
        lower = text.lower()
        return any(hk in lower for hk in HINDI_KEYWORDS) or bool(re.search(r"[\u0900-\u097F]", text))

    def _build_prompt(self, query: str) -> str:
        return (
            "You are an expert e-commerce query understanding engine. Analyze the user shopping query (which may be in English, Hindi, or Hinglish) "
            "and extract structured shopping requirements in valid JSON.\n\n"
            f"User Query: \"{query}\"\n\n"
            "Return JSON with ONLY these fields:\n"
            "{\n"
            '  "category": "laptop | smartphone | clothing | television | headphones | shoes | general",\n'
            '  "product_type": "specific product type or null",\n'
            '  "brand": "extracted brand name or null",\n'
            '  "model": "extracted specific model or null",\n'
            '  "budget_min": numeric or null,\n'
            '  "budget_max": numeric or null,\n'
            '  "currency": "INR",\n'
            '  "min_rating": numeric rating (e.g. 4.0) or null,\n'
            '  "intent": "exact_product_search | product_search | comparison | cheapest_search",\n'
            '  "use_case": "extracted use case like coding, gaming, running or null",\n'
            '  "keywords": ["keyword1", "keyword2"],\n'
            '  "required_attributes": ["attribute1"],\n'
            '  "preferred_attributes": ["attribute1"]\n'
            "}\n"
            "DO NOT add any markdown formatting other than pure JSON."
        )

    def _parse_json_to_requirements(self, query: str, text: str, is_hindi: bool) -> ShoppingRequirements:
        data = json.loads(text)
        b_max = data.get("budget_max")
        if b_max is not None:
            try:
                b_max = float(b_max)
            except Exception:
                b_max = None

        return ShoppingRequirements(
            raw_query=query,
            category=data.get("category"),
            product_type=data.get("product_type"),
            brand=data.get("brand"),
            model=data.get("model"),
            budget_min=float(data["budget_min"]) if data.get("budget_min") is not None else None,
            budget_max=b_max,
            currency="INR",
            min_rating=float(data["min_rating"]) if data.get("min_rating") is not None else None,
            intent=data.get("intent", "product_search"),
            use_case=data.get("use_case"),
            keywords=data.get("keywords") or [],
            required_attributes=data.get("required_attributes") or [],
            preferred_attributes=data.get("preferred_attributes") or [],
            is_hindi_hinglish=is_hindi,
        )

    async def _extract_with_groq(self, query: str, is_hindi: bool) -> Optional[ShoppingRequirements]:
        prompt = self._build_prompt(query)
        response = await self._groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert e-commerce query understanding engine. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content.strip()
        return self._parse_json_to_requirements(query, text, is_hindi)

    async def _extract_with_llm(self, query: str, is_hindi: bool) -> Optional[ShoppingRequirements]:
        prompt = self._build_prompt(query)

        response = self._client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )

        text = response.text.strip()
        return self._parse_json_to_requirements(query, text, is_hindi)

    def _extract_deterministic(self, query: str, is_hindi: bool) -> ShoppingRequirements:
        """Deterministic regex-based fallback extractor for English & Hinglish."""
        lower = query.lower()

        # 1. Budget extraction (handles "50000 ke andar" and "under 50000")
        budget_max = None
        # Pattern A: Number before phrase (e.g. "50000 ke andar", "60k tak")
        currency_prefix = r"(?:₹|Rs\.?|INR|US\$|USD|\$|GBP|£|EUR|€|CAD|AUD|JPY|¥)?"
        currency_suffix = r"(?:rs\.?|inr|rupees?|usd|gbp|eur|cad|aud|jpy)?"
        b_before = re.search(r"\b([\d,]+)\s*(k|lakh)?\s*" + currency_suffix + r"\s*(?:ke\s*andar|tak|se\s*kam|ke\s*niche)\b", lower)
        # Pattern B: Number after phrase (e.g. "under 50000", "below 60k", "ke andar 50000")
        b_after = re.search(r"(?:under|below|less than|within|ke\s*andar|tak|me|mein)\s*" + currency_prefix + r"\s*([\d,]+)\s*(k|lakh)?\s*" + currency_suffix + r"\b", lower)

        target_match = b_before or b_after
        if target_match:
            val_str = target_match.group(1).replace(",", "")
            multiplier = target_match.group(2)
            try:
                val = float(val_str)
                if multiplier == "k":
                    val *= 1000
                elif multiplier == "lakh":
                    val *= 100000
                # Filter out screen sizes like 55 inch if wrongly captured
                if val > 100:
                    budget_max = val
            except ValueError:
                pass

        # 2. Category & Product Type
        category = None
        product_type = None
        if any(w in lower for w in ["laptop", "notebook", "macbook"]):
            category = "laptop"
            product_type = "laptop"
        elif any(w in lower for w in ["phone", "smartphone", "iphone", "redmi", "galaxy", "pixel", "mobile"]):
            category = "smartphone"
            product_type = "smartphone"
        elif any(w in lower for w in ["tv", "television", "4k tv", "smart tv"]):
            category = "television"
            product_type = "television"
        elif any(w in lower for w in ["t-shirt", "tshirt", "shirt", "hoodie", "jeans", "clothing"]):
            category = "clothing"
            product_type = "t-shirt" if "shirt" in lower else "clothing"
        elif any(w in lower for w in ["shoes", "sneakers", "running shoes"]):
            category = "shoes"
            product_type = "shoes"
        elif any(w in lower for w in ["headphones", "earphones", "earbuds", "airpods"]):
            category = "headphones"
            product_type = "headphones"

        # 3. Brand & Model detection
        brand = None
        model = None
        for b in ["Apple", "Samsung", "Xiaomi", "Redmi", "Nike", "Adidas", "Puma", "Boat", "Sony", "HP", "Dell", "Lenovo", "Asus"]:
            if re.search(rf"\b{b}\b", query, re.IGNORECASE):
                brand = b
                break

        # Check for model patterns like "Note 10S", "iPhone 17 Pro", "S26"
        model_match = re.search(r"\b(Note\s*\d+[A-Za-z]?|iPhone\s*\d+\s*(?:Pro|Max|Plus)?|Galaxy\s*S\d+|17\s*Pro)\b", query, re.IGNORECASE)
        if model_match:
            model = model_match.group(1).strip()

        # 4. Intent
        intent = "product_search"
        if model or (brand and ("note" in lower or "pro" in lower)):
            intent = "exact_product_search"
        elif any(w in lower for w in ["sasta", "cheapest", "lowest price", "compare", "kaha"]):
            intent = "cheapest_search"

        # 5. Rating
        min_rating = None
        rating_match = re.search(r"(\d(?:\.\d)?)\s*(?:stars?|rating|\+ stars?)", lower)
        if rating_match:
            try:
                min_rating = float(rating_match.group(1))
            except ValueError:
                pass

        # 6. Keywords
        words = re.findall(r"\b[A-Za-z0-9]+\b", lower)
        stop_words = {"i", "want", "need", "show", "find", "me", "a", "under", "below", "less", "than", "within", "for", "with", "good", "best", "price", "buy", "online", "shop", "shopping", "rs", "inr", "rupee", "rupees", "ke", "andar", "chahiye", "kaha", "sasta", "milega", "wali", "wala", "the", "in", "and"}
        keywords = [
            w for w in words
            if w not in stop_words
            and not w.isdigit()
            and not re.fullmatch(r"\d+(?:rs|inr|rupees?)", w)
        ]

        use_case = None
        if "coding" in lower:
            use_case = "coding"
        elif "gaming" in lower:
            use_case = "gaming"
        elif "running" in lower:
            use_case = "running"

        return ShoppingRequirements(
            raw_query=query,
            category=category,
            product_type=product_type,
            brand=brand,
            model=model,
            budget_max=budget_max,
            currency=self._detect_currency(lower),
            min_rating=min_rating,
            intent=intent,
            use_case=use_case,
            keywords=keywords,
            is_hindi_hinglish=is_hindi,
        )

    @staticmethod
    def _detect_currency(query: str) -> str:
        upper = query.upper()
        if any(token in upper for token in ("USD", "US$", "$")):
            return "USD"
        if "GBP" in upper or "£" in query:
            return "GBP"
        if "EUR" in upper or "€" in query:
            return "EUR"
        if "CAD" in upper:
            return "CAD"
        if "AUD" in upper:
            return "AUD"
        if "JPY" in upper or "¥" in query:
            return "JPY"
        return "INR"
