"""쿠팡 리뷰 크롤러 — 상품 URL을 받아 리뷰 데이터를 수집한다."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from typing import Iterator
from urllib.parse import urlparse, parse_qs

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup


REVIEW_ENDPOINT = "https://www.coupang.com/vp/product/reviews"
PAGE_SIZE = 5  # 쿠팡 기본 페이지 크기


@dataclass
class Review:
    nickname: str
    rating: int
    date: str
    option: str
    headline: str
    content: str
    survey: str
    helpful: int
    verified: bool
    images: str


def parse_product_url(url: str) -> tuple[str, str, str]:
    """쿠팡 상품 URL에서 productId, itemId, vendorItemId를 추출한다."""
    parsed = urlparse(url)
    match = re.search(r"/products/(\d+)", parsed.path)
    if not match:
        raise ValueError("쿠팡 상품 URL이 아닙니다. (productId를 찾을 수 없음)")

    product_id = match.group(1)
    qs = parse_qs(parsed.query)
    item_id = qs.get("itemId", [""])[0]
    vendor_item_id = qs.get("vendorItemId", [""])[0]
    return product_id, item_id, vendor_item_id


IMPERSONATE_TARGET = "chrome131"


def create_session(product_id: str, item_id: str = "", vendor_item_id: str = ""):
    """홈페이지 → 상품 페이지를 차례로 방문해 쿠키를 받아 둔 세션을 만든다.

    curl_cffi 의 chrome131 impersonate 옵션이 TLS / HTTP2 핑거프린트까지
    실제 Chrome 으로 위장해 쿠팡의 봇 탐지(Akamai Bot Manager)를 통과한다.
    """
    session = curl_requests.Session(impersonate=IMPERSONATE_TARGET)

    try:
        session.get("https://www.coupang.com/", timeout=15)
    except Exception:
        pass

    product_url = f"https://www.coupang.com/vp/products/{product_id}"
    params = {}
    if item_id:
        params["itemId"] = item_id
    if vendor_item_id:
        params["vendorItemId"] = vendor_item_id

    try:
        session.get(product_url, params=params, timeout=15)
    except Exception:
        pass

    return session


def _build_referer(product_id: str, item_id: str, vendor_item_id: str) -> str:
    referer = f"https://www.coupang.com/vp/products/{product_id}"
    if item_id:
        referer += f"?itemId={item_id}"
        if vendor_item_id:
            referer += f"&vendorItemId={vendor_item_id}"
    return referer


def _fetch_page_html(
    session,
    product_id: str,
    item_id: str,
    vendor_item_id: str,
    page: int,
    sort_by: str,
    rating_filter: str,
) -> str:
    params = {
        "productId": product_id,
        "page": page,
        "size": PAGE_SIZE,
        "sortBy": sort_by,
        "ratings": rating_filter,
        "q": "",
        "viewType": "pdp",
        "itemId": item_id,
        "vendorItemId": vendor_item_id,
    }
    headers = {
        "Referer": _build_referer(product_id, item_id, vendor_item_id),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = session.get(REVIEW_ENDPOINT, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text


def _text(node) -> str:
    return node.get_text(strip=True) if node else ""


def _extract_rating(article) -> int:
    star = article.select_one(".sdp-review__article__list__info__product-info__star-orange")
    if star and star.has_attr("data-rating"):
        try:
            return int(star["data-rating"])
        except (TypeError, ValueError):
            return 0
    return 0


def _extract_helpful(article) -> int:
    el = article.select_one(".js_reviewArticleHelpfulCount, .sdp-review__article__list__help__count")
    if not el:
        return 0
    raw = re.sub(r"[^\d]", "", el.get_text())
    return int(raw) if raw else 0


def _extract_images(article) -> list[str]:
    imgs = article.select(".sdp-review__article__list__attachment img")
    urls: list[str] = []
    for img in imgs:
        src = img.get("src") or img.get("data-src") or ""
        if src and not src.startswith("data:"):
            if src.startswith("//"):
                src = "https:" + src
            urls.append(src)
    return urls


def _extract_survey(article) -> str:
    rows = article.select(".sdp-review__article__list__survey__row")
    parts: list[str] = []
    for row in rows:
        q = _text(row.select_one(".sdp-review__article__list__survey__row__question"))
        a = _text(row.select_one(".sdp-review__article__list__survey__row__answer"))
        if q or a:
            parts.append(f"{q}: {a}")
    return " · ".join(parts)


def parse_reviews_html(html: str) -> list[Review]:
    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article.sdp-review__article__list")

    reviews: list[Review] = []
    for art in articles:
        nickname = _text(art.select_one(".sdp-review__article__list__info__user__name"))
        if not nickname:
            continue

        rating = _extract_rating(art)
        date = _text(art.select_one(".sdp-review__article__list__info__product-info__reg-date"))
        option = _text(art.select_one(".sdp-review__article__list__info__product-info__name"))
        headline = _text(art.select_one(".sdp-review__article__list__headline"))
        content_el = art.select_one(
            ".sdp-review__article__list__review__content, "
            ".sdp-review__article__list__review > div, "
            ".js_reviewArticleContent"
        )
        content = _text(content_el)
        survey = _extract_survey(art)
        helpful = _extract_helpful(art)

        verified_el = art.select_one(".sdp-review__article__list__info__icon__svg-text")
        verified = "확인" in _text(verified_el) or "인증" in _text(verified_el)

        images = _extract_images(art)

        reviews.append(
            Review(
                nickname=nickname.strip(),
                rating=rating,
                date=date,
                option=option,
                headline=headline,
                content=content,
                survey=survey,
                helpful=helpful,
                verified=verified,
                images=", ".join(images),
            )
        )
    return reviews


def crawl_reviews(
    url: str,
    max_count: int = 100,
    sort_by: str = "ORDER_SCORE_ASC",
    rating_filter: str = "",
    delay: float = 1.2,
    text_only: bool = False,
    progress_cb=None,
) -> list[dict]:
    """리뷰를 max_count 개수만큼 수집해 dict 리스트로 반환한다.

    sort_by: DATE_DESC(최신순) / ORDER_SCORE_ASC(베스트순)
    rating_filter: '' / '1' / '1,2' 등
    text_only: True 면 본문(content)이 비어 있는 리뷰는 제외
    progress_cb(current, total): 진행률 콜백
    """
    product_id, item_id, vendor_item_id = parse_product_url(url)
    session = create_session(product_id, item_id, vendor_item_id)

    collected: list[Review] = []
    page = 1
    empty_streak = 0
    max_pages_no_text = 60  # text_only 모드에서 본문이 계속 안 나오면 멈출 한계

    while len(collected) < max_count:
        html = _fetch_page_html(
            session=session,
            product_id=product_id,
            item_id=item_id,
            vendor_item_id=vendor_item_id,
            page=page,
            sort_by=sort_by,
            rating_filter=rating_filter,
        )
        page_reviews = parse_reviews_html(html)

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
        if page > 200:  # 안전 장치
            break
        if text_only and page > max_pages_no_text and not collected:
            break
        if delay:
            time.sleep(delay)

    return [asdict(r) for r in collected[:max_count]]


def iter_review_pages(
    url: str,
    sort_by: str = "DATE_DESC",
    rating_filter: str = "",
    delay: float = 1.2,
    max_pages: int = 200,
) -> Iterator[list[Review]]:
    """페이지 단위로 리뷰를 yield (제너레이터)."""
    product_id, item_id, vendor_item_id = parse_product_url(url)
    session = create_session(product_id, item_id, vendor_item_id)
    for page in range(1, max_pages + 1):
        html = _fetch_page_html(
            session=session,
            product_id=product_id,
            item_id=item_id,
            vendor_item_id=vendor_item_id,
            page=page,
            sort_by=sort_by,
            rating_filter=rating_filter,
        )
        page_reviews = parse_reviews_html(html)
        if not page_reviews:
            break
        yield page_reviews
        if delay:
            time.sleep(delay)
