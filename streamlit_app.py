"""
HGVC Deal Finder - Streamlit Cloud 진입점
"""
import streamlit as st
from pathlib import Path
import sys

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import UI_TEXT

# 페이지 설정
st.set_page_config(
    page_title=UI_TEXT['app_title'],
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS로 사이드바 요소 순서 강제 변경 (제목 → 메뉴 → 필터)
st.markdown("""
<style>
    /* 사이드바 컨텐츠를 flexbox로 변경 */
    section[data-testid="stSidebar"] > div > div > div {
        display: flex !important;
        flex-direction: column !important;
    }

    /* 제목 컨테이너를 맨 위로 (order: -2) */
    section[data-testid="stSidebar"] div:has(> .sidebar-title) {
        order: -2 !important;
    }

    /* 네비게이션 메뉴 (order: -1) */
    [data-testid="stSidebarNav"] {
        order: -1 !important;
    }

    .sidebar-title {
        font-size: 1.5rem;
        font-weight: 600;
        padding: 0.5rem 0;
        margin: 0;
    }
    .sidebar-caption {
        font-size: 0.85rem;
        color: #808080;
        padding-bottom: 0.5rem;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

# 사이드바 제목
st.sidebar.markdown('<p class="sidebar-title">🏨 HGVC 딜 파인더</p>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="sidebar-caption">HGVC 타임쉐어 리셀 매물 분석</p>', unsafe_allow_html=True)
st.sidebar.markdown("---")

# 페이지 정의
dashboard_page = st.Page("app/pages/1_dashboard.py", title="딜 대시보드", icon="📊", default=True)
analysis_page = st.Page("app/pages/2_analysis.py", title="분석", icon="📈")
data_page = st.Page("app/pages/3_data_management.py", title="데이터 관리", icon="🔧")

# 네비게이션
pg = st.navigation([dashboard_page, analysis_page, data_page], position="sidebar")
pg.run()
