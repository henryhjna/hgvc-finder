"""
HGVC 딜 계산 로직
MF per Point, 10년 비용, 딜 등급 계산
"""
from typing import Dict, Optional, List
from pathlib import Path
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GRADE_THRESHOLDS, CLOSING_COSTS, EOY_CLUB_DUES_ANNUAL, GRADE_COLORS


def calculate_annual_points(points: int, usage: str) -> int:
    """
    연환산 포인트 계산

    Args:
        points: 원래 포인트
        usage: 사용 주기 ('Annual', 'EOY-Even', 'EOY-Odd', 'EOY')

    Returns:
        연환산 포인트
    """
    if not points:
        return 0

    if usage and usage.upper().startswith('EOY'):
        return points // 2
    return points


def calculate_mf_per_point(annual_mf: float, annual_points: int) -> Optional[float]:
    """
    MF per Point 계산

    Args:
        annual_mf: 연간 유지비
        annual_points: 연환산 포인트

    Returns:
        MF per Point 또는 None
    """
    if not annual_mf or not annual_points or annual_points == 0:
        return None
    return annual_mf / annual_points


def calculate_10yr_cost(asking_price: float, annual_mf: float, usage: str) -> Optional[float]:
    """
    10년 총비용 계산

    Args:
        asking_price: 구매 가격
        annual_mf: 연간 유지비
        usage: 사용 주기

    Returns:
        10년 총비용 또는 None
    """
    if asking_price is None or annual_mf is None:
        return None

    if usage and usage.upper().startswith('EOY'):
        # EOY: 5번의 MF + 10년간 매년 클럽 회비
        return asking_price + CLOSING_COSTS + (annual_mf * 5) + (EOY_CLUB_DUES_ANNUAL * 10)
    else:
        # Annual: 10번의 MF
        return asking_price + CLOSING_COSTS + (annual_mf * 10)


def get_deal_grade(mf_per_point: Optional[float]) -> str:
    """
    딜 등급 결정

    Args:
        mf_per_point: MF per Point

    Returns:
        등급 문자열 ('excellent', 'good', 'fair', 'poor', 'unknown')
    """
    if mf_per_point is None:
        return 'unknown'

    if mf_per_point <= GRADE_THRESHOLDS['excellent']:
        return 'excellent'
    elif mf_per_point <= GRADE_THRESHOLDS['good']:
        return 'good'
    elif mf_per_point <= GRADE_THRESHOLDS['fair']:
        return 'fair'
    else:
        return 'poor'


def get_grade_stars(grade: str) -> str:
    """
    등급을 별표로 변환

    Args:
        grade: 등급 문자열

    Returns:
        별표 문자열
    """
    grade_map = {
        'excellent': '★★★',
        'good': '★★☆',
        'fair': '★☆☆',
        'poor': '☆☆☆',
        'unknown': '???',
    }
    return grade_map.get(grade, '???')


def get_grade_display(grade: str) -> str:
    """
    등급을 표시용 문자열로 변환 (한국어)

    Args:
        grade: 등급 문자열

    Returns:
        표시용 문자열
    """
    grade_map = {
        'excellent': '★★★ 최고',
        'good': '★★☆ 좋음',
        'fair': '★☆☆ 보통',
        'poor': '☆☆☆ 비추천',
        'unknown': '??? 정보없음',
    }
    return grade_map.get(grade, '??? 정보없음')


def get_grade_color(grade: str) -> str:
    """
    등급에 해당하는 배경색 반환

    Args:
        grade: 등급 문자열

    Returns:
        HEX 색상 코드
    """
    return GRADE_COLORS.get(grade, GRADE_COLORS['unknown'])


def calculate_deal_metrics(listing: Dict, mf_from_reference: Optional[float] = None) -> Dict:
    """
    매물의 모든 딜 메트릭 계산

    Args:
        listing: 매물 정보 딕셔너리
        mf_from_reference: MF 참조 데이터에서 가져온 연간 MF (매물에 없을 경우 사용)

    Returns:
        계산된 메트릭 딕셔너리
    """
    points = listing.get('points', 0) or 0
    usage = listing.get('usage', 'Annual')
    asking_price = listing.get('asking_price', 0) or 0

    # MF 결정: 매물 데이터 우선, 없으면 참조 데이터 사용
    annual_mf = listing.get('annual_mf') or mf_from_reference

    # 연환산 포인트
    annual_points = calculate_annual_points(points, usage)

    # MF per Point
    mf_per_point = calculate_mf_per_point(annual_mf, annual_points)

    # 10년 총비용
    total_10yr = calculate_10yr_cost(asking_price, annual_mf, usage)

    # 딜 등급
    grade = get_deal_grade(mf_per_point)

    return {
        'annual_points': annual_points,
        'mf_per_point': round(mf_per_point, 4) if mf_per_point else None,
        'total_10yr': round(total_10yr, 2) if total_10yr else None,
        'deal_grade': grade,
        'deal_grade_stars': get_grade_stars(grade),
        'deal_grade_display': get_grade_display(grade),
        'grade_color': get_grade_color(grade),
    }


def enrich_listings_dataframe(
    listings_df: pd.DataFrame,
    mf_reference_df: pd.DataFrame = None
) -> pd.DataFrame:
    """
    매물 DataFrame에 계산된 메트릭 추가

    Args:
        listings_df: 매물 DataFrame
        mf_reference_df: MF 참조 DataFrame (옵션)

    Returns:
        메트릭이 추가된 DataFrame
    """
    if listings_df.empty:
        return listings_df

    # MF 참조 데이터 딕셔너리 생성 (정규화된 리조트명 기준)
    mf_lookup = {}
    if mf_reference_df is not None and not mf_reference_df.empty:
        for _, row in mf_reference_df.iterrows():
            key = row.get('resort_name_normalized', '').lower()
            if key:
                mf_lookup[key] = row.get('annual_mf')

    # 각 매물에 메트릭 계산
    metrics_list = []
    for _, row in listings_df.iterrows():
        listing_dict = row.to_dict()

        # MF 참조 데이터에서 MF 찾기
        mf_from_ref = None
        resort_norm = listing_dict.get('resort_name_normalized', '')
        if resort_norm and resort_norm.lower() in mf_lookup:
            mf_from_ref = mf_lookup[resort_norm.lower()]

        metrics = calculate_deal_metrics(listing_dict, mf_from_ref)
        metrics_list.append(metrics)

    # 메트릭 DataFrame 생성 및 병합
    metrics_df = pd.DataFrame(metrics_list)
    result = pd.concat([listings_df.reset_index(drop=True), metrics_df], axis=1)

    return result


def get_summary_stats(df: pd.DataFrame) -> Dict:
    """
    요약 통계 계산

    Args:
        df: 메트릭이 포함된 매물 DataFrame

    Returns:
        요약 통계 딕셔너리
    """
    if df.empty:
        return {
            'total_count': 0,
            'avg_mf_per_point': None,
            'min_mf_per_point': None,
            'best_deal_resort': None,
            'excellent_count': 0,
            'good_count': 0,
            'fair_count': 0,
            'poor_count': 0,
        }

    mf_col = df['mf_per_point'].dropna()

    best_deal = None
    best_resort = None
    if not mf_col.empty:
        best_idx = mf_col.idxmin()
        best_deal = mf_col[best_idx]
        best_resort = df.loc[best_idx, 'resort_name'] if 'resort_name' in df.columns else None

    return {
        'total_count': len(df),
        'avg_mf_per_point': round(mf_col.mean(), 4) if not mf_col.empty else None,
        'min_mf_per_point': round(best_deal, 4) if best_deal else None,
        'best_deal_resort': best_resort,
        'excellent_count': len(df[df['deal_grade'] == 'excellent']) if 'deal_grade' in df.columns else 0,
        'good_count': len(df[df['deal_grade'] == 'good']) if 'deal_grade' in df.columns else 0,
        'fair_count': len(df[df['deal_grade'] == 'fair']) if 'deal_grade' in df.columns else 0,
        'poor_count': len(df[df['deal_grade'] == 'poor']) if 'deal_grade' in df.columns else 0,
    }
