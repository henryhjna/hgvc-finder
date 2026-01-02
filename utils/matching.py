"""
리조트명 매칭 유틸리티
Fuzzy matching을 사용한 리조트명 정규화 및 매칭
"""
import re
from typing import Optional, Tuple, List, Dict
from pathlib import Path

from rapidfuzz import fuzz, process

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LOCATION_KEYWORDS


# HGVC 리조트명 별칭 매핑
RESORT_ALIASES: Dict[str, List[str]] = {
    'elara': ['elara', 'elara grand', 'elara by hilton'],
    'boulevard': ['on the boulevard', 'boulevard', 'las vegas boulevard'],
    'flamingo': ['at the flamingo', 'flamingo'],
    'trump': ['trump international', 'trump'],
    'paradise': ['paradise', 'paradise las vegas'],
    'parc soleil': ['parc soleil', 'parc soliel'],  # 흔한 오타 포함
    'seaworld': ['at seaworld', 'seaworld', 'sea world'],
    'tuscany village': ['tuscany village', 'tuscany'],
    'ocean tower': ['ocean tower', 'waikoloa ocean tower'],
    'bay club': ['bay club', 'waikoloa bay club'],
    'kings land': ["kings land", "king's land", "kingsland"],
    'grand islander': ['grand islander'],
    'lagoon tower': ['lagoon tower', 'waikiki lagoon tower'],
    'kalia': ['kalia tower', 'kalia suites'],
    'west 57th': ['west 57th', 'west 57', 'w 57th', '57th street'],
    'anderson ocean': ['anderson ocean', 'ocean plaza'],
    'mcalpin': ['mcalpin', 'mcalpin ocean plaza'],
    'marbrisa': ['marbrisa', 'carlsbad'],
    'sunrise lodge': ['sunrise lodge', 'park city'],
    'valdoro': ['valdoro', 'breckenridge'],
    'craigendarroch': ['craigendarroch', 'scotland'],
}


def normalize_resort_name(name: str) -> str:
    """
    리조트명 정규화

    Args:
        name: 원본 리조트명

    Returns:
        정규화된 리조트명 (소문자, 접두사 제거)
    """
    if not name:
        return ''

    # 공통 접두사 제거
    name = re.sub(r'^Hilton Grand Vacations?\s*(Club)?\s*', '', name, flags=re.I)
    name = re.sub(r'^HGV(C)?\s*', '', name, flags=re.I)
    name = re.sub(r'^The\s+', '', name, flags=re.I)

    # "at the", "on the", "by" 등 제거
    name = re.sub(r'\b(at the|on the|at|by)\b\s*', '', name, flags=re.I)

    # 구분자 정규화
    name = re.sub(r'\s*[-–—]\s*', ' ', name)

    # 공백 정리
    name = ' '.join(name.split())

    return name.lower().strip()


def get_canonical_name(name: str) -> Optional[str]:
    """
    별칭에서 정규 리조트명 찾기

    Args:
        name: 정규화된 리조트명

    Returns:
        정규 리조트명 또는 None
    """
    name_lower = name.lower()

    for canonical, aliases in RESORT_ALIASES.items():
        for alias in aliases:
            if alias in name_lower:
                return canonical

    return None


def match_resort_to_reference(
    listing_resort: str,
    reference_resorts: List[str],
    threshold: int = 75
) -> Optional[Tuple[str, int]]:
    """
    매물 리조트명을 참조 리조트 목록과 매칭

    Args:
        listing_resort: 매물의 리조트명
        reference_resorts: 참조 리조트명 목록
        threshold: 최소 매칭 점수 (0-100)

    Returns:
        (매칭된 리조트명, 점수) 또는 None
    """
    normalized = normalize_resort_name(listing_resort)

    if not normalized or not reference_resorts:
        return None

    # 1. 정규명 별칭 매칭 시도
    canonical = get_canonical_name(normalized)
    if canonical:
        # 참조 목록에서 정규명 포함하는 것 찾기
        for ref in reference_resorts:
            ref_norm = normalize_resort_name(ref)
            if canonical in ref_norm or ref_norm in canonical:
                return (ref, 100)

    # 2. 직접 포함 관계 확인
    for ref in reference_resorts:
        ref_norm = normalize_resort_name(ref)
        if normalized in ref_norm or ref_norm in normalized:
            return (ref, 95)

    # 3. Fuzzy matching
    normalized_refs = {normalize_resort_name(r): r for r in reference_resorts}

    matches = process.extract(
        normalized,
        list(normalized_refs.keys()),
        scorer=fuzz.token_sort_ratio,
        limit=1
    )

    if matches and matches[0][1] >= threshold:
        matched_norm = matches[0][0]
        original_ref = normalized_refs[matched_norm]
        return (original_ref, matches[0][1])

    return None


def infer_location(resort_name: str) -> str:
    """
    리조트명에서 위치 추론

    Args:
        resort_name: 리조트명

    Returns:
        위치 문자열
    """
    if not resort_name:
        return 'Other'

    name_lower = resort_name.lower()

    for location, keywords in LOCATION_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return location

    return 'Other'


def extract_unit_info(text: str) -> Dict[str, any]:
    """
    텍스트에서 유닛 정보 추출

    Args:
        text: 매물 설명 텍스트

    Returns:
        유닛 정보 딕셔너리 (bedrooms, bathrooms, unit_type)
    """
    info = {}

    # 침실 수
    bed_match = re.search(r'(\d+)\s*(?:BR|Bed|bedroom)s?', text, re.I)
    if bed_match:
        info['bedrooms'] = int(bed_match.group(1))

    # 스튜디오
    if re.search(r'\bstudio\b', text, re.I):
        info['bedrooms'] = 0
        info['unit_type'] = 'Studio'

    # 욕실 수
    bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:BA|Bath|bathroom)s?', text, re.I)
    if bath_match:
        info['bathrooms'] = float(bath_match.group(1))

    # 유닛 타입 결정
    if 'unit_type' not in info and 'bedrooms' in info:
        if info['bedrooms'] == 0:
            info['unit_type'] = 'Studio'
        else:
            info['unit_type'] = f"{info['bedrooms']}BR"

    return info


def extract_season(text: str) -> str:
    """
    텍스트에서 시즌 추출

    Args:
        text: 매물 설명 텍스트

    Returns:
        시즌 문자열
    """
    text_lower = text.lower()

    if 'platinum' in text_lower:
        return 'Platinum'
    elif 'gold' in text_lower:
        return 'Gold'
    elif 'silver' in text_lower:
        return 'Silver'
    elif 'bronze' in text_lower:
        return 'Bronze'

    # 기본값 (HGVC에서 가장 일반적)
    return 'Platinum'


def extract_usage(text: str) -> str:
    """
    텍스트에서 사용 주기 추출

    Args:
        text: 매물 설명 텍스트

    Returns:
        사용 주기 문자열
    """
    text_lower = text.lower()

    if re.search(r'\beven\s*year', text_lower):
        return 'EOY-Even'
    elif re.search(r'\bodd\s*year', text_lower):
        return 'EOY-Odd'
    elif re.search(r'\bevery\s*other\s*year|biennial|\beoy\b', text_lower):
        return 'EOY'

    return 'Annual'
