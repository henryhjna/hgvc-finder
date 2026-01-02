"""
TUG Marketplace 스크래퍼
https://tug2.com/timesharemarketplace
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
from config import TUG_SEARCH_URL, TUG_HGVC_SEARCH_PARAMS, LOCATION_KEYWORDS


class TUGScraper(BaseScraper):
    """TUG Marketplace HGVC 매물 스크래퍼"""

    SOURCE_NAME = "tug"
    BASE_URL = "https://tug2.com"

    # HGVC 관련 키워드
    HGVC_KEYWORDS = ['hgvc', 'hilton grand', 'hilton vacation']

    def __init__(self):
        super().__init__(cache_name="tug_cache")
        self.logger = logging.getLogger(self.__class__.__name__)

    def scrape_listings(self, filters: Dict = None) -> List[Dict]:
        """
        TUG Marketplace에서 HGVC 매물 스크래핑

        Args:
            filters: 추가 필터 (price_min, price_max, location 등)

        Returns:
            매물 딕셔너리 리스트
        """
        params = {**TUG_HGVC_SEARCH_PARAMS}

        # 필터 적용
        if filters:
            if filters.get('price_max'):
                params['PriceMax'] = filters['price_max']
            if filters.get('price_min'):
                params['PriceMin'] = filters['price_min']

        self.logger.info(f"TUG 스크래핑 시작: {TUG_SEARCH_URL}")
        self.logger.info(f"파라미터: {params}")

        html = self._fetch_with_retry(TUG_SEARCH_URL, params)
        if not html:
            self.logger.error("페이지 가져오기 실패")
            return []

        self.logger.info(f"HTML 길이: {len(html)} bytes")

        soup = self._parse_html(html)

        # .listing-row 클래스로 매물 행 찾기
        listing_rows = soup.select('.listing-row')
        self.logger.info(f"전체 listing-row 수: {len(listing_rows)}")

        listings = []
        hgvc_count = 0

        for row in listing_rows:
            try:
                # HGVC 관련 매물인지 확인
                row_text = row.get_text().lower()
                if not any(kw in row_text for kw in self.HGVC_KEYWORDS):
                    continue

                hgvc_count += 1
                listing = self.parse_listing_row(row)
                if listing:
                    listings.append(listing)

            except Exception as e:
                self.logger.error(f"행 파싱 오류: {e}")
                continue

        self.logger.info(f"HGVC 관련 행: {hgvc_count}개")
        self.logger.info(f"파싱 성공: {len(listings)}개 매물")

        return listings

    def parse_listing_card(self, card) -> Optional[Dict]:
        """추상 메서드 구현 (사용하지 않음)"""
        return self.parse_listing_row(card)

    def parse_listing_row(self, row) -> Optional[Dict]:
        """
        개별 매물 행 파싱

        TUG HTML 구조:
        <div class="row listing-row">
            <div class="col-...">For Sale badge</div>
            <div class="col-...">
                <a href="/resorts/resort/...">Resort Name</a>
                <div>X,XXX Points</div>
            </div>
            <div class="col-...">Details</div>
            <div class="col-...">
                <strong class="text-success">$X,XXX.XX</strong>
                <small class="text-muted">Fees $X,XXX.XX</small>
            </div>
            <div class="col-...">
                <a href="/.../classified-listing/XXXXX">Open Listing</a>
            </div>
        </div>

        Args:
            row: BeautifulSoup .listing-row 요소

        Returns:
            매물 정보 딕셔너리
        """
        listing = {
            'source': self.SOURCE_NAME,
            'scraped_at': datetime.utcnow()
        }

        row_text = row.get_text(separator=' ', strip=True)

        # 1. Listing URL 및 ID 추출
        listing_link = row.select_one('a[href*="classified-listing"]')
        if not listing_link:
            return None

        href = listing_link.get('href', '')
        listing['listing_url'] = urljoin(self.BASE_URL, href)

        # ID 추출
        id_match = re.search(r'/classified-listing/(\d+)', href)
        if id_match:
            listing['source_id'] = f"tug_{id_match.group(1)}"
        else:
            return None

        # 2. 리조트명 추출
        resort_link = row.select_one('a[href*="/resorts/resort/"][href*="/description"]')
        if not resort_link:
            # 대체: 첫 번째 리조트 링크
            resort_link = row.select_one('a[href*="/resorts/resort/"]')

        if resort_link:
            listing['resort_name'] = resort_link.get_text(strip=True)
        else:
            return None

        # 3. 가격 추출 (.text-success 클래스)
        price_elem = row.select_one('.text-success, strong.text-success')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', price_text)
            if price_match:
                listing['asking_price'] = float(price_match.group(1).replace(',', ''))

        # FREE 매물 확인
        if listing.get('asking_price') is None:
            if 'free' in row_text.lower() or '$0' in row_text:
                listing['asking_price'] = 0.0

        # 4. 유지비(Fees) 추출 (.text-muted 클래스)
        fees_elem = row.select_one('.text-muted, small.text-muted')
        if fees_elem:
            fees_text = fees_elem.get_text(strip=True)
            fees_match = re.search(r'Fees?\s*\$\s*([\d,]+(?:\.\d{2})?)', fees_text, re.I)
            if fees_match:
                listing['annual_mf'] = float(fees_match.group(1).replace(',', ''))

        # 5. 포인트 추출
        points_patterns = [
            r'([\d,]+)\s*(?:Hilton Grand Vacation|HGVC|Hilton Vacation).*?Points',
            r'([\d,]+)\s*Points',
        ]
        for pattern in points_patterns:
            match = re.search(pattern, row_text, re.I)
            if match:
                listing['points'] = int(match.group(1).replace(',', ''))
                break

        # 6. 침실/욕실 추출 (.detail-item 클래스)
        bedroom_elem = row.select_one('.detail-item.bedroom')
        bathroom_elem = row.select_one('.detail-item.bathroom')

        if bedroom_elem:
            bed_text = bedroom_elem.get_text(strip=True).lower()
            if 'studio' in bed_text:
                listing['bedrooms'] = 0
                listing['unit_type'] = 'Studio'
            else:
                bed_match = re.search(r'(\d+)', bed_text)
                if bed_match:
                    listing['bedrooms'] = int(bed_match.group(1))
                    listing['unit_type'] = f"{listing['bedrooms']}BR"

        if bathroom_elem:
            bath_text = bathroom_elem.get_text(strip=True)
            bath_match = re.search(r'(\d+(?:\.\d+)?)', bath_text)
            if bath_match:
                listing['bathrooms'] = float(bath_match.group(1))

        # 7. 사용 주기 결정
        listing['usage'] = self._determine_usage(row_text)

        # 8. 시즌 추출
        listing['season'] = self._determine_season(row_text)

        # 9. 위치 추론
        listing['location'] = self._infer_location(listing.get('resort_name', ''))

        # 10. 리조트명 정규화
        listing['resort_name_normalized'] = self._normalize_resort_name(
            listing.get('resort_name', '')
        )

        return listing

    def _determine_usage(self, text: str) -> str:
        """사용 주기 결정"""
        text_lower = text.lower()
        if re.search(r'\beven\s*year', text_lower):
            return 'EOY-Even'
        elif re.search(r'\bodd\s*year', text_lower):
            return 'EOY-Odd'
        elif re.search(r'\bevery\s*other\s*year|biennial|\beoy\b', text_lower):
            return 'EOY'
        return 'Annual'

    def _determine_season(self, text: str) -> str:
        """시즌 결정"""
        text_lower = text.lower()
        if 'platinum' in text_lower:
            return 'Platinum'
        elif 'gold' in text_lower:
            return 'Gold'
        elif 'silver' in text_lower:
            return 'Silver'
        elif 'bronze' in text_lower:
            return 'Bronze'
        return 'Platinum'  # 기본값 (HGVC는 대부분 Platinum)

    def _normalize_resort_name(self, name: str) -> str:
        """리조트명 정규화 (매칭용)"""
        if not name:
            return ''
        # 공통 접두사 제거
        name = re.sub(r'^Hilton Grand Vacations?\s*(Club)?\s*', '', name, flags=re.I)
        name = re.sub(r'^HGV(C)?\s*', '', name, flags=re.I)
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
    scraper = TUGScraper()
    listings = scraper.scrape_listings()
    print(f"\n총 {len(listings)}개 매물 발견")
    print()
    for listing in listings[:10]:
        print(f"- {listing.get('resort_name')}")
        print(f"  가격: ${listing.get('asking_price', 'N/A')}, "
              f"포인트: {listing.get('points', 'N/A')}, "
              f"MF: ${listing.get('annual_mf', 'N/A')}")
        print(f"  위치: {listing.get('location')}, "
              f"사용: {listing.get('usage')}")
        print()
