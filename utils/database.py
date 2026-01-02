"""
데이터베이스 모델 및 헬퍼 함수
"""
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, DATA_DIR

Base = declarative_base()


class Listing(Base):
    """매물 정보 모델"""
    __tablename__ = 'listings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)  # 'tug', 'redweek', 'smtsn'
    source_id = Column(String(100), unique=True, nullable=False)  # 외부 매물 ID
    resort_name = Column(String(200))
    resort_name_normalized = Column(String(200))  # 매칭용 정규화된 이름
    unit_type = Column(String(50))  # '1BR', '2BR', 'Studio' 등
    season = Column(String(50))  # 'Platinum', 'Gold', 'Silver', 'Bronze'
    week = Column(String(20))  # 주 번호 (해당시)
    points = Column(Integer)
    usage = Column(String(20))  # 'Annual', 'EOY-Even', 'EOY-Odd'
    asking_price = Column(Float)
    annual_mf = Column(Float, nullable=True)  # 연간 유지비 (매물에서 직접 추출)
    location = Column(String(100))
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Float, nullable=True)
    listing_url = Column(String(500))
    listing_date = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Listing {self.source_id}: {self.resort_name} - ${self.asking_price}>"


class MFReference(Base):
    """리조트별 MF 참조 데이터"""
    __tablename__ = 'mf_reference'

    id = Column(Integer, primary_key=True, autoincrement=True)
    resort_name = Column(String(200), nullable=False)
    resort_name_normalized = Column(String(200))
    unit_type = Column(String(50))  # '1BR', '2BR', 'Studio' 등
    season = Column(String(50))  # 'Platinum', 'Gold' 등
    points = Column(Integer)
    annual_mf = Column(Float, nullable=False)
    mf_per_point = Column(Float)  # 미리 계산된 MF/pt
    year = Column(Integer, default=2025)
    source = Column(String(100))  # 'manual', 'tug_forum'
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MFReference {self.resort_name} {self.unit_type}: ${self.annual_mf}>"


class ScrapeLog(Base):
    """스크래핑 로그"""
    __tablename__ = 'scrape_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    listings_found = Column(Integer, default=0)
    listings_new = Column(Integer, default=0)
    listings_updated = Column(Integer, default=0)
    status = Column(String(20), default='running')  # 'running', 'completed', 'failed'
    error_message = Column(String(500), nullable=True)

    def __repr__(self):
        return f"<ScrapeLog {self.source} {self.started_at}: {self.status}>"


# 데이터베이스 엔진 및 세션
_engine = None
_SessionLocal = None


def get_engine():
    """SQLAlchemy 엔진 반환 (싱글톤)"""
    global _engine
    if _engine is None:
        # data 디렉토리 생성
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    return _engine


def get_session() -> Session:
    """새 세션 반환"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_db():
    """데이터베이스 테이블 생성"""
    engine = get_engine()
    Base.metadata.create_all(engine)


def get_all_listings(session: Session, active_only: bool = True) -> List[Listing]:
    """모든 매물 조회"""
    query = session.query(Listing)
    if active_only:
        query = query.filter(Listing.is_active == True)
    return query.order_by(Listing.scraped_at.desc()).all()


def get_listing_by_source_id(session: Session, source_id: str) -> Optional[Listing]:
    """소스 ID로 매물 조회"""
    return session.query(Listing).filter(Listing.source_id == source_id).first()


def upsert_listing(session: Session, listing_data: dict) -> tuple:
    """매물 추가 또는 업데이트. (listing, is_new) 반환"""
    source_id = listing_data.get('source_id')
    existing = get_listing_by_source_id(session, source_id)

    if existing:
        # 업데이트
        for key, value in listing_data.items():
            if hasattr(existing, key) and key != 'id':
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        return existing, False
    else:
        # 새로 추가
        listing = Listing(**listing_data)
        session.add(listing)
        return listing, True


def get_all_mf_references(session: Session) -> List[MFReference]:
    """모든 MF 참조 데이터 조회"""
    return session.query(MFReference).all()


def add_mf_reference(session: Session, mf_data: dict) -> MFReference:
    """MF 참조 데이터 추가"""
    mf_ref = MFReference(**mf_data)
    session.add(mf_ref)
    return mf_ref


def clear_mf_references(session: Session):
    """모든 MF 참조 데이터 삭제"""
    session.query(MFReference).delete()


def get_recent_scrape_logs(session: Session, limit: int = 10) -> List[ScrapeLog]:
    """최근 스크래핑 로그 조회"""
    return session.query(ScrapeLog).order_by(ScrapeLog.started_at.desc()).limit(limit).all()


def create_scrape_log(session: Session, source: str) -> ScrapeLog:
    """스크래핑 로그 생성"""
    log = ScrapeLog(source=source)
    session.add(log)
    session.commit()
    return log


def complete_scrape_log(session: Session, log: ScrapeLog,
                        found: int, new: int, updated: int,
                        status: str = 'completed', error: str = None):
    """스크래핑 로그 완료 처리"""
    log.completed_at = datetime.utcnow()
    log.listings_found = found
    log.listings_new = new
    log.listings_updated = updated
    log.status = status
    log.error_message = error
    session.commit()


# 데이터베이스 초기화 (모듈 로드 시)
init_db()
