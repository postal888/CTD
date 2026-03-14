from sqlalchemy import Column, Integer, String, Float, Text, Numeric
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

from app.config import settings

Base = declarative_base()


class Fund(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sno = Column(Integer, index=True)
    investor_name = Column(String(500), nullable=False, index=True)
    domain_name = Column(String(500))
    overview = Column(Text)
    founded_year = Column(String(20))
    country = Column(String(500), index=True)
    state = Column(String(500))
    city = Column(String(500))
    description = Column(Text)
    investor_type = Column(String(200))
    practice_areas = Column(String(500))
    feed_name = Column(String(500))
    business_models = Column(String(1000))
    investment_score = Column(Float)
    website = Column(String(1000))
    linkedin = Column(String(1000))
    twitter = Column(String(1000))

    # Hard filters: stage + check size (logical filter first, then semantic ranking)
    stage = Column(ARRAY(Text), index=True)  # e.g. ["pre-seed", "seed", "series-a"]
    check_min_usd = Column(Numeric(14, 2), nullable=True)  # min check size in USD
    check_max_usd = Column(Numeric(14, 2), nullable=True)  # max check size in USD
    # Display field: original check_size string from JSONL (for UI)
    check_size_text = Column(Text, nullable=True)

    # Vector embedding of the concatenated text
    embedding = Column(Vector(settings.embedding_dim))

    def to_dict(self):
        return {
            "id": self.id,
            "investor_name": self.investor_name,
            "domain_name": self.domain_name,
            "overview": self.overview,
            "founded_year": self.founded_year,
            "country": self.country,
            "state": self.state,
            "city": self.city,
            "description": self.description,
            "investor_type": self.investor_type,
            "practice_areas": self.practice_areas,
            "feed_name": self.feed_name,
            "business_models": self.business_models,
            "investment_score": self.investment_score,
            "website": self.website,
            "linkedin": self.linkedin,
            "twitter": self.twitter,
        }
