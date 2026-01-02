"""
Streamlit 사이드바 필터 컴포넌트
"""
import streamlit as st
import pandas as pd
from typing import Dict, List
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    DEFAULT_POINTS_RANGE, DEFAULT_PRICE_RANGE, DEFAULT_MF_PER_POINT_MAX,
    UI_TEXT, LOCATION_KEYWORDS
)


def render_sidebar_filters() -> Dict:
    """
    사이드바 필터 렌더링

    Returns:
        필터 값 딕셔너리
    """
    st.sidebar.header(UI_TEXT['filter_header'])

    filters = {}

    # 시즌 필터
    st.sidebar.subheader("시즌")
    filters['season'] = st.sidebar.radio(
        "시즌 선택",
        options=['Platinum만', '전체'],
        index=0,
        label_visibility="collapsed"
    )

    # 사용 주기 필터
    st.sidebar.subheader("사용 주기")
    filters['usage'] = st.sidebar.radio(
        "사용 주기 선택",
        options=['Annual만', 'EOY 포함', '전체'],
        index=2,
        label_visibility="collapsed"
    )

    # 위치 필터
    st.sidebar.subheader("위치")
    location_options = ['전체'] + list(LOCATION_KEYWORDS.keys()) + ['Other']
    filters['locations'] = st.sidebar.multiselect(
        "위치 선택",
        options=location_options[1:],  # '전체' 제외
        default=[],
        placeholder="선택하세요...",
        label_visibility="collapsed"
    )

    # 포인트 범위
    st.sidebar.subheader("포인트 범위")
    filters['points_range'] = st.sidebar.slider(
        "포인트",
        min_value=0,
        max_value=50000,
        value=DEFAULT_POINTS_RANGE,
        step=1000,
        format="%d pts",
        label_visibility="collapsed"
    )

    # 가격 범위
    st.sidebar.subheader("가격 범위")
    filters['price_range'] = st.sidebar.slider(
        "가격",
        min_value=0,
        max_value=50000,
        value=DEFAULT_PRICE_RANGE,
        step=500,
        format="$%d",
        label_visibility="collapsed"
    )

    # 최대 MF/pt
    st.sidebar.subheader("최대 MF/pt")
    filters['max_mf_per_point'] = st.sidebar.slider(
        "MF per Point",
        min_value=0.05,
        max_value=0.50,
        value=DEFAULT_MF_PER_POINT_MAX,
        step=0.01,
        format="$%.2f",
        label_visibility="collapsed"
    )

    # 데이터 소스
    st.sidebar.subheader("데이터 소스")
    filters['sources'] = {
        'tug': st.sidebar.checkbox("TUG Marketplace", value=True),
        'redweek': st.sidebar.checkbox("RedWeek", value=True),
        'smtsn': st.sidebar.checkbox("SellMyTimeshareNow", value=True),
    }

    return filters


def apply_filters(df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
    """
    필터를 DataFrame에 적용

    Args:
        df: 매물 DataFrame
        filters: 필터 값 딕셔너리

    Returns:
        필터링된 DataFrame
    """
    if df.empty:
        return df

    filtered = df.copy()

    # 시즌 필터
    if filters.get('season') == 'Platinum만':
        if 'season' in filtered.columns:
            filtered = filtered[
                filtered['season'].str.contains('Platinum', case=False, na=False)
            ]

    # 사용 주기 필터
    usage_filter = filters.get('usage', '전체')
    if usage_filter == 'Annual만':
        if 'usage' in filtered.columns:
            filtered = filtered[filtered['usage'] == 'Annual']
    elif usage_filter == 'EOY 포함':
        if 'usage' in filtered.columns:
            filtered = filtered[
                filtered['usage'].isin(['Annual', 'EOY', 'EOY-Even', 'EOY-Odd'])
            ]
    # '전체'면 필터링 없음

    # 위치 필터
    locations = filters.get('locations', [])
    if locations and 'location' in filtered.columns:
        filtered = filtered[filtered['location'].isin(locations)]

    # 포인트 범위 (null 값은 유지 - 정보 없음)
    points_range = filters.get('points_range', DEFAULT_POINTS_RANGE)
    if 'points' in filtered.columns:
        filtered = filtered[
            (filtered['points'].isna()) |
            ((filtered['points'] >= points_range[0]) &
             (filtered['points'] <= points_range[1]))
        ]

    # 가격 범위 (null 값은 유지 - 정보 없음)
    price_range = filters.get('price_range', DEFAULT_PRICE_RANGE)
    if 'asking_price' in filtered.columns:
        filtered = filtered[
            (filtered['asking_price'].isna()) |
            ((filtered['asking_price'] >= price_range[0]) &
             (filtered['asking_price'] <= price_range[1]))
        ]

    # MF/pt 필터
    max_mf = filters.get('max_mf_per_point', DEFAULT_MF_PER_POINT_MAX)
    if 'mf_per_point' in filtered.columns:
        # None 값은 유지 (정보 없음)
        filtered = filtered[
            (filtered['mf_per_point'].isna()) |
            (filtered['mf_per_point'] <= max_mf)
        ]

    # 데이터 소스 필터
    sources = filters.get('sources', {})
    active_sources = [s for s, enabled in sources.items() if enabled]
    if active_sources and 'source' in filtered.columns:
        filtered = filtered[filtered['source'].isin(active_sources)]

    return filtered


def get_sort_options() -> List[Dict]:
    """정렬 옵션 목록 반환"""
    return [
        {'label': 'MF/pt 오름차순 (추천)', 'column': 'mf_per_point', 'ascending': True},
        {'label': 'MF/pt 내림차순', 'column': 'mf_per_point', 'ascending': False},
        {'label': '가격 오름차순', 'column': 'asking_price', 'ascending': True},
        {'label': '가격 내림차순', 'column': 'asking_price', 'ascending': False},
        {'label': '포인트 오름차순', 'column': 'points', 'ascending': True},
        {'label': '포인트 내림차순', 'column': 'points', 'ascending': False},
        {'label': '10년비용 오름차순', 'column': 'total_10yr', 'ascending': True},
        {'label': '최신순', 'column': 'scraped_at', 'ascending': False},
    ]


def render_sort_selector() -> Dict:
    """
    정렬 옵션 선택기 렌더링

    Returns:
        선택된 정렬 옵션
    """
    options = get_sort_options()
    labels = [opt['label'] for opt in options]

    selected_label = st.selectbox(
        "정렬",
        options=labels,
        index=0
    )

    selected_idx = labels.index(selected_label)
    return options[selected_idx]


def apply_sort(df: pd.DataFrame, sort_option: Dict) -> pd.DataFrame:
    """
    정렬 옵션 적용

    Args:
        df: DataFrame
        sort_option: 정렬 옵션 딕셔너리

    Returns:
        정렬된 DataFrame
    """
    if df.empty:
        return df

    column = sort_option.get('column')
    ascending = sort_option.get('ascending', True)

    if column and column in df.columns:
        # None 값을 뒤로 보내기
        return df.sort_values(
            by=column,
            ascending=ascending,
            na_position='last'
        )

    return df
