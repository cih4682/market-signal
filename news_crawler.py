"""뉴스 크롤러 — Google News RSS 기반.

- 검색어 + 다중 키워드 지원 (쉼표 분리)
- 카테고리 사전 정의
- 기간 필터 (when: 연산자)
- 한국어 키워드 빈도 분석
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Callable, Optional
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup


GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


PERIOD_QUERY = {
    "최근 1시간": "when:1h",
    "최근 6시간": "when:6h",
    "최근 24시간": "when:1d",
    "최근 7일": "when:7d",
    "최근 30일": "when:30d",
}


CATEGORIES = {
    "정치": "정치",
    "경제": "경제",
    "사회": "사회",
    "IT · 과학": "IT 과학 기술",
    "생활 · 문화": "생활 문화",
    "세계": "국제 세계",
    "스포츠": "스포츠",
    "연예": "연예",
}


KOREAN_STOPWORDS = {
    "있다", "없다", "이다", "되다", "하다", "한다", "지만", "면서",
    "기자", "뉴스", "보도", "취재", "사진", "영상", "단독", "속보",
    "이번", "지난", "올해", "작년", "최근", "현재", "오늘", "내일",
    "그리고", "하지만", "그러나", "또한", "라고", "이라고", "라는",
    "에서", "으로", "에게", "에는", "이라는", "으로부터",
    "한국", "한겨레", "조선", "동아", "중앙", "매일", "연합", "서울",
    "기사", "관련", "내용", "사실", "정도", "이상", "이하", "수도",
    "년", "월", "일",
}


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
}


def _build_query(query: str, period_label: str) -> str:
    base = (query or "").strip()
    period_suffix = PERIOD_QUERY.get(period_label, "")
    if period_suffix:
        return f"{base} {period_suffix}".strip()
    return base


def _fetch_rss(query: str, period_label: str) -> bytes:
    full_query = _build_query(query, period_label)
    params = {
        "q": full_query,
        "hl": "ko",
        "gl": "KR",
        "ceid": "KR:ko",
    }
    response = requests.get(GOOGLE_NEWS_RSS, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.content


def _parse_rss(xml_bytes: bytes) -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items

    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pubdate = (item.findtext("pubDate") or "").strip()

        source = ""
        src_el = item.find("source")
        if src_el is not None:
            source = (src_el.text or "").strip()
        # Google News 는 거의 항상 "제목 - 언론사" 형태로 title 끝에 언론사명을 붙여 보냄.
        # source 변수 채워졌든 아니든 일관되게 title 에서 분리한다.
        if " - " in title:
            t, s = title.rsplit(" - ", 1)
            s = s.strip()
            if len(s) <= 30 and not any(c.isdigit() for c in s):
                title = t.strip()
                if not source:
                    source = s

        published_dt = None
        try:
            published_dt = parsedate_to_datetime(pubdate)
            if published_dt and published_dt.tzinfo:
                published_dt = published_dt.astimezone()
        except Exception:
            pass
        published_str = (
            published_dt.strftime("%Y-%m-%d %H:%M") if published_dt else pubdate[:16]
        )

        # description은 HTML이 들어 있어 태그 제거
        summary = re.sub(r"<[^>]+>", " ", description)
        summary = re.sub(r"\s+", " ", summary).strip()
        # 종종 summary가 여러 기사 묶음(컨퍼런스성)이라 첫 100자만 사용
        if len(summary) > 280:
            summary = summary[:280] + "…"

        items.append({
            "title": title,
            "summary": summary,
            "source": source or "기타",
            "published_at": published_str,
            "_published_dt": published_dt,
            "url": link,
        })

    return items


ARTICLE_SELECTORS = [
    "article",
    "[itemprop='articleBody']",
    "#articleBody",
    "#article-body",
    "#newsct_article",
    "#dic_area",
    ".article-body",
    ".article_body",
    ".news_view",
    ".news-content",
    ".news-content-body",
    ".article-view-content-div",
    ".content_body",
    "main",
]


def _resolve_url(url: str) -> str:
    """Google News 인코딩 URL을 실제 원문 URL로 디코드. 실패 시 원본 그대로 반환."""
    if "news.google.com" not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder
        result = gnewsdecoder(url, interval=1)
        if isinstance(result, dict) and result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception:
        pass
    return url


def extract_article_content(url: str, timeout: int = 12, max_paragraphs: int = 20) -> str:
    """기사 URL → 본문 텍스트 추출. 사이트별 차이가 있어 여러 셀렉터를 시도한다."""
    if not url:
        return ""
    try:
        url = _resolve_url(url)
        response = requests.get(
            url, headers=HEADERS, timeout=timeout, allow_redirects=True
        )
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"

        soup = BeautifulSoup(response.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "aside", "iframe", "noscript", "form"]):
            tag.decompose()

        candidates = []
        for sel in ARTICLE_SELECTORS:
            found = soup.select(sel)
            if found:
                candidates.extend(found)
                break

        if not candidates:
            candidates = [soup.body or soup]

        paragraphs: list[str] = []
        for el in candidates:
            for p in el.find_all(["p", "div"]):
                if p.find(["p", "div"]):
                    continue
                text = p.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text)
                if 25 <= len(text) <= 1500:
                    paragraphs.append(text)

        if not paragraphs:
            raw = soup.get_text(separator="\n", strip=True)
            for line in raw.split("\n"):
                t = line.strip()
                if 25 <= len(t) <= 1000:
                    paragraphs.append(t)

        # 광고/저작권 문구 등 노이즈 라인 제거
        noise_patterns = re.compile(
            r"(저작권자|무단전재|재배포 금지|기자\s*$|이메일|구독\s*하기|네이버 메인|언론사 선택"
            r"|프린트|인쇄|스크랩|글자\s*크기|폰트\s*크기|Copyright|쿠키|쿠팡|광고\s*문의"
            r"|메일주소|페이스북|트위터|카카오|로그인|회원가입)"
        )
        paragraphs = [p for p in paragraphs if not noise_patterns.search(p)]
        # 한국어 비율이 너무 낮은 라인(메뉴/언어 선택 바 등) 제거
        def _is_meaningful(p: str) -> bool:
            korean = sum(1 for c in p if "가" <= c <= "힣")
            total = sum(1 for c in p if c.isalpha())
            if total == 0:
                return False
            return (korean / total) >= 0.4
        paragraphs = [p for p in paragraphs if _is_meaningful(p)]

        return "\n\n".join(paragraphs[:max_paragraphs]).strip()
    except Exception:
        return ""


def summarize_text(text: str, max_sentences: int = 3) -> str:
    """추출형 요약 — 앞쪽 N문장. 한국어 종결('다.', '요.') 패턴 인식."""
    if not text:
        return ""
    raw = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[다요죠음니까\.\!\?])\s+", raw)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 15]
    if not sentences:
        return raw[:240] + ("…" if len(raw) > 240 else "")
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    return " ".join(sentences[:max_sentences])


def extract_top_keywords(items: list[dict], top_n: int = 12) -> list[tuple[str, int]]:
    """제목에서 한국어/영어 단어 빈도 추출 (불용어 제거)."""
    counter: Counter = Counter()
    for item in items:
        text = item.get("title", "")
        words = re.findall(r"[가-힣]{2,}|[A-Za-z]{3,}", text)
        for w in words:
            wn = w.strip()
            if not wn or wn.isdigit():
                continue
            if wn in KOREAN_STOPWORDS:
                continue
            counter[wn] += 1
    return counter.most_common(top_n)


def _dedupe_by_title(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for it in items:
        key = re.sub(r"\s+", " ", it.get("title", "")).strip()[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return unique


def crawl_news(
    query: str,
    period_label: str = "최근 24시간",
    sort_label: str = "관련도",
    max_count: int = 50,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> tuple[list[dict], list[tuple[str, int]]]:
    """뉴스를 수집해 (items, top_keywords) 튜플 반환.

    query 안에 ',' 또는 ';' 가 들어 있으면 다중 키워드로 분리해 각각 검색 후 병합한다.
    """
    if not (query or "").strip():
        raise ValueError("검색어를 입력해주세요.")

    keywords = [k.strip() for k in re.split(r"[,;]", query) if k.strip()]
    if not keywords:
        keywords = [query.strip()]

    per_kw = max(20, max_count // max(1, len(keywords)) + 10)

    aggregated: list[dict] = []
    for i, kw in enumerate(keywords, start=1):
        try:
            xml_bytes = _fetch_rss(kw, period_label)
            page_items = _parse_rss(xml_bytes)
            aggregated.extend(page_items[:per_kw])
        except Exception:
            continue
        if progress_cb:
            progress_cb(i, len(keywords))

    aggregated = _dedupe_by_title(aggregated)

    if sort_label == "최신순":
        aggregated.sort(
            key=lambda x: x.get("_published_dt") or datetime.min.replace(tzinfo=None),
            reverse=True,
        )

    aggregated = aggregated[:max_count]

    # 직렬화 가능하도록 datetime 제거
    for it in aggregated:
        it.pop("_published_dt", None)

    top_keywords = extract_top_keywords(aggregated)
    return aggregated, top_keywords
