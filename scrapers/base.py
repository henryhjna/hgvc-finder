"""
스크래퍼 기본 클래스
Rate limiting, retry 로직, 캐싱 포함
"""
import time
import random
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pathlib import Path

import requests
import requests_cache
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, MAX_RETRIES,
    CACHE_EXPIRE_SECONDS, DEFAULT_HEADERS, DATA_DIR
)


class BaseScraper(ABC):
    """
    스크래퍼 추상 기본 클래스

    기능:
    - Rate limiting (랜덤 딜레이)
    - Exponential backoff retry
    - 요청 캐싱
    - 공통 HTTP 헤더
    """

    SOURCE_NAME = "base"  # 하위 클래스에서 오버라이드

    def __init__(self, cache_name: str = None, use_cache: bool = False):
        """
        Args:
            cache_name: 캐시 파일명 (기본값: {SOURCE_NAME}_cache)
            use_cache: 캐시 사용 여부 (기본값: False - 캐시 비활성화)
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # 캐시 설정 (선택적)
        if use_cache:
            cache_path = DATA_DIR / f"{cache_name or self.SOURCE_NAME}_cache"
            requests_cache.install_cache(
                str(cache_path),
                backend='sqlite',
                expire_after=CACHE_EXPIRE_SECONDS
            )
        else:
            # 캐시 비활성화
            requests_cache.uninstall_cache()

        # 세션 설정
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _rate_limit(self):
        """요청 간 랜덤 딜레이"""
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        self.logger.debug(f"대기 중: {delay:.2f}초")
        time.sleep(delay)

    def _fetch_with_retry(self, url: str, params: Dict = None) -> Optional[str]:
        """
        URL 가져오기 (재시도 포함)

        Args:
            url: 요청할 URL
            params: 쿼리 파라미터

        Returns:
            HTML 문자열 또는 None (실패 시)
        """
        for attempt in range(MAX_RETRIES):
            try:
                self._rate_limit()
                response = self.session.get(url, params=params, timeout=30)

                # Rate limit 체크
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limit 도달, {retry_after}초 대기")
                    time.sleep(retry_after)
                    continue

                # 403 Forbidden 체크
                if response.status_code == 403:
                    self.logger.warning("접근 거부됨 (403)")
                    wait_time = (2 ** attempt) * 30
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.text

            except requests.Timeout:
                self.logger.error(f"타임아웃 (시도 {attempt + 1}/{MAX_RETRIES})")
            except requests.ConnectionError as e:
                self.logger.error(f"연결 오류: {e}")
            except requests.HTTPError as e:
                self.logger.error(f"HTTP 오류: {e}")
            except Exception as e:
                self.logger.error(f"예상치 못한 오류: {e}")

            # Exponential backoff
            if attempt < MAX_RETRIES - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                self.logger.info(f"{wait_time:.1f}초 후 재시도...")
                time.sleep(wait_time)

        self.logger.error(f"모든 재시도 실패: {url}")
        return None

    def _parse_html(self, html: str) -> BeautifulSoup:
        """
        HTML 파싱

        Args:
            html: HTML 문자열

        Returns:
            BeautifulSoup 객체
        """
        return BeautifulSoup(html, 'lxml')

    def _extract_number(self, text: str) -> Optional[float]:
        """
        텍스트에서 숫자 추출

        Args:
            text: 숫자가 포함된 텍스트 (예: "$1,234.56")

        Returns:
            추출된 숫자 또는 None
        """
        if not text:
            return None
        import re
        # 콤마, 달러 기호 제거 후 숫자 추출
        cleaned = re.sub(r'[,$]', '', text)
        match = re.search(r'[\d.]+', cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None

    @abstractmethod
    def scrape_listings(self, filters: Dict = None) -> List[Dict]:
        """
        매물 스크래핑 (하위 클래스에서 구현 필수)

        Args:
            filters: 필터 옵션

        Returns:
            매물 딕셔너리 리스트
        """
        pass

    @abstractmethod
    def parse_listing_card(self, card_element) -> Optional[Dict]:
        """
        개별 매물 카드 파싱 (하위 클래스에서 구현 필수)

        Args:
            card_element: BeautifulSoup 요소

        Returns:
            매물 정보 딕셔너리 또는 None
        """
        pass

    def clear_cache(self):
        """캐시 삭제"""
        requests_cache.clear()
        self.logger.info("캐시 삭제 완료")
