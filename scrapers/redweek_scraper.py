"""
RedWeek Marketplace 스크래퍼
https://www.redweek.com
"""
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from scrapers.base import BaseScraper
from config import LOCATION_KEYWORDS


class RedWeekScraper(BaseScraper):
    """RedWeek HGVC 매물 스크래퍼"""

    SOURCE_NAME = "redweek"
    BASE_URL = "https://www.redweek.com"

    # HGVC 리조트 디렉토리 URL
    HGVC_DIRECTORY_URL = "https://www.redweek.com/timeshare-companies/hgvc/resort-directory"

    # HGVC 관련 키워드
    HGVC_KEYWORDS = ['hgvc', 'hilton grand', 'hilton vacation', 'hilton club']

    def __init__(self):
        super().__init__(cache_name="redweek_cache")
        self.logger = logging.getLogger(self.__class__.__name__)

    def scrape_listings(self, filters: Dict = None) -> List[Dict]:
        """
        RedWeek에서 HGVC 매물 스크래핑

        1. HGVC 리조트 디렉토리에서 리조트 목록 가져오기
        2. 각 리조트의 resale 페이지에서 매물 추출

        Args:
            filters: 추가 필터 (price_min, price_max 등)

        Returns:
            매물 딕셔너리 리스트
        """
        self.logger.info("RedWeek 스크래핑 시작")

        # 1. HGVC 리조트 목록 가져오기
        resorts = self._get_hgvc_resorts()
        self.logger.info(f"HGVC 리조트 {len(resorts)}개 발견")

        all_listings = []

        # 2. 각 리조트의 resale 페이지 스크래핑
        for resort_name, resort_url in resorts:
            self.logger.info(f"스크래핑 중: {resort_name}")

            resale_url = f"{resort_url}/timeshare-resales"
            html = self._fetch_with_retry(resale_url)

            if not html:
                self.logger.warning(f"페이지 가져오기 실패: {resort_name}")
                continue

            soup = self._parse_html(html)
            cards = soup.select('.posting-card')

            for card in cards:
                try:
                    listing = self.parse_listing_card(card, resort_name)
                    if listing:
                        # 필터 적용
                        if filters:
                            if filters.get('price_max') and listing.get('asking_price', 0) > filters['price_max']:
                                continue
                            if filters.get('price_min') and listing.get('asking_price', 0) < filters['price_min']:
                                continue

                        all_listings.append(listing)
                except Exception as e:
                    self.logger.error(f"카드 파싱 오류: {e}")
                    continue

        self.logger.info(f"총 {len(all_listings)}개 매물 수집")
        return all_listings

    def _get_hgvc_resorts(self) -> List[tuple]:
        """
        HGVC 리조트 디렉토리에서 리조트 목록 가져오기

        Returns:
            (리조트명, URL) 튜플 리스트
        """
        html = self._fetch_with_retry(self.HGVC_DIRECTORY_URL)
        if not html:
            return []

        soup = self._parse_html(html)
        resorts = []

        # 리조트 링크 찾기
        resort_links = soup.select('a[href*="/resort/"]')

        for link in resort_links:
            href = link.get('href', '')
            name = link.get_text(strip=True)

            # HGVC 관련 리조트만 필터링
            if any(kw in name.lower() for kw in self.HGVC_KEYWORDS):
                full_url = urljoin(self.BASE_URL, href)
                resorts.append((name, full_url))

        # 중복 제거
        seen = set()
        unique_resorts = []
        for name, url in resorts:
            if url not in seen:
                seen.add(url)
                unique_resorts.append((name, url))

        return unique_resorts

    def _fetch_detail_page_points(self, posting_url: str) -> Optional[int]:
        """
        상세 페이지에서 ANNUAL POINTS 추출

        Args:
            posting_url: 매물 상세 페이지 URL

        Returns:
            포인트 수 또는 None
        """
        html = self._fetch_with_retry(posting_url)
        if not html:
            return None

        text = html
        # ANNUAL POINTS: 2000.0 패턴
        points_match = re.search(r'ANNUAL\s*POINTS[:\s]+([0-9,.]+)', text, re.I)
        if points_match:
            try:
                points_str = points_match.group(1).replace(',', '').replace('.0', '')
                return int(float(points_str))
            except ValueError:
                pass
        return None

    def parse_listing_card(self, card, resort_name: str = None, fetch_details: bool = True) -> Optional[Dict]:
        """
        RedWeek posting-card 파싱

        RedWeek HTML 구조:
        <div class="posting-card"
             data-posting-path="/posting/R1362283"
             data-price="1000"
             data-bedrooms="2"
             data-bathrooms="2"
             data-sleeps="8"
             data-use="Annual"
             data-week="Floating"
             data-type="Deed"
             data-view="Ocean view">
            ...
            Price: $1,000
            Maint. fee: $1,828
            ...
        </div>

        Args:
            card: BeautifulSoup posting-card 요소
            resort_name: 리조트명 (상위에서 전달)
            fetch_details: 상세 페이지에서 포인트 추출 여부

        Returns:
            매물 정보 딕셔너리
        """
        listing = {
            'source': self.SOURCE_NAME,
            'scraped_at': datetime.utcnow()
        }

        # 1. data 속성에서 기본 정보 추출
        posting_path = card.get('data-posting-path', '')
        if not posting_path:
            return None

        listing['listing_url'] = urljoin(self.BASE_URL, posting_path)

        # ID 추출
        id_match = re.search(r'/posting/([A-Z0-9]+)', posting_path)
        if id_match:
            listing['source_id'] = f"redweek_{id_match.group(1)}"
        else:
            return None

        # data 속성 파싱
        listing['asking_price'] = self._extract_number(card.get('data-price', ''))
        listing['bedrooms'] = self._extract_number(card.get('data-bedrooms', ''))

        # 사용 주기
        use = card.get('data-use', 'Annual')
        if 'even' in use.lower():
            listing['usage'] = 'EOY-Even'
        elif 'odd' in use.lower():
            listing['usage'] = 'EOY-Odd'
        elif 'every other' in use.lower() or 'biennial' in use.lower():
            listing['usage'] = 'EOY'
        else:
            listing['usage'] = 'Annual'

        # 침실 수로 unit_type 결정
        bedrooms = listing.get('bedrooms', 0)
        if bedrooms == 0:
            listing['unit_type'] = 'Studio'
        elif bedrooms:
            listing['unit_type'] = f"{int(bedrooms)}BR"

        # 2. 텍스트에서 MF 추출
        text = card.get_text(separator=' ', strip=True)

        mf_match = re.search(r'Maint\.?\s*fee:?\s*\$?([\d,]+)', text, re.I)
        if mf_match:
            listing['annual_mf'] = float(mf_match.group(1).replace(',', ''))

        # 3. 리조트명
        listing['resort_name'] = resort_name or 'Unknown HGVC Resort'

        # 4. 시즌 (RedWeek은 week 정보 사용)
        week = card.get('data-week', '')
        if 'float' in week.lower():
            listing['season'] = 'Platinum'  # Floating은 보통 Platinum
        else:
            listing['season'] = 'Platinum'  # HGVC는 대부분 Platinum

        # 5. 위치 추론
        listing['location'] = self._infer_location(resort_name or '')

        # 6. 포인트 - 상세 페이지에서만 추출 (추정 절대 안 함)
        if fetch_details:
            listing['points'] = self._fetch_detail_page_points(listing['listing_url'])
        else:
            listing['points'] = None  # 상세 페이지 방문 안 하면 포인트 없음

        # 7. 리조트명 정규화
        listing['resort_name_normalized'] = self._normalize_resort_name(
            listing.get('resort_name', '')
        )

        return listing

    def _normalize_resort_name(self, name: str) -> str:
        """리조트명 정규화 (매칭용)"""
        if not name:
            return ''
        # 공통 접두사 제거
        name = re.sub(r'^Hilton Grand Vacations?\s*(Club)?', '', name, flags=re.I)
        name = re.sub(r'^HGV(C)?\s*', '', name, flags=re.I)
        name = re.sub(r'\s+by Hilton.*$', '', name, flags=re.I)
        # 구분자 정규화
        name = re.sub(r'\s*[-–—]\s*', ' ', name)
        # 공백 정리
        name = ' '.join(name.split())
        return name.lower().strip()

    def _infer_location(self, resort_name: str) -> str:
        """리조트명에서 위치 추론"""
        if not resort_name:
            return 'Other'

        name_lower = resort_name.lower()
        for location, keywords in LOCATION_KEYWORDS.items():
            if any(kw in name_lower for kw in keywords):
                return location
        return 'Other'


# 테스트용 메인
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = RedWeekScraper()
    listings = scraper.scrape_listings()
    print(f"\n총 {len(listings)}개 매물 발견")
    print()
    for listing in listings[:10]:
        print(f"- {listing.get('resort_name')}")
        print(f"  가격: ${listing.get('asking_price', 'N/A')}, "
              f"MF: ${listing.get('annual_mf', 'N/A')}")
        print(f"  위치: {listing.get('location')}, "
              f"사용: {listing.get('usage')}")
        print()
