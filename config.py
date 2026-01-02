"""
HGVC Deal Finder 설정 파일
"""
from pathlib import Path

# 프로젝트 경로
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "listings.db"

# TUG Marketplace 설정
TUG_BASE_URL = "https://tug2.com/timesharemarketplace"
TUG_SEARCH_URL = f"{TUG_BASE_URL}/search"
TUG_HGVC_SEARCH_PARAMS = {
    "ForSale": "True",
    "q": "HGVC"
}

# 스크래핑 설정
REQUEST_DELAY_MIN = 2.0  # 최소 대기 시간 (초)
REQUEST_DELAY_MAX = 5.0  # 최대 대기 시간 (초)
MAX_RETRIES = 3          # 최대 재시도 횟수
CACHE_EXPIRE_SECONDS = 900  # 캐시 만료 시간 (15분)

# HTTP 헤더
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

# 딜 등급 임계값 (MF per point)
GRADE_THRESHOLDS = {
    "excellent": 0.10,  # ★★★ 최고
    "good": 0.15,       # ★★☆ 좋음
    "fair": 0.20,       # ★☆☆ 보통
    # 이 이상은 ☆☆☆ 비추천
}

# 10년 비용 계산 상수
CLOSING_COSTS = 1100          # 평균 클로징 비용 ($)
EOY_CLUB_DUES_ANNUAL = 209    # EOY 클럽 연회비 ($)

# 기본 필터 값
DEFAULT_POINTS_RANGE = (5000, 30000)
DEFAULT_PRICE_RANGE = (0, 20000)
DEFAULT_MF_PER_POINT_MAX = 0.30

# 위치 키워드 매핑
LOCATION_KEYWORDS = {
    "Las Vegas": ["vegas", "elara", "boulevard", "flamingo", "trump", "paradise"],
    "Orlando": ["orlando", "parc soleil", "seaworld", "tuscany", "international drive"],
    "Hawaii": ["hawaii", "waikiki", "waikoloa", "maui", "kona", "kings land",
               "ocean tower", "grand islander", "lagoon tower", "kalia"],
    "New York": ["new york", "manhattan", "midtown", "west 57"],
    "Miami": ["miami", "south beach", "mcalpin"],
    "Park City": ["park city", "sunrise"],
    "San Diego": ["san diego", "marbrisa"],
    "Carlsbad": ["carlsbad"],
    "Myrtle Beach": ["myrtle", "anderson ocean", "ocean 22"],
    "Scotland": ["scotland", "craigendarroch"],
    "Japan": ["japan", "odawara", "okinawa", "sesoko"],
    "Italy": ["italy", "tuscany"],
}

# UI 텍스트 (한국어)
UI_TEXT = {
    "app_title": "HGVC 딜 파인더",
    "dashboard": "딜 대시보드",
    "analysis": "분석",
    "data_management": "데이터 관리",

    # 필터
    "filter_header": "필터 설정",
    "season": "시즌",
    "season_platinum_only": "Platinum만",
    "season_all": "전체",
    "usage": "사용 주기",
    "usage_annual_only": "Annual만",
    "usage_include_eoy": "EOY 포함",
    "usage_all": "전체",
    "location": "위치",
    "points_range": "포인트 범위",
    "price_range": "가격 범위",
    "max_mf_per_point": "최대 MF/pt",
    "data_sources": "데이터 소스",

    # 테이블 컬럼
    "col_grade": "등급",
    "col_resort": "리조트",
    "col_location": "위치",
    "col_points": "포인트",
    "col_usage": "사용주기",
    "col_price": "가격",
    "col_annual_mf": "연간MF",
    "col_mf_per_point": "MF/pt",
    "col_10yr_cost": "10년비용",
    "col_source": "출처",

    # 등급
    "grade_excellent": "★★★ 최고",
    "grade_good": "★★☆ 좋음",
    "grade_fair": "★☆☆ 보통",
    "grade_poor": "☆☆☆ 비추천",
    "grade_unknown": "??? 정보없음",

    # 메트릭
    "total_listings": "총 매물",
    "avg_mf_per_point": "평균 MF/pt",
    "best_deal": "최저 MF/pt",
    "excellent_deals": "최고 등급 매물",

    # 버튼
    "scrape_tug": "TUG 스크래핑",
    "upload_mf_csv": "MF 데이터 업로드",
    "refresh": "새로고침",

    # 메시지
    "no_listings": "매물이 없습니다. 필터를 조정하거나 데이터를 스크래핑하세요.",
    "scraping": "스크래핑 중...",
    "scrape_success": "스크래핑 완료: {count}개 매물",
    "scrape_error": "스크래핑 실패: {error}",
    "last_updated": "마지막 업데이트: {time}",
}

# 등급 색상 (배경색)
GRADE_COLORS = {
    "excellent": "#d4edda",  # 초록
    "good": "#fff3cd",       # 노랑
    "fair": "#ffe5d0",       # 주황
    "poor": "#f8d7da",       # 빨강
    "unknown": "#f0f0f0",    # 회색
}
