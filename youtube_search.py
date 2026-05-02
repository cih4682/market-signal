"""유튜브 트렌드 발굴 — 검색어로 최근 영상을 찾고 break-out 점수로 알고리즘 노출 채널을 찾는다."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import requests


API_BASE = "https://www.googleapis.com/youtube/v3"


SORT_MAP = {"관련도": "relevance", "최신순": "date", "조회순": "viewCount"}
DURATION_MAP = {
    "전체": "any",
    "Shorts (4분 미만)": "short",
    "일반 (4~20분)": "medium",
    "롱폼 (20분+)": "long",
}


FRIENDLY_REASONS = {
    "quotaExceeded": "오늘 YouTube API 무료 한도(10,000 쿼터)를 모두 사용했습니다. 한국시간 오후 5시에 자동으로 갱신됩니다.",
    "dailyLimitExceeded": "오늘 YouTube API 무료 한도를 모두 사용했습니다. 한국시간 오후 5시에 자동으로 갱신됩니다.",
    "rateLimitExceeded": "요청이 너무 빠릅니다. 잠시 후 다시 시도해 주세요.",
    "userRateLimitExceeded": "요청 빈도가 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
    "keyInvalid": "API 키가 유효하지 않습니다. Google Cloud Console에서 키를 다시 확인해 주세요.",
    "ipRefererBlocked": "이 API 키는 현재 환경에서 사용할 수 없게 제한되어 있습니다. 키 제한 설정을 확인해 주세요.",
    "forbidden": "API 접근이 차단되었습니다. 키 권한 또는 'YouTube Data API v3' 활성화 여부를 확인해 주세요.",
    "badRequest": "요청 형식이 잘못되었습니다. 검색어나 옵션을 다시 확인해 주세요.",
    "notFound": "해당 리소스를 찾을 수 없습니다.",
}


def _api_error(response: requests.Response) -> str:
    try:
        body = response.json()
        err = body.get("error", {})
        msg = err.get("message") or response.text[:200]
        details = err.get("errors", [])
        reason = details[0].get("reason") if details else ""

        friendly = FRIENDLY_REASONS.get(reason)
        if friendly:
            return friendly

        return f"{msg} ({reason})" if reason else msg
    except Exception:
        return response.text[:200]


def _check(response: requests.Response, label: str) -> dict:
    if response.status_code in (400, 401, 403, 404):
        raise PermissionError(f"YouTube {label} 거부: {_api_error(response)}")
    response.raise_for_status()
    return response.json()


def parse_iso8601_duration(iso: str) -> int:
    """PT4M32S → 272 (초)."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "PT0S")
    if not m:
        return 0
    h, mn, s = (int(g or 0) for g in m.groups())
    return h * 3600 + mn * 60 + s


def fmt_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def humanize(n: int) -> str:
    if n >= 100_000_000:
        return f"{n/100_000_000:.1f}억"
    if n >= 10_000:
        return f"{n/10_000:.1f}만"
    if n >= 1_000:
        return f"{n/1_000:.1f}천"
    return f"{n:,}"


def _search_video_ids(
    api_key: str,
    query: str,
    days_ago: int,
    order_label: str,
    duration_label: str,
    region: str,
    max_count: int,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> list[str]:
    published_after = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    video_ids: list[str] = []
    page_token: Optional[str] = None

    while len(video_ids) < max_count:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": SORT_MAP.get(order_label, "relevance"),
            "maxResults": min(50, max_count - len(video_ids)),
            "publishedAfter": published_after,
            "regionCode": region,
            "relevanceLanguage": "ko",
            "videoDuration": DURATION_MAP.get(duration_label, "any"),
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        r = requests.get(f"{API_BASE}/search", params=params, timeout=20)
        data = _check(r, "검색")
        items = data.get("items", [])
        for it in items:
            vid = it.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)

        if progress_cb:
            progress_cb(len(video_ids), max_count, "검색 중…")

        page_token = data.get("nextPageToken")
        if not page_token or not items:
            break

    return video_ids[:max_count]


def _fetch_videos_detail(api_key: str, video_ids: list[str]) -> list[dict]:
    """50개씩 묶어서 videos.list."""
    videos: list[dict] = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(chunk),
            "key": api_key,
        }
        r = requests.get(f"{API_BASE}/videos", params=params, timeout=20)
        data = _check(r, "영상 메타")
        for item in data.get("items", []):
            snip = item.get("snippet", {})
            stats = item.get("statistics", {})
            thumbs = snip.get("thumbnails", {})
            thumb = (
                thumbs.get("medium")
                or thumbs.get("high")
                or thumbs.get("default")
                or {}
            ).get("url", "")
            videos.append({
                "video_id": item.get("id", ""),
                "title": snip.get("title", ""),
                "channel_id": snip.get("channelId", ""),
                "channel_title": snip.get("channelTitle", ""),
                "published_at": snip.get("publishedAt", ""),
                "thumbnail_url": thumb,
                "view_count": int(stats.get("viewCount", 0) or 0),
                "like_count": int(stats.get("likeCount", 0) or 0),
                "comment_count": int(stats.get("commentCount", 0) or 0),
                "duration_seconds": parse_iso8601_duration(
                    item.get("contentDetails", {}).get("duration", "PT0S")
                ),
            })
    return videos


def _fetch_channels_subs(api_key: str, channel_ids: list[str]) -> dict[str, int]:
    """채널 ID → 구독자수 매핑 (50개씩 일괄)."""
    subs: dict[str, int] = {}
    unique_ids = list(dict.fromkeys(channel_ids))
    for i in range(0, len(unique_ids), 50):
        chunk = unique_ids[i : i + 50]
        params = {
            "part": "statistics",
            "id": ",".join(chunk),
            "key": api_key,
        }
        r = requests.get(f"{API_BASE}/channels", params=params, timeout=20)
        data = _check(r, "채널 메타")
        for item in data.get("items", []):
            stats = item.get("statistics", {})
            subs[item["id"]] = int(stats.get("subscriberCount", 0) or 0)
    return subs


def search_trends(
    api_key: str,
    query: str,
    days_ago: int = 7,
    order_label: str = "관련도",
    duration_label: str = "전체",
    region: str = "KR",
    min_views: int = 0,
    max_subscribers: Optional[int] = None,
    min_breakout: float = 0.0,
    max_count: int = 50,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> list[dict]:
    """검색어로 영상을 모으고 채널 구독자수까지 합쳐 break-out 점수를 계산한다.

    필터 적용 후 break-out 내림차순으로 정렬해 반환.
    """
    if not (api_key or "").strip():
        raise PermissionError("YouTube API Key가 필요합니다.")
    if not (query or "").strip():
        raise ValueError("검색어를 입력해주세요.")

    api_key = api_key.strip()
    query = query.strip()

    if progress_cb:
        progress_cb(0, max_count, "검색 시작…")

    video_ids = _search_video_ids(
        api_key, query, days_ago, order_label, duration_label, region, max_count, progress_cb
    )
    if not video_ids:
        return []

    if progress_cb:
        progress_cb(len(video_ids), max_count, "영상 정보 조회 중…")
    videos = _fetch_videos_detail(api_key, video_ids)

    if progress_cb:
        progress_cb(len(video_ids), max_count, "채널 정보 조회 중…")
    channel_ids = [v["channel_id"] for v in videos if v.get("channel_id")]
    subs = _fetch_channels_subs(api_key, channel_ids)

    results: list[dict] = []
    for v in videos:
        sub = subs.get(v["channel_id"], 0)
        views = v["view_count"]
        breakout = (views / sub) if sub > 0 else 0.0
        engagement_pct = (
            ((v["like_count"] + v["comment_count"]) / views * 100) if views > 0 else 0.0
        )

        if views < min_views:
            continue
        if max_subscribers is not None and sub > max_subscribers:
            continue
        if breakout < min_breakout:
            continue

        results.append({
            **v,
            "subscriber_count": sub,
            "breakout_score": round(breakout, 2),
            "engagement_score": round(engagement_pct, 2),
            "duration_text": fmt_duration(v["duration_seconds"]),
            "published_date": (v.get("published_at") or "")[:10],
            "video_url": f"https://www.youtube.com/watch?v={v['video_id']}",
            "channel_url": f"https://www.youtube.com/channel/{v['channel_id']}",
        })

    results.sort(key=lambda x: x["breakout_score"], reverse=True)
    return results
