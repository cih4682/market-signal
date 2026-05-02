"""네이버 스마트스토어 / 브랜드스토어 리뷰 크롤러."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from typing import Callable, Optional
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests


REVIEW_API = "https://smartstore.naver.com/i/v1/reviews/paged-reviews"
PAGE_SIZE = 20
IMPERSONATE_TARGET = "chrome131"

SORT_MAP = {
    "랭킹순": "REVIEW_RANKING",
    "최신순": "REVIEW_CREATE_DATE_DESC",
    "별점 높은순": "REVIEW_SCORE_DESC",
    "별점 낮은순": "REVIEW_SCORE_ASC",
}


@dataclass
class NaverReview:
    nickname: str
    rating: int
    date: str
    option: str
    content: str
    helpful: int


def parse_naver_url(url: str) -> tuple[str, str, str]:
    """네이버 스마트스토어/브랜드스토어 URL에서 (host_kind, store, productNo) 추출.

    지원 URL:
      - https://smartstore.naver.com/{store}/products/{productNo}
      - https://brand.naver.com/{store}/products/{productNo}
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("네이버 상품 URL을 입력해주세요.")

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    if host == "smartstore.naver.com":
        host_kind = "smartstore"
    elif host == "brand.naver.com":
        host_kind = "brand"
    else:
        raise ValueError("네이버 스마트스토어 또는 브랜드스토어 URL이어야 합니다.")

    m = re.match(r"^/([^/]+)/products/(\d+)", parsed.path)
    if not m:
        raise ValueError("URL에서 상품 번호(productNo)를 찾을 수 없습니다.")

    store, product_no = m.group(1), m.group(2)
    return host_kind, store, product_no


def _product_url(host_kind: str, store: str, product_no: str) -> str:
    base = "https://smartstore.naver.com" if host_kind == "smartstore" else "https://brand.naver.com"
    return f"{base}/{store}/products/{product_no}"


def create_session(host_kind: str, store: str, product_no: str):
    """브랜드 홈 → 상품 페이지 차례로 방문해 쿠키 확보."""
    session = curl_requests.Session(impersonate=IMPERSONATE_TARGET)
    base = "https://smartstore.naver.com" if host_kind == "smartstore" else "https://brand.naver.com"
    try:
        session.get(f"{base}/{store}", timeout=15)
    except Exception:
        pass
    try:
        session.get(_product_url(host_kind, store, product_no), timeout=15)
    except Exception:
        pass
    return session


def _api_error(response) -> str:
    try:
        data = response.json()
        return data.get("message") or data.get("error") or str(data)[:200]
    except Exception:
        return (response.text or "")[:200]


def _fetch_review_page(
    session,
    host_kind: str,
    store: str,
    product_no: str,
    page: int,
    sort_by: str,
) -> dict:
    body = {
        "productNo": product_no,
        "page": page,
        "pageSize": PAGE_SIZE,
        "reviewSearchSortType": sort_by,
    }
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Referer": _product_url(host_kind, store, product_no),
        "Origin": "https://smartstore.naver.com" if host_kind == "smartstore" else "https://brand.naver.com",
    }
    response = session.post(REVIEW_API, json=body, headers=headers, timeout=20)
    if response.status_code in (400, 401, 403, 404):
        raise PermissionError(f"네이버 API 거부 ({response.status_code}): {_api_error(response)}")
    response.raise_for_status()
    try:
        return response.json()
    except Exception as e:
        raise RuntimeError(f"응답 파싱 실패: {e} · 본문 {response.text[:200]}")


def _parse_reviews(data: dict) -> list[NaverReview]:
    items = data.get("contents") or data.get("reviews") or []
    reviews: list[NaverReview] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        nickname = (
            item.get("writerMemberMaskingId")
            or item.get("writerMemberId")
            or item.get("writerName")
            or ""
        )
        rating = int(item.get("reviewScore") or item.get("rating") or 0)
        date = (item.get("createDate") or item.get("registerDate") or "")[:10]
        option = (
            item.get("productOptionContent")
            or item.get("optionContent")
            or item.get("productName")
            or ""
        )
        content = (item.get("reviewContent") or item.get("content") or "").strip()
        helpful = int(item.get("helpCount") or item.get("likeCount") or 0)

        if not (nickname or content):
            continue

        reviews.append(
            NaverReview(
                nickname=str(nickname).strip() or "익명",
                rating=rating,
                date=date.replace("-", "."),
                option=str(option).strip(),
                content=content,
                helpful=helpful,
            )
        )
    return reviews


def crawl_naver_reviews(
    url: str,
    max_count: int = 100,
    sort_label: str = "랭킹순",
    delay: float = 1.0,
    text_only: bool = False,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> tuple[list[dict], str]:
    """네이버 상품 리뷰를 max_count 만큼 수집한다.

    반환: (리뷰 dict 리스트, productNo)
    """
    host_kind, store, product_no = parse_naver_url(url)
    sort_by = SORT_MAP.get(sort_label, "REVIEW_RANKING")
    session = create_session(host_kind, store, product_no)

    collected: list[NaverReview] = []
    page = 1
    empty_streak = 0

    while len(collected) < max_count:
        data = _fetch_review_page(session, host_kind, store, product_no, page, sort_by)
        page_reviews = _parse_reviews(data)

        if not page_reviews:
            empty_streak += 1
            if empty_streak >= 2:
                break
        else:
            empty_streak = 0
            if text_only:
                page_reviews = [r for r in page_reviews if r.content.strip()]
            if page_reviews:
                collected.extend(page_reviews)
                if progress_cb:
                    progress_cb(min(len(collected), max_count), max_count)

        page += 1
        if page > 500:
            break
        if delay:
            time.sleep(delay)

    return [asdict(r) for r in collected[:max_count]], product_no
