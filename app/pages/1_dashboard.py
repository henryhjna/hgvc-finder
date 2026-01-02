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


def render_user_guide():
    """사용자 가이드 정보 표시"""
    st.markdown("---")

    st.subheader("HGVC 리셀 매물 찾기 가이드")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        #### 핵심 지표: MF per Point (MF/pt)

        **MF/pt = 연간 관리비 / 포인트**

        이 수치가 낮을수록 효율적인 매물입니다.

        | 등급 | MF/pt | 평가 |
        |------|-------|------|
        | 🟢 최고 | $0.10 이하 | 매우 희귀, 즉시 검토 |
        | 🟡 좋음 | $0.10-0.15 | 괜찮은 딜 |
        | 🟠 보통 | $0.15-0.20 | 시장 평균 |
        | 🔴 비추천 | $0.20 이상 | 비효율적 |
        """)

    with col2:
        st.markdown("""
        #### 추천 검색 조건

        **입문자용 (저예산)**
        - 가격: $5,000 이하
        - 포인트: 3,000-5,000
        - 위치: Las Vegas (MF 저렴)

        **가성비 추천**
        - MF/pt: $0.15 이하
        - 사용주기: Annual
        - 위치: Las Vegas, Orlando

        **프리미엄 (하와이)**
        - 포인트: 7,000 이상
        - 위치: Hawaii
        - MF/pt: $0.18 이하면 양호
        """)

    st.markdown("---")

    with st.expander("리조트별 특징 보기"):
        st.markdown("""
        | 위치 | 대표 리조트 | 특징 |
        |------|------------|------|
        | **Las Vegas** | Elara, Boulevard, Flamingo | MF 저렴, 포인트 효율 좋음 |
        | **Orlando** | Parc Soleil, SeaWorld | 가족 여행에 적합, 중간 MF |
        | **Hawaii** | Ocean Tower, Kings Land | 인기 높음, MF 비쌈 |
        | **New York** | Hilton Club NYC | 도심, 높은 MF |
        | **Myrtle Beach** | Ocean 22 | 해변, 저렴한 편 |
        """)

    with st.expander("10년 총비용 계산법"):
        st.markdown("""
        **Annual (매년 사용)**
        ```
        10년 비용 = 매물가격 + 클로징비용($1,100) + (연간MF × 10년)
        ```

        **EOY (격년 사용)**
        ```
        10년 비용 = 매물가격 + 클로징비용($1,100) + (연간MF × 5년) + (클럽회비 $209 × 10년)
        ```

        *EOY는 포인트를 2년에 한 번 받으므로 연환산 시 포인트÷2로 계산*
        """)

    with st.expander("주의사항"):
        st.markdown("""
        - **MF 정보 확인 필수**: 매물 페이지의 MF가 오래된 정보일 수 있음
        - **포인트 확인**: 일부 매물은 포인트 정보가 누락됨 (? 표시)
        - **직접 확인**: 구매 전 반드시 판매자에게 최신 MF 확인
        - **클로징 비용**: 별도 $800-1,500 예상
        - **ROFR**: Hilton이 먼저 구매할 권리 있음 (2-4주 소요)
        """)


def render_market_summary(stats: dict, df: pd.DataFrame):
    """현재 시장 현황 요약"""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 현재 매물 현황")

        # 위치별 분포
        if 'location' in df.columns:
            location_counts = df['location'].value_counts().head(5)
            st.markdown("**위치별 매물 수**")
            for loc, count in location_counts.items():
                st.markdown(f"- {loc}: {count}개")

        # 가격대 분포
        if 'asking_price' in df.columns:
            price_df = df[df['asking_price'].notna()]
            if not price_df.empty:
                st.markdown(f"""
                **가격 범위**
                - 최저: ${price_df['asking_price'].min():,.0f}
                - 최고: ${price_df['asking_price'].max():,.0f}
                - 평균: ${price_df['asking_price'].mean():,.0f}
                """)

    with col2:
        st.markdown("#### 오늘의 추천 기준")

        avg_mf = stats.get('avg_mf_per_point')
        if avg_mf:
            st.markdown(f"""
            현재 평균 MF/pt: **${avg_mf:.3f}**

            **추천 필터 설정:**
            - MF/pt $0.15 이하로 필터링
            - 🟢🟡 등급 위주로 검토
            - Annual 사용주기 우선

            **좋은 딜 조건:**
            - MF/pt가 평균(${avg_mf:.3f})보다 낮음
            - 포인트 정보가 명확함 (?가 아님)
            - 10년 비용 대비 효율적
            """)
        else:
            st.markdown("""
            **추천 필터 설정:**
            - MF/pt $0.15 이하로 필터링
            - 🟢🟡 등급 위주로 검토
            - Annual 사용주기 우선
            """)


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
        # 데이터 없을 때 가이드 표시
        st.warning("매물 데이터가 없습니다. '데이터 관리' 페이지에서 스크래핑을 실행하세요.")

        render_user_guide()

        if st.button("데이터 관리로 이동"):
            st.switch_page("pages/data_management.py")
        return

    # 메트릭 계산
    enriched_df = enrich_listings_dataframe(listings_df, mf_ref_df)

    # 필터 적용
    filtered_df = apply_filters(enriched_df, filters)

    # 요약 통계
    stats = get_summary_stats(filtered_df)

    # 현황 요약
    with st.expander("현재 시장 현황 및 검색 가이드", expanded=False):
        render_market_summary(stats, filtered_df)

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
