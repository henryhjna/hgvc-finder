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

# 사이드바 제목 (먼저 렌더링)
st.sidebar.title("🏨 HGVC 딜 파인더")
st.sidebar.caption("HGVC 타임쉐어 리셀 매물 분석")
st.sidebar.markdown("---")

# 페이지 정의
pages = [
    st.Page("app/pages/1_dashboard.py", title="딜 대시보드", icon="📊", default=True),
    st.Page("app/pages/2_analysis.py", title="분석", icon="📈"),
    st.Page("app/pages/3_data_management.py", title="데이터 관리", icon="🔧"),
]

# 네비게이션 (hidden으로 자동 사이드바 렌더링 비활성화)
pg = st.navigation(pages, position="hidden")

# 수동 메뉴 (라디오 버튼)
page_options = {
    "📊 딜 대시보드": "app/pages/1_dashboard.py",
    "📈 분석": "app/pages/2_analysis.py",
    "🔧 데이터 관리": "app/pages/3_data_management.py",
}

# 현재 페이지 확인
current_page = st.session_state.get("current_page", "📊 딜 대시보드")

selection = st.sidebar.radio(
    "메뉴",
    options=list(page_options.keys()),
    index=list(page_options.keys()).index(current_page) if current_page in page_options else 0,
    label_visibility="collapsed"
)

# 페이지 전환
if selection != current_page:
    st.session_state["current_page"] = selection
    st.switch_page(page_options[selection])

st.sidebar.markdown("---")

# 현재 페이지 실행
pg.run()
