"""유튜브 댓글 크롤러 — YouTube Data API v3 기반."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, parse_qs

import requests


API_BASE = "https://www.googleapis.com/youtube/v3"


@dataclass
class Comment:
    author: str
    content: str
    like_count: int
    published_at: str
    reply_count: int
    is_reply: bool


def parse_video_id(url: str) -> str:
    """다양한 형태의 유튜브 URL 또는 ID에서 video_id를 추출한다."""
    raw = (url or "").strip()
    if not raw:
        raise ValueError("유튜브 링크를 입력해주세요.")

    # URL 이 아니라 ID(11자) 자체가 들어왔다면 그대로 사용
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", raw):
        return raw

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc.lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    path = parsed.path or ""

    if host == "youtu.be":
        candidate = path.strip("/").split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate

    if host.endswith("youtube.com"):
        if path == "/watch":
            qs = parse_qs(parsed.query)
            v = qs.get("v", [""])[0]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", v):
                return v
        prefixes = ("/embed/", "/shorts/", "/v/", "/live/")
        for p in prefixes:
            if path.startswith(p):
                candidate = path[len(p):].split("/")[0]
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
                    return candidate

    # 마지막 폴백: 11자 ID 패턴 검색
    m = re.search(r"(?:v=|/)([A-Za-z0-9_-]{11})(?:[?&/]|$)", raw)
    if m:
        return m.group(1)

    raise ValueError("유튜브 URL에서 video ID를 찾을 수 없습니다.")


def fetch_video_meta(api_key: str, video_id: str) -> dict:
    """영상 제목 / 채널명을 함께 가져와 결과 파일명에 사용."""
    params = {"part": "snippet,statistics", "id": video_id, "key": api_key}
    r = requests.get(f"{API_BASE}/videos", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", [])
    if not items:
        return {}
    snip = items[0].get("snippet", {})
    stats = items[0].get("statistics", {})
    return {
        "title": snip.get("title", ""),
        "channel": snip.get("channelTitle", ""),
        "comment_count": int(stats.get("commentCount", 0) or 0),
    }


FRIENDLY_REASONS = {
    "quotaExceeded": "오늘 YouTube API 무료 한도(10,000 쿼터)를 모두 사용했습니다. 한국시간 오후 5시에 자동으로 갱신됩니다.",
    "dailyLimitExceeded": "오늘 YouTube API 무료 한도를 모두 사용했습니다. 한국시간 오후 5시에 자동으로 갱신됩니다.",
    "rateLimitExceeded": "요청이 너무 빠릅니다. 잠시 후 다시 시도해 주세요.",
    "userRateLimitExceeded": "요청 빈도가 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
    "keyInvalid": "API 키가 유효하지 않습니다. Google Cloud Console에서 키를 다시 확인해 주세요.",
    "ipRefererBlocked": "이 API 키는 현재 환경에서 사용할 수 없게 제한되어 있습니다. 키 제한 설정을 확인해 주세요.",
    "forbidden": "API 접근이 차단되었습니다. 키 권한 또는 'YouTube Data API v3' 활성화 여부를 확인해 주세요.",
    "videoNotFound": "영상을 찾을 수 없습니다. URL이나 영상 공개 여부를 확인해 주세요.",
    "notFound": "해당 리소스를 찾을 수 없습니다. URL을 다시 확인해 주세요.",
    "commentsDisabled": "이 영상은 댓글이 비활성화되어 있어 수집할 수 없습니다.",
    "videoNotAccessible": "비공개 또는 제한된 영상이라 접근할 수 없습니다.",
    "badRequest": "요청 형식이 잘못되었습니다. URL을 다시 확인해 주세요.",
}


def _api_error_message(response: requests.Response) -> str:
    try:
        body = response.json()
        err = body.get("error", {})
        msg = err.get("message", "") or ""
        details = err.get("errors", [])
        reason = details[0].get("reason") if details else ""

        friendly = FRIENDLY_REASONS.get(reason)
        if friendly:
            return friendly

        return f"{msg} ({reason})" if reason else msg or response.text[:200]
    except Exception:
        return response.text[:200]


def _fetch_thread_page(
    api_key: str,
    video_id: str,
    page_token: str | None,
    order: str,
) -> dict:
    params = {
        "part": "snippet,replies",
        "videoId": video_id,
        "maxResults": 100,
        "order": order,
        "textFormat": "plainText",
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    r = requests.get(f"{API_BASE}/commentThreads", params=params, timeout=15)
    if r.status_code in (400, 401, 403, 404):
        raise PermissionError(f"YouTube API 거부: {_api_error_message(r)}")
    r.raise_for_status()
    return r.json()


def _to_comment(snippet: dict, is_reply: bool, total_reply_count: int) -> Comment:
    return Comment(
        author=snippet.get("authorDisplayName", "").lstrip("@"),
        content=snippet.get("textDisplay", "").strip(),
        like_count=int(snippet.get("likeCount", 0) or 0),
        published_at=(snippet.get("publishedAt") or "")[:10],
        reply_count=total_reply_count,
        is_reply=is_reply,
    )


def crawl_youtube_comments(
    url: str,
    api_key: str,
    max_count: int = 100,
    order: str = "relevance",
    include_replies: bool = True,
    delay: float = 0.0,
    progress_cb=None,
) -> tuple[list[dict], dict]:
    """YouTube Data API v3로 댓글을 max_count 만큼 수집한다.

    order: relevance(추천순) / time(최신순)
    반환: (댓글 dict 리스트, 영상 메타 dict)
    """
    video_id = parse_video_id(url)

    if not api_key or not api_key.strip():
        raise PermissionError("YouTube API Key가 필요합니다.")

    api_key = api_key.strip()
    meta = fetch_video_meta(api_key, video_id)

    collected: list[Comment] = []
    page_token: str | None = None

    while len(collected) < max_count:
        data = _fetch_thread_page(api_key, video_id, page_token, order)
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            snippet_outer = item.get("snippet", {})
            top_snippet = snippet_outer.get("topLevelComment", {}).get("snippet", {})
            total_reply_count = int(snippet_outer.get("totalReplyCount", 0) or 0)
            collected.append(_to_comment(top_snippet, False, total_reply_count))

            if include_replies and item.get("replies"):
                for reply in item["replies"].get("comments", []):
                    if len(collected) >= max_count:
                        break
                    collected.append(_to_comment(reply.get("snippet", {}), True, 0))

            if progress_cb:
                progress_cb(min(len(collected), max_count), max_count)

            if len(collected) >= max_count:
                break

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        if delay:
            time.sleep(delay)

    meta["video_id"] = video_id
    return [asdict(c) for c in collected[:max_count]], meta
