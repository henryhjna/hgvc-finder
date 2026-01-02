"""
메인 대시보드 페이지
HGVC 매물 목록과 요약 통계 표시
"""
import streamlit as st
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.database import get_session, get_all_listings, get_all_mf_references, Listing, MFReference
from utils.calculator import enrich_listings_dataframe, get_summary_stats
from app.components.filters import render_sidebar_filters, apply_filters, render_sort_selector, apply_sort
from app.components.metrics import render_summary_metrics, render_grade_distribution, render_last_updated
from config import UI_TEXT


def load_listings_df() -> pd.DataFrame:
    """데이터베이스에서 매물 로드"""
    session = get_session()
    try:
        listings = get_all_listings(session, active_only=True)
        if not listings:
            return pd.DataFrame()

        data = []
        for l in listings:
            data.append({
                'id': l.id,
                'source': l.source,
                'source_id': l.source_id,
                'resort_name': l.resort_name,
                'resort_name_normalized': l.resort_name_normalized,
                'unit_type': l.unit_type,
                'season': l.season,
                'points': l.points,
                'usage': l.usage,
                'asking_price': l.asking_price,
                'annual_mf': l.annual_mf,
                'location': l.location,
                'bedrooms': l.bedrooms,
                'listing_url': l.listing_url,
                'scraped_at': l.scraped_at,
            })
        return pd.DataFrame(data)
    finally:
        session.close()


def load_mf_reference_df() -> pd.DataFrame:
    """MF 참조 데이터 로드"""
    session = get_session()
    try:
        refs = get_all_mf_references(session)
        if not refs:
            return pd.DataFrame()

        data = []
        for r in refs:
            data.append({
                'resort_name': r.resort_name,
                'resort_name_normalized': r.resort_name_normalized,
                'unit_type': r.unit_type,
                'season': r.season,
                'points': r.points,
                'annual_mf': r.annual_mf,
            })
        return pd.DataFrame(data)
    finally:
        session.close()


def format_display_df(df: pd.DataFrame) -> pd.DataFrame:
    """표시용 DataFrame 포맷팅"""
    if df.empty:
        return df

    display_cols = {
        'deal_grade_display': '등급',
        'resort_name': '리조트',
        'location': '위치',
        'points': '포인트',
        'usage': '사용주기',
        'asking_price': '가격',
        'annual_mf': '연간MF',
        'mf_per_point': 'MF/pt',
        'total_10yr': '10년비용',
        'source': '출처',
        'listing_url': '링크',
    }

    # 존재하는 컬럼만 선택
    available_cols = [c for c in display_cols.keys() if c in df.columns]
    display_df = df[available_cols].copy()

    # 컬럼명 한국어로 변경
    display_df.columns = [display_cols[c] for c in available_cols]

    # 숫자 포맷팅
    if '가격' in display_df.columns:
        display_df['가격'] = display_df['가격'].apply(
            lambda x: f"${x:,.0f}" if pd.notna(x) else "?"
        )

    if '연간MF' in display_df.columns:
        display_df['연간MF'] = display_df['연간MF'].apply(
            lambda x: f"${x:,.0f}" if pd.notna(x) else "?"
        )

    if 'MF/pt' in display_df.columns:
        display_df['MF/pt'] = display_df['MF/pt'].apply(
            lambda x: f"${x:.4f}" if pd.notna(x) else "?"
        )

    if '10년비용' in display_df.columns:
        display_df['10년비용'] = display_df['10년비용'].apply(
            lambda x: f"${x:,.0f}" if pd.notna(x) else "?"
        )

    if '포인트' in display_df.columns:
        display_df['포인트'] = display_df['포인트'].apply(
            lambda x: f"{int(x):,}" if pd.notna(x) else "?"
        )

    return display_df


def get_grade_emoji(grade: str) -> str:
    """등급에 맞는 이모지 반환"""
    emoji_map = {
        'excellent': '🟢',  # 초록
        'good': '🟡',       # 노랑
        'fair': '🟠',       # 주황
        'poor': '🔴',       # 빨강
        'unknown': '⚪',    # 회색
    }
    return emoji_map.get(grade, '⚪')


def render_listings_table(df: pd.DataFrame, enriched_df: pd.DataFrame):
    """매물 테이블 렌더링"""
    if df.empty:
        st.info(UI_TEXT['no_listings'])
        return

    # 표시용 DataFrame
    display_df = format_display_df(enriched_df)

    # 등급 컬럼에 이모지 추가
    if '등급' in display_df.columns and 'deal_grade' in enriched_df.columns:
        display_df['등급'] = enriched_df.apply(
            lambda row: f"{get_grade_emoji(row['deal_grade'])} {row['deal_grade_display']}",
            axis=1
        )

    # 링크 컬럼은 순수 URL로 설정 (LinkColumn이 처리)
    if '링크' in display_df.columns:
        display_df['링크'] = enriched_df['listing_url']

    # 테이블 표시
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        column_config={
            '링크': st.column_config.LinkColumn(
                '링크',
                display_text='보기',
                help='TUG 매물 페이지로 이동'
            ),
        }
    )


# 페이지 메인 함수
def main():
    st.title("HGVC 딜 대시보드")

    # 사이드바 필터
    filters = render_sidebar_filters()

    # 데이터 로드
    with st.spinner("데이터 로딩 중..."):
        listings_df = load_listings_df()
        mf_ref_df = load_mf_reference_df()

    if listings_df.empty:
        st.warning("매물 데이터가 없습니다. '데이터 관리' 페이지에서 스크래핑을 실행하세요.")

        if st.button("데이터 관리로 이동"):
            st.switch_page("pages/data_management.py")
        return

    # 메트릭 계산
    enriched_df = enrich_listings_dataframe(listings_df, mf_ref_df)

    # 필터 적용
    filtered_df = apply_filters(enriched_df, filters)

    # 요약 통계
    stats = get_summary_stats(filtered_df)

    st.markdown("---")

    # 메트릭 카드
    render_summary_metrics(stats)

    st.markdown("---")

    # 등급 분포
    render_grade_distribution(stats)

    st.markdown("---")

    # 정렬 옵션
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"매물 목록 ({len(filtered_df)}개)")
    with col2:
        sort_option = render_sort_selector()

    # 정렬 적용
    sorted_df = apply_sort(filtered_df, sort_option)

    # 테이블 렌더링
    render_listings_table(sorted_df, sorted_df)

    # 마지막 업데이트 시간
    if not filtered_df.empty and 'scraped_at' in filtered_df.columns:
        last_update = filtered_df['scraped_at'].max()
        render_last_updated(last_update)


# 페이지 실행
if __name__ == "__main__":
    main()
else:
    main()
