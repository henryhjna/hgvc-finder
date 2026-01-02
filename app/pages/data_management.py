"""
데이터 관리 페이지
스크래핑 실행, MF 데이터 업로드, DB 상태 확인
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.database import (
    get_session, get_all_listings, get_all_mf_references,
    upsert_listing, add_mf_reference, clear_mf_references,
    get_recent_scrape_logs, create_scrape_log, complete_scrape_log,
    Listing, MFReference
)
from utils.matching import normalize_resort_name
from scrapers.tug_scraper import TUGScraper
from scrapers.redweek_scraper import RedWeekScraper
from scrapers.smtsn_scraper import SMTSNScraper
from config import UI_TEXT


# 각 스크래핑 소스 정보
SCRAPER_INFO = {
    'tug': {
        'name': 'TUG Marketplace',
        'url': 'tug2.com/timesharemarketplace',
        'rating': '⭐⭐ 2.4/5',
        'pros': [
            '무료 리스팅 검색',
            'HGVC 매물 많음',
            '포럼 정보 풍부',
        ],
        'cons': [
            '데이터 검증 없음 - 판매자가 아무거나 입력 가능',
            '사기 리스팅 신고해도 방치됨',
            'MF 정보 부정확한 경우 많음',
        ],
        'warning': '⚠️ 판매자 입력 데이터를 그대로 표시하므로 실제 매물과 다를 수 있음. 반드시 직접 확인 필요!',
    },
    'redweek': {
        'name': 'RedWeek',
        'url': 'redweek.com',
        'rating': '⭐⭐⭐⭐ 4.2/5',
        'pros': [
            'BBB A+ 등급, 20년 운영',
            '300만+ 사용자',
            'Verified 배지로 검증된 매물 표시',
            '고객 서비스 응답 빠름',
        ],
        'cons': [
            '유료 멤버십 필요 ($18.99/년)',
            'HGVC 전용이 아님',
        ],
        'warning': '✅ 가장 신뢰할 수 있는 타임쉐어 마켓플레이스. Verified 배지 매물 권장.',
    },
    'smtsn': {
        'name': 'SellMyTimeshareNow',
        'url': 'sellmytimesharenow.com',
        'rating': '⭐⭐⭐ 3.5/5',
        'pros': [
            '2003년부터 운영',
            '일일 방문자 10,000+',
            '구매자에게 좋은 플랫폼',
        ],
        'cons': [
            'BBB 미인증',
            '판매자 리뷰 부정적 (긴 대기 시간)',
            '선불 수수료 요구',
        ],
        'warning': '⚠️ 구매/검색용으로는 OK. 판매자로서는 주의 필요.',
    },
}


def run_scraping(source: str):
    """범용 스크래핑 실행 함수"""
    session = get_session()
    log = create_scrape_log(session, source)

    try:
        # 스크래퍼 선택
        if source == 'tug':
            scraper = TUGScraper()
        elif source == 'redweek':
            scraper = RedWeekScraper()
        elif source == 'smtsn':
            scraper = SMTSNScraper()
        else:
            raise ValueError(f"Unknown source: {source}")

        listings = scraper.scrape_listings()

        new_count = 0
        updated_count = 0

        for listing_data in listings:
            listing, is_new = upsert_listing(session, listing_data)
            if is_new:
                new_count += 1
            else:
                updated_count += 1

        session.commit()
        complete_scrape_log(
            session, log,
            found=len(listings),
            new=new_count,
            updated=updated_count,
            status='completed'
        )

        return {
            'success': True,
            'found': len(listings),
            'new': new_count,
            'updated': updated_count
        }

    except Exception as e:
        session.rollback()
        complete_scrape_log(
            session, log,
            found=0, new=0, updated=0,
            status='failed',
            error=str(e)
        )
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        session.close()


def run_tug_scraping():
    """TUG Marketplace 스크래핑 실행 (하위호환)"""
    return run_scraping('tug')


def import_mf_csv(df: pd.DataFrame) -> dict:
    """MF CSV 데이터 가져오기"""
    session = get_session()
    try:
        # 기존 데이터 삭제
        clear_mf_references(session)

        count = 0
        for _, row in df.iterrows():
            resort_name = row.get('resort_name', '')
            points = row.get('points', 0)
            annual_mf = row.get('annual_mf', 0)

            if not resort_name or not annual_mf:
                continue

            mf_per_point = annual_mf / points if points > 0 else 0

            mf_data = {
                'resort_name': resort_name,
                'resort_name_normalized': normalize_resort_name(resort_name),
                'unit_type': row.get('unit_type', ''),
                'season': row.get('season', 'Platinum'),
                'points': int(points) if points else 0,
                'annual_mf': float(annual_mf),
                'mf_per_point': mf_per_point,
                'year': int(row.get('year', 2025)),
                'source': 'manual',
            }

            add_mf_reference(session, mf_data)
            count += 1

        session.commit()
        return {'success': True, 'count': count}

    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def get_db_stats() -> dict:
    """데이터베이스 통계 조회"""
    session = get_session()
    try:
        listing_count = session.query(Listing).count()
        active_count = session.query(Listing).filter(Listing.is_active == True).count()
        mf_count = session.query(MFReference).count()

        return {
            'listing_count': listing_count,
            'active_count': active_count,
            'mf_count': mf_count,
        }
    finally:
        session.close()


def main():
    st.title("데이터 관리")

    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["스크래핑", "MF 데이터", "DB 상태"])

    # 탭 1: 스크래핑
    with tab1:
        st.subheader("매물 스크래핑")

        # 각 소스별 카드 렌더링
        for source_key in ['tug', 'redweek', 'smtsn']:
            info = SCRAPER_INFO[source_key]

            with st.expander(f"**{info['name']}** - {info['rating']}", expanded=(source_key == 'tug')):
                col_info, col_action = st.columns([3, 1])

                with col_info:
                    st.caption(f"🔗 {info['url']}")

                    # 장단점
                    pros_text = " / ".join([f"✅ {p}" for p in info['pros']])
                    cons_text = " / ".join([f"❌ {c}" for c in info['cons']])

                    st.markdown(f"**장점:** {pros_text}")
                    st.markdown(f"**단점:** {cons_text}")

                    # 주의사항
                    if info['warning'].startswith('⚠️'):
                        st.warning(info['warning'])
                    else:
                        st.success(info['warning'])

                with col_action:
                    if st.button(
                        f"{info['name']} 스크래핑",
                        type="primary" if source_key == 'tug' else "secondary",
                        key=f"scrape_{source_key}",
                        use_container_width=True
                    ):
                        with st.spinner(f"{info['name']} 스크래핑 중... (2-5분 소요)"):
                            result = run_scraping(source_key)

                        if result['success']:
                            st.success(
                                f"완료! 발견: {result['found']}개, "
                                f"신규: {result['new']}개, "
                                f"업데이트: {result['updated']}개"
                            )
                        else:
                            st.error(f"실패: {result.get('error', '알 수 없는 오류')}")

        st.markdown("---")

        # 최근 스크래핑 로그
        st.subheader("최근 스크래핑 기록")
        session = get_session()
        try:
            logs = get_recent_scrape_logs(session, limit=10)
            if logs:
                log_data = []
                for log in logs:
                    log_data.append({
                        '소스': log.source.upper(),
                        '시작시간': log.started_at.strftime('%Y-%m-%d %H:%M') if log.started_at else '',
                        '상태': '완료' if log.status == 'completed' else ('실패' if log.status == 'failed' else '진행중'),
                        '발견': log.listings_found,
                        '신규': log.listings_new,
                        '업데이트': log.listings_updated,
                    })
                st.dataframe(pd.DataFrame(log_data), use_container_width=True)
            else:
                st.info("스크래핑 기록이 없습니다.")
        finally:
            session.close()

    # 탭 2: MF 데이터
    with tab2:
        st.subheader("MF 참조 데이터 관리")

        st.markdown("""
        리조트별 유지비(Maintenance Fee) 데이터를 업로드하세요.

        **CSV 형식:**
        ```
        resort_name,unit_type,season,points,annual_mf,year
        "Elara by Hilton Grand Vacations","2BR Grand","Platinum",13440,1331.68,2025
        ```
        """)

        uploaded_file = st.file_uploader(
            "MF 데이터 CSV 업로드",
            type=['csv'],
            help="resort_name, unit_type, season, points, annual_mf 컬럼이 필요합니다."
        )

        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("미리보기 (처음 10행):")
                st.dataframe(df.head(10))

                required_cols = ['resort_name', 'annual_mf']
                missing = [c for c in required_cols if c not in df.columns]

                if missing:
                    st.error(f"필수 컬럼 누락: {', '.join(missing)}")
                else:
                    if st.button("MF 데이터 가져오기", type="primary"):
                        result = import_mf_csv(df)
                        if result['success']:
                            st.success(f"성공! {result['count']}개 MF 데이터 가져옴")
                        else:
                            st.error(f"실패: {result.get('error')}")

            except Exception as e:
                st.error(f"CSV 파일 읽기 오류: {e}")

        st.markdown("---")

        # 현재 MF 데이터 표시
        st.subheader("현재 MF 데이터")
        session = get_session()
        try:
            refs = get_all_mf_references(session)
            if refs:
                ref_data = []
                for r in refs:
                    ref_data.append({
                        '리조트': r.resort_name,
                        '유닛': r.unit_type or '',
                        '시즌': r.season or '',
                        '포인트': f"{r.points:,}" if r.points else '',
                        '연간MF': f"${r.annual_mf:,.2f}",
                        'MF/pt': f"${r.mf_per_point:.4f}" if r.mf_per_point else '',
                    })
                st.dataframe(pd.DataFrame(ref_data), use_container_width=True)
            else:
                st.info("MF 데이터가 없습니다. CSV를 업로드하세요.")
        finally:
            session.close()

    # 탭 3: DB 상태
    with tab3:
        st.subheader("데이터베이스 상태")

        stats = get_db_stats()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("전체 매물", f"{stats['listing_count']:,}개")

        with col2:
            st.metric("활성 매물", f"{stats['active_count']:,}개")

        with col3:
            st.metric("MF 참조 데이터", f"{stats['mf_count']:,}개")

        st.markdown("---")

        # 소스별 매물 수
        st.subheader("소스별 매물 수")
        session = get_session()
        try:
            from sqlalchemy import func
            source_counts = session.query(
                Listing.source,
                func.count(Listing.id)
            ).group_by(Listing.source).all()

            if source_counts:
                source_data = [{'소스': s.upper(), '매물 수': c} for s, c in source_counts]
                st.dataframe(pd.DataFrame(source_data), use_container_width=True)
            else:
                st.info("매물 데이터가 없습니다.")
        finally:
            session.close()


# 페이지 실행
if __name__ == "__main__":
    main()
else:
    main()
