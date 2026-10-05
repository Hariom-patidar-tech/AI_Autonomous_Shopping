from __future__ import annotations
import datetime
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Numeric,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship
from backend.database import Base

PK_TYPE = Integer().with_variant(BigInteger, "postgresql")


class User(Base):
    __tablename__ = "users"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True, default="Guest User")
    email = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    searches = relationship("SearchHistory", back_populates="user")
    audit_logs = relationship("AgentAuditLog", back_populates="user")


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    raw_query = Column(Text, nullable=False)
    constraints_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    user = relationship("User", back_populates="searches")
    products = relationship("ProductRow", back_populates="search")


class ProductRow(Base):
    __tablename__ = "products"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    search_id = Column(BigInteger, ForeignKey("search_history.id"), nullable=True)
    product_name = Column(String(500), nullable=False)
    brand = Column(String(200), nullable=True)
    model = Column(String(200), nullable=True)
    price = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(10), default="INR")
    rating = Column(Numeric(3, 2), nullable=True)
    review_count = Column(BigInteger, nullable=True)
    seller = Column(String(255), nullable=True)
    availability = Column(Boolean, nullable=True)
    delivery = Column(String(255), nullable=True)
    return_policy = Column(String(255), nullable=True)
    specifications = Column(JSON, nullable=True)
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    source = Column(String(100), nullable=False)
    verification_status = Column(String(50), default="verified")
    observed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    last_verified_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    retrieved_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    search = relationship("SearchHistory", back_populates="products")
    offers = relationship("ProductOfferRow", back_populates="product", cascade="all, delete-orphan")
    review_summaries = relationship("ReviewSummaryRow", back_populates="product", cascade="all, delete-orphan")


class ProductOfferRow(Base):
    __tablename__ = "product_offers"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, ForeignKey("products.id"), nullable=False)
    platform = Column(String(100), nullable=False)
    seller = Column(String(255), nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="INR")
    availability = Column(Boolean, default=True)
    delivery = Column(String(255), nullable=True)
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    observed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    verification_status = Column(String(50), default="verified")

    product = relationship("ProductRow", back_populates="offers")


class ReviewSummaryRow(Base):
    __tablename__ = "reviews_summary"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, ForeignKey("products.id"), nullable=False)
    sentiment_score = Column(Numeric(3, 2), nullable=True)
    overall_sentiment = Column(String(50), nullable=True)
    positive_themes = Column(JSON, nullable=True)
    negative_themes = Column(JSON, nullable=True)
    defects = Column(JSON, nullable=True)
    value_for_money = Column(String(255), nullable=True)
    delivery_issues = Column(String(255), nullable=True)
    generated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    product = relationship("ProductRow", back_populates="review_summaries")


class AgentAuditLog(Base):
    __tablename__ = "agent_audit_log"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    user = relationship("User", back_populates="audit_logs")


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"

    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    product_id = Column(BigInteger, ForeignKey("products.id"), nullable=True)
    state = Column(String(50), default="PENDING_USER_APPROVAL")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
