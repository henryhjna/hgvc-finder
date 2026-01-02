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

# 페이지 정의
pages = {
    "🏨 HGVC 딜 파인더": [
        st.Page("app/pages/1_dashboard.py", title="딜 대시보드", icon="📊", default=True),
        st.Page("app/pages/2_analysis.py", title="분석", icon="📈"),
        st.Page("app/pages/3_data_management.py", title="데이터 관리", icon="🔧"),
    ]
}

# 네비게이션 (섹션 헤더 포함)
pg = st.navigation(pages)
pg.run()
