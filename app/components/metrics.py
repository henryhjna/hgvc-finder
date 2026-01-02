"""
요약 통계 메트릭 컴포넌트
"""
import streamlit as st
from typing import Dict, Optional
import pandas as pd


def render_summary_metrics(stats: Dict):
    """
    요약 통계 메트릭 카드 렌더링

    Args:
        stats: 통계 딕셔너리 (get_summary_stats()에서 반환)
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="총 매물",
            value=f"{stats.get('total_count', 0):,}개"
        )

    with col2:
        avg_mf = stats.get('avg_mf_per_point')
        st.metric(
            label="평균 MF/pt",
            value=f"${avg_mf:.3f}" if avg_mf else "N/A"
        )

    with col3:
        min_mf = stats.get('min_mf_per_point')
        best_resort = stats.get('best_deal_resort', '')
        # 리조트명이 너무 길면 자르기
        if best_resort and len(best_resort) > 20:
            best_resort = best_resort[:17] + "..."
        st.metric(
            label="최저 MF/pt",
            value=f"${min_mf:.3f}" if min_mf else "N/A",
            help=best_resort if best_resort else None
        )

    with col4:
        excellent = stats.get('excellent_count', 0)
        st.metric(
            label="★★★ 최고 등급",
            value=f"{excellent}개"
        )


def render_grade_distribution(stats: Dict):
    """
    등급 분포 표시

    Args:
        stats: 통계 딕셔너리
    """
    st.markdown("##### 등급 분포")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"<div style='background-color:#d4edda;padding:10px;border-radius:5px;text-align:center;'>"
            f"<b>★★★ 최고</b><br>{stats.get('excellent_count', 0)}개</div>",
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f"<div style='background-color:#fff3cd;padding:10px;border-radius:5px;text-align:center;'>"
            f"<b>★★☆ 좋음</b><br>{stats.get('good_count', 0)}개</div>",
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            f"<div style='background-color:#ffe5d0;padding:10px;border-radius:5px;text-align:center;'>"
            f"<b>★☆☆ 보통</b><br>{stats.get('fair_count', 0)}개</div>",
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            f"<div style='background-color:#f8d7da;padding:10px;border-radius:5px;text-align:center;'>"
            f"<b>☆☆☆ 비추천</b><br>{stats.get('poor_count', 0)}개</div>",
            unsafe_allow_html=True
        )


def render_last_updated(timestamp):
    """
    마지막 업데이트 시간 표시

    Args:
        timestamp: datetime 또는 문자열
    """
    if timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%Y-%m-%d %H:%M')
        else:
            time_str = str(timestamp)
        st.caption(f"마지막 업데이트: {time_str}")
    else:
        st.caption("마지막 업데이트: 정보 없음")
