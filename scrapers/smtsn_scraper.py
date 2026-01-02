"""
SellMyTimeshareNow (SMTSN) 스크래퍼
https://www.sellmytimesharenow.com
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


class SMTSNScraper(BaseScraper):
    """SellMyTimeshareNow HGVC 매물 스크래퍼"""

    SOURCE_NAME = "smtsn"
    BASE_URL = "https://www.sellmytimesharenow.com"

    # HGVC 리조트 목록 (URL에 사용할 이름)
    HGVC_RESORTS = [
        ("Elara, a Hilton Grand Vacations Club", "Las Vegas"),
        ("Hilton Grand Vacations Club on the Boulevard", "Las Vegas"),
        ("Hilton Grand Vacations Club at the Flamingo", "Las Vegas"),
        ("Hilton Grand Vacations Club at Trump International", "Las Vegas"),
        ("Hilton Grand Vacations Club on Paradise", "Las Vegas"),
        ("Hilton Grand Vacations Club at Parc Soleil", "Orlando"),
        ("Hilton Grand Vacations Club at SeaWorld", "Orlando"),
        ("Hilton Grand Vacations Club at Tuscany Village", "Orlando"),
        ("Hilton Grand Vacations Club at Las Palmeras", "Orlando"),
        ("Hilton Grand Vacations Club Ocean Tower", "Hawaii"),
        ("Hilton Grand Vacations Club at Kings Land", "Hawaii"),
        ("Hilton Grand Vacations Club at Lagoon Tower", "Hawaii"),
        ("Hilton Grand Vacations Club Grand Islander", "Hawaii"),
        ("Hilton Grand Vacations Club Grand Waikikian", "Hawaii"),
        ("Hilton Grand Vacations Club at Waikoloa Beach", "Hawaii"),
        ("Hilton Grand Vacations Club at MarBrisa", "California"),
        ("Hilton Grand Vacations Club at Anderson Ocean", "South Carolina"),
        ("Hilton Grand Vacations Club at Ocean 22", "South Carolina"),
        ("Hilton Club New York", "New York"),
        ("West 57th Street by Hilton Club", "New York"),
        ("Hilton Grand Vacations Club at Sunrise Lodge", "Utah"),
        ("Hilton Grand Vacations Club at Valdoro Mountain Lodge", "Colorado"),
        ("Hilton Grand Vacations Club at Craigendarroch", "Scotland"),
    ]

    def __init__(self):
        super().__init__(cache_name="smtsn_cache")
        self.logger = logging.getLogger(self.__class__.__name__)

    def _fetch_detail_page_points(self, posting_url: str) -> Optional[int]:
        """
        상세 페이지에서 포인트 추출

        SMTSN 상세 페이지 패턴:
        - "Points" 8000
        - "8,000 points"

        Args:
            posting_url: 매물 상세 페이지 URL

        Returns:
            포인트 수 또는 None
        """
        html = self._fetch_with_retry(posting_url)
        if not html:
            return None

        # 다양한 패턴 시도
        patterns = [
            r'"Points"[:\s]*(\d+)',           # "Points" 8000
            r'Points[:\s]+(\d[\d,]*)',         # Points: 8,000
            r'(\d[\d,]+)\s*points',            # 8,000 points
            r'ANNUAL\s*POINTS[:\s]+(\d[\d,]*)', # ANNUAL POINTS: 8000
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.I)
            if match:
                try:
                    points_str = match.group(1).replace(',', '')
                    return int(float(points_str))
                except ValueError:
                    continue

        return None

    def scrape_listings(self, filters: Dict = None) -> List[Dict]:
        """
        SMTSN에서 HGVC 매물 스크래핑

        Args:
            filters: 추가 필터 (price_min, price_max 등)

        Returns:
            매물 딕셔너리 리스트
        """
        self.logger.info("SMTSN 스크래핑 시작")

        all_listings = []

        for resort_name, location in self.HGVC_RESORTS:
            self.logger.info(f"스크래핑 중: {resort_name}")

            # URL 생성 (SMTSN은 공백을 +로, 쉼표는 그대로 사용)
            url_name = resort_name.replace(' ', '+')
            resale_url = f"{self.BASE_URL}/timeshare/{url_name}/resort/buy-timeshare/"

            html = self._fetch_with_retry(resale_url)
            if not html:
                self.logger.warning(f"페이지 가져오기 실패: {resort_name}")
                continue

            soup = self._parse_html(html)

            # result-box 카드 찾기
            cards = soup.select('.result-box.result-city-resort-listing')

            for card in cards:
                try:
                    listing = self.parse_listing_card(card, resort_name, location)
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

    def parse_listing_card(self, card, resort_name: str = None, location: str = None) -> Optional[Dict]:
        """
        SMTSN result-box 카드 파싱

        SMTSN HTML 구조:
        <div class="result-box result-city-resort-listing">
            <div class="description">
                <div>AD # 100400321</div>
                <h5>Elara, a Hilton Grand Vacations Club</h5>
                <p>...2,560 even year points...</p>
            </div>
            <div class="price-container">
                <span class="price">$8,000</span>
            </div>
            <a href="/timeshares/index/content/details/AdNumber/100400321/sale">...</a>
        </div>

        Args:
            card: BeautifulSoup result-box 요소
            resort_name: 리조트명 (상위에서 전달)
            location: 위치 (상위에서 전달)

        Returns:
            매물 정보 딕셔너리
        """
        listing = {
            'source': self.SOURCE_NAME,
            'scraped_at': datetime.utcnow()
        }

        card_text = card.get_text(separator=' ', strip=True)

        # 1. AD 번호 추출
        ad_match = re.search(r'AD\s*#\s*(\d+)', card_text)
        if not ad_match:
            return None

        ad_number = ad_match.group(1)
        listing['source_id'] = f"smtsn_{ad_number}"

        # 2. URL 추출
        link = card.select_one('a[href*="/timeshares/"]')
        if link:
            listing['listing_url'] = urljoin(self.BASE_URL, link.get('href', ''))
        else:
            listing['listing_url'] = f"{self.BASE_URL}/timeshares/index/content/details/AdNumber/{ad_number}/sale"

        # 3. 가격 추출
        price_elem = card.select_one('[class*=price]')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            listing['asking_price'] = self._extract_number(price_text)
        else:
            # 텍스트에서 첫 번째 $ 가격 추출
            price_match = re.search(r'\$([\d,]+)', card_text)
            if price_match:
                listing['asking_price'] = float(price_match.group(1).replace(',', ''))

        # 4. 포인트 추출 - 카드에서 먼저 시도
        points = None
        points_patterns = [
            r'([\d,]+)\s*(?:even|odd)?\s*(?:year)?\s*points',
            r'([\d,]+)\s*HGVC\s*points',
            r'([\d,]+)\s*Hilton.*?points',
        ]
        for pattern in points_patterns:
            match = re.search(pattern, card_text, re.I)
            if match:
                points = int(match.group(1).replace(',', ''))
                break

        # 카드에서 포인트 못 찾으면 상세 페이지에서 추출 (추정 안 함)
        if not points:
            points = self._fetch_detail_page_points(listing['listing_url'])

        listing['points'] = points  # None일 수 있음

        # 5. 사용 주기 결정
        text_lower = card_text.lower()
        if 'even year' in text_lower:
            listing['usage'] = 'EOY-Even'
        elif 'odd year' in text_lower:
            listing['usage'] = 'EOY-Odd'
        elif 'every other year' in text_lower or 'biennial' in text_lower:
            listing['usage'] = 'EOY'
        else:
            listing['usage'] = 'Annual'

        # 6. 침실 수 추출
        bedroom_match = re.search(r'(\d+)\s*(?:bed(?:room)?|BR)', card_text, re.I)
        if bedroom_match:
            listing['bedrooms'] = int(bedroom_match.group(1))
            listing['unit_type'] = f"{listing['bedrooms']}BR"
        elif 'studio' in text_lower:
            listing['bedrooms'] = 0
            listing['unit_type'] = 'Studio'

        # 7. 리조트명
        listing['resort_name'] = resort_name or 'Unknown HGVC Resort'

        # 8. 시즌 (HGVC는 대부분 Platinum)
        listing['season'] = 'Platinum'

        # 9. 위치
        listing['location'] = location or self._infer_location(resort_name or '')

        # 10. 리조트명 정규화
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
        name = re.sub(r',?\s*a Hilton.*$', '', name, flags=re.I)
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
    scraper = SMTSNScraper()
    listings = scraper.scrape_listings()
    print(f"\n총 {len(listings)}개 매물 발견")
    print()
    for listing in listings[:10]:
        print(f"- {listing.get('resort_name')}")
        print(f"  가격: ${listing.get('asking_price', 'N/A')}, "
              f"포인트: {listing.get('points', 'N/A')}")
        print(f"  위치: {listing.get('location')}, "
              f"사용: {listing.get('usage')}")
        print()
