"""SQLAlchemy ORM 모델."""

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, Integer, Numeric,
    SmallInteger, String, Text, TIMESTAMP, ARRAY,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID

from app.db import Base


class RegionCode(Base):
    __tablename__ = "region_codes"

    id = Column(Integer, primary_key=True)
    sido_code = Column(String(2), nullable=False)
    sido_name = Column(String(20), nullable=False)
    sigungu_code = Column(String(5), nullable=False)
    sigungu_name = Column(String(30), nullable=False)
    eupmyeondong_code = Column(String(8), nullable=False)
    eupmyeondong_name = Column(String(30), nullable=False)
    beopjungri_code = Column(String(10), nullable=False, unique=True)
    beopjungri_name = Column(String(30), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class LandTransaction(Base):
    __tablename__ = "land_transactions"

    id = Column(BigInteger, primary_key=True)
    transaction_hash = Column(String(64), nullable=False, unique=True)
    contract_year = Column(SmallInteger, nullable=False)
    contract_month = Column(SmallInteger, nullable=False)
    contract_date = Column(Date)
    beopjungri_code = Column(String(10), nullable=False)
    sido_code = Column(String(2), nullable=False)
    sigungu_code = Column(String(5), nullable=False)
    land_category = Column(String(10))
    zone_type = Column(String(20))
    road_condition = Column(String(20))
    area_sqm = Column(Numeric(12, 2))
    area_category = Column(String(10))
    total_price_10k = Column(Numeric(14, 2), nullable=False)
    unit_price_per_sqm = Column(Numeric(14, 2))
    is_partial_ownership = Column(Boolean, nullable=False, default=False)
    is_cancelled = Column(Boolean, nullable=False, default=False)
    is_valid = Column(Boolean, nullable=False, default=True)
    needs_review = Column(Boolean, nullable=False, default=False)
    mapping_notes = Column(String(240))
    updated_at = Column(TIMESTAMP)


class PopulationStat(Base):
    """추후 지도 인구 레이어 (테이블만 준비, MVP에서는 미사용)."""

    __tablename__ = "population_stats"

    id = Column(BigInteger, primary_key=True)
    stats_year = Column(SmallInteger, nullable=False)
    stats_month = Column(SmallInteger)
    admin_code = Column(String(10), nullable=False)
    admin_level = Column(String(20), nullable=False)
    total_population = Column(Integer)
    household_count = Column(Integer)
    pop_change_rate = Column(Numeric(8, 4))
    density_per_km2 = Column(Numeric(14, 4))
    source = Column(String(80))


class LandBasicStats(Base):
    __tablename__ = "land_basic_stats"

    id = Column(BigInteger, primary_key=True)
    beopjungri_code = Column(String(10), nullable=False)
    zone_type = Column(String(20), nullable=False, default="ALL")
    land_category = Column(String(10), nullable=False, default="ALL")
    count = Column(Integer, nullable=False, default=0)
    mean = Column(Numeric(14, 2))
    std = Column(Numeric(14, 2))
    ci_lower = Column(Numeric(14, 2))
    ci_upper = Column(Numeric(14, 2))
    p_min = Column(Numeric(14, 2))
    p25 = Column(Numeric(14, 2))
    median = Column(Numeric(14, 2))
    p75 = Column(Numeric(14, 2))
    p_max = Column(Numeric(14, 2))
    year_from = Column(SmallInteger, nullable=False)
    year_to = Column(SmallInteger, nullable=False)
    computed_at = Column(TIMESTAMP)
