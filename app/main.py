"""
HGVC Deal Finder - Streamlit 메인 앱
"""
import streamlit as st
from pathlib import Path
import sys

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import UI_TEXT

# 페이지 설정
st.set_page_config(
    page_title=UI_TEXT['app_title'],
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 페이지 정의
dashboard_page = st.Page(
    "pages/dashboard.py",
    title="딜 대시보드",
    icon="📊",
    default=True
)

analysis_page = st.Page(
    "pages/analysis.py",
    title="분석",
    icon="📈"
)

data_page = st.Page(
    "pages/data_management.py",
    title="데이터 관리",
    icon="🔧"
)

# 네비게이션 설정
pg = st.navigation([dashboard_page, analysis_page, data_page])

# 사이드바 헤더
st.sidebar.title("🏨 HGVC 딜 파인더")
st.sidebar.caption("HGVC 타임쉐어 리셀 매물 분석")
st.sidebar.markdown("---")

# 선택된 페이지 실행
pg.run()
