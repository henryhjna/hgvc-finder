"""
분석 페이지
차트 및 시각화
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.database import get_session, get_all_listings, get_all_mf_references
from utils.calculator import enrich_listings_dataframe
from app.components.filters import render_sidebar_filters, apply_filters


def load_data():
    """데이터 로드"""
    session = get_session()
    try:
        listings = get_all_listings(session, active_only=True)
        if not listings:
            return pd.DataFrame(), pd.DataFrame()

        listings_data = []
        for l in listings:
            listings_data.append({
                'id': l.id,
                'resort_name': l.resort_name,
                'resort_name_normalized': l.resort_name_normalized,
                'location': l.location,
                'points': l.points,
                'usage': l.usage,
                'asking_price': l.asking_price,
                'annual_mf': l.annual_mf,
                'season': l.season,
                'scraped_at': l.scraped_at,
            })
        listings_df = pd.DataFrame(listings_data)

        refs = get_all_mf_references(session)
        if refs:
            ref_data = [{
                'resort_name_normalized': r.resort_name_normalized,
                'annual_mf': r.annual_mf,
            } for r in refs]
            ref_df = pd.DataFrame(ref_data)
        else:
            ref_df = pd.DataFrame()

        return listings_df, ref_df
    finally:
        session.close()


def main():
    st.title("분석")

    # 사이드바 필터
    filters = render_sidebar_filters()

    # 데이터 로드
    with st.spinner("데이터 로딩 중..."):
        listings_df, mf_ref_df = load_data()

    if listings_df.empty:
        st.warning("분석할 데이터가 없습니다. '데이터 관리' 페이지에서 스크래핑을 실행하세요.")
        return

    # 메트릭 계산 및 필터 적용
    enriched_df = enrich_listings_dataframe(listings_df, mf_ref_df)
    filtered_df = apply_filters(enriched_df, filters)

    if filtered_df.empty:
        st.warning("필터 조건에 맞는 데이터가 없습니다.")
        return

    st.markdown("---")

    # 1. 리조트별 평균 MF/pt 비교
    st.subheader("리조트별 평균 MF/pt")

    # MF/pt가 있는 데이터만
    mf_data = filtered_df[filtered_df['mf_per_point'].notna()].copy()

    if not mf_data.empty:
        resort_avg = mf_data.groupby('resort_name')['mf_per_point'].mean().sort_values()

        # 상위/하위 15개만 표시
        if len(resort_avg) > 30:
            st.info(f"총 {len(resort_avg)}개 리조트 중 상/하위 15개씩 표시")
            bottom_15 = resort_avg.head(15)
            top_15 = resort_avg.tail(15)
            resort_avg = pd.concat([bottom_15, top_15])

        fig_resort = px.bar(
            x=resort_avg.values,
            y=resort_avg.index,
            orientation='h',
            labels={'x': 'MF/pt ($)', 'y': '리조트'},
            color=resort_avg.values,
            color_continuous_scale=['green', 'yellow', 'orange', 'red'],
        )
        fig_resort.update_layout(
            height=max(400, len(resort_avg) * 25),
            showlegend=False,
            coloraxis_showscale=False
        )
        fig_resort.add_vline(x=0.10, line_dash="dash", line_color="green", annotation_text="최고 $0.10")
        fig_resort.add_vline(x=0.15, line_dash="dash", line_color="orange", annotation_text="좋음 $0.15")

        st.plotly_chart(fig_resort, use_container_width=True)
    else:
        st.info("MF 데이터가 있는 매물이 없습니다.")

    st.markdown("---")

    # 2. 가격 vs MF/pt 산점도
    st.subheader("가격 vs MF/pt")

    scatter_data = filtered_df[
        (filtered_df['mf_per_point'].notna()) &
        (filtered_df['asking_price'].notna())
    ].copy()

    if not scatter_data.empty:
        fig_scatter = px.scatter(
            scatter_data,
            x='asking_price',
            y='mf_per_point',
            color='location',
            size='points',
            hover_data=['resort_name', 'usage', 'points'],
            labels={
                'asking_price': '가격 ($)',
                'mf_per_point': 'MF/pt ($)',
                'location': '위치',
                'points': '포인트'
            }
        )
        fig_scatter.add_hline(y=0.10, line_dash="dash", line_color="green")
        fig_scatter.add_hline(y=0.15, line_dash="dash", line_color="orange")
        fig_scatter.add_hline(y=0.20, line_dash="dash", line_color="red")

        fig_scatter.update_layout(height=500)
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("산점도를 그릴 데이터가 부족합니다.")

    st.markdown("---")

    # 3. 위치별 분포
    st.subheader("위치별 매물 분포")

    location_counts = filtered_df['location'].value_counts()

    col1, col2 = st.columns(2)

    with col1:
        fig_pie = px.pie(
            values=location_counts.values,
            names=location_counts.index,
            title="위치별 매물 수"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        if not mf_data.empty:
            location_mf = mf_data.groupby('location')['mf_per_point'].mean().sort_values()
            fig_bar = px.bar(
                x=location_mf.index,
                y=location_mf.values,
                labels={'x': '위치', 'y': '평균 MF/pt ($)'},
                title="위치별 평균 MF/pt"
            )
            fig_bar.add_hline(y=0.10, line_dash="dash", line_color="green")
            st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # 4. 포인트 분포
    st.subheader("포인트 분포")

    points_data = filtered_df[filtered_df['points'].notna()].copy()
    if not points_data.empty:
        fig_hist = px.histogram(
            points_data,
            x='points',
            nbins=30,
            labels={'points': '포인트', 'count': '매물 수'},
            color='location'
        )
        fig_hist.update_layout(height=400)
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("---")

    # 5. 등급별 가격 분포 (박스플롯)
    st.subheader("등급별 가격 분포")

    grade_data = filtered_df[
        (filtered_df['deal_grade'].notna()) &
        (filtered_df['asking_price'].notna())
    ].copy()

    if not grade_data.empty:
        # 등급 순서 정의
        grade_order = ['excellent', 'good', 'fair', 'poor']
        grade_labels = {'excellent': '★★★ 최고', 'good': '★★☆ 좋음', 'fair': '★☆☆ 보통', 'poor': '☆☆☆ 비추천'}

        grade_data['grade_label'] = grade_data['deal_grade'].map(grade_labels)

        fig_box = px.box(
            grade_data,
            x='grade_label',
            y='asking_price',
            color='grade_label',
            color_discrete_map={
                '★★★ 최고': '#28a745',
                '★★☆ 좋음': '#ffc107',
                '★☆☆ 보통': '#fd7e14',
                '☆☆☆ 비추천': '#dc3545'
            },
            labels={'grade_label': '등급', 'asking_price': '가격 ($)'},
            category_orders={'grade_label': [grade_labels[g] for g in grade_order if g in grade_data['deal_grade'].values]}
        )
        fig_box.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_box, use_container_width=True)


# 페이지 실행
if __name__ == "__main__":
    main()
else:
    main()
