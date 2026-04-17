"""YouTube Data API v3 harvester for direct channel imports and keyword discovery."""

from __future__ import annotations

import asyncio
from decimal import ROUND_HALF_UP, Decimal

import httpx

from ima.config import settings
from ima.harvesters.exceptions import (
    YouTubeChannelNotFoundError,
    YouTubeConfigurationError,
    YouTubeDataAPIError,
    YouTubeQuotaExceededError,
)
from ima.harvesters.schemas import (
    HarvestedContentRecord,
    HarvestedCreatorRecord,
    HarvestedMetricSnapshotRecord,
    YouTubeChannelHarvestRequest,
    YouTubeKeywordDiscoveryRequest,
)
from ima.logging import get_logger

logger = get_logger(__name__)


class YouTubeDataAPIHarvester:
    """Harvest creator source data from YouTube Data API v3."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
    ) -> None:
        """Create the harvester with configurable API credentials and retry behavior."""

        self.api_key = api_key if api_key is not None else settings.youtube_data_api_key
        self.base_url = base_url if base_url is not None else settings.youtube_data_api_base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds

    async def harvest_channel(
        self,
        request: YouTubeChannelHarvestRequest,
    ) -> HarvestedCreatorRecord:
        """Harvest one YouTube channel and its most recent uploaded videos."""

        self._require_api_key()

        channel_items = await self._load_channel_details([request.channel_id])
        if not channel_items:
            raise YouTubeChannelNotFoundError(
                f"Kein YouTube-Kanal fuer channel_id={request.channel_id} gefunden."
            )

        return await self._build_creator_record(
            channel=channel_items[0],
            channel_id=request.channel_id,
            max_videos=request.max_videos,
            source_labels=request.source_labels,
        )

    async def discover_channels(
        self,
        request: YouTubeKeywordDiscoveryRequest,
    ) -> list[HarvestedCreatorRecord]:
        """Discover channels from YouTube keyword search and feed them into canonical harvest."""

        self._require_api_key()

        discovered_channel_ids: list[str] = []
        seen_channel_ids: set[str] = set()
        for keyword in request.keywords:
            search_response = await self._request(
                "/search",
                params={
                    "part": "snippet",
                    "q": keyword,
                    "type": "channel",
                    "maxResults": request.max_results_per_keyword,
                    "key": self.api_key,
                    **({"relevanceLanguage": request.language} if request.language else {}),
                    **({"regionCode": request.region} if request.region else {}),
                },
            )
            for item in search_response.get("items", []):
                channel_id = item.get("id", {}).get("channelId")
                if not channel_id or channel_id in seen_channel_ids:
                    continue
                seen_channel_ids.add(channel_id)
                discovered_channel_ids.append(channel_id)

        if not discovered_channel_ids:
            return []

        channel_items = await self._load_channel_details(discovered_channel_ids)
        harvested_records: list[HarvestedCreatorRecord] = []
        for channel in channel_items:
            channel_id = str(channel.get("id"))
            subscriber_count = self._parse_optional_int(
                channel.get("statistics", {}).get("subscriberCount")
            )
            if request.min_subscribers is not None and (
                subscriber_count is None or subscriber_count < request.min_subscribers
            ):
                continue
            if request.max_subscribers is not None and (
                subscriber_count is None or subscriber_count > request.max_subscribers
            ):
                continue

            harvested_records.append(
                await self._build_creator_record(
                    channel=channel,
                    channel_id=channel_id,
                    max_videos=request.max_videos,
                    source_labels=[*request.source_labels, "youtube_search_discovery"],
                )
            )
        return harvested_records

    async def _build_creator_record(
        self,
        *,
        channel: dict[str, object],
        channel_id: str,
        max_videos: int,
        source_labels: list[str],
    ) -> HarvestedCreatorRecord:
        """Build one harvested creator record from a resolved channel resource."""

        uploads_playlist_id = (
            channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        )

        harvested_content: list[HarvestedContentRecord] = []
        recent_video_items: list[dict[str, object]] = []
        if uploads_playlist_id:
            playlist_items = await self._load_upload_playlist_items(
                uploads_playlist_id=uploads_playlist_id,
                max_results=max_videos,
            )
            video_ids = [
                item.get("contentDetails", {}).get("videoId")
                for item in playlist_items
                if item.get("contentDetails", {}).get("videoId")
            ]
            if video_ids:
                recent_video_items = await self._load_video_details(video_ids)
                video_map = {item["id"]: item for item in recent_video_items if item.get("id")}
                for playlist_item in playlist_items:
                    video_id = playlist_item.get("contentDetails", {}).get("videoId")
                    if not video_id or video_id not in video_map:
                        continue
                    harvested_content.append(self._build_content_record(video_map[video_id]))

        channel_snippet = channel.get("snippet", {})
        channel_statistics = channel.get("statistics", {})
        channel_branding = channel.get("brandingSettings", {}).get("channel", {})
        custom_url = self._normalize_custom_url(channel_snippet.get("customUrl"))
        follower_count = self._parse_optional_int(channel_statistics.get("subscriberCount"))

        metric_snapshot = HarvestedMetricSnapshotRecord(
            followers=follower_count,
            average_views_30d=self._average_stat(recent_video_items, "viewCount"),
            average_likes_30d=self._average_stat(recent_video_items, "likeCount"),
            average_comments_30d=self._average_stat(recent_video_items, "commentCount"),
            engagement_rate_30d=self._calculate_engagement_rate(recent_video_items),
            source="youtube_data_api",
        )

        return HarvestedCreatorRecord(
            source="youtube_data_api",
            platform="youtube",
            handle=custom_url or channel_id,
            external_id=channel_id,
            profile_url=f"https://www.youtube.com/channel/{channel_id}",
            display_name=channel_snippet.get("title"),
            bio=channel_snippet.get("description"),
            followers=follower_count,
            language=channel_branding.get("defaultLanguage"),
            source_labels=sorted(set([*source_labels, "youtube_data_api"])),
            metric_snapshot=metric_snapshot,
            content_items=harvested_content,
            raw_payload={
                "channel_id": channel_id,
                "uploads_playlist_id": uploads_playlist_id,
                "video_count_loaded": len(recent_video_items),
                "channel": channel,
            },
        )

    async def _load_channel_details(self, channel_ids: list[str]) -> list[dict[str, object]]:
        """Load one or more channel resources including statistics and branding settings."""

        response = await self._request(
            "/channels",
            params={
                "part": "snippet,statistics,contentDetails,brandingSettings",
                "id": ",".join(channel_ids),
                "key": self.api_key,
            },
        )
        return response.get("items", [])

    async def _load_upload_playlist_items(
        self,
        *,
        uploads_playlist_id: str,
        max_results: int,
    ) -> list[dict[str, object]]:
        """Load recent upload entries from a channel's uploads playlist."""

        response = await self._request(
            "/playlistItems",
            params={
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": min(max_results, 50),
                "key": self.api_key,
            },
        )
        return response.get("items", [])

    async def _load_video_details(self, video_ids: list[str]) -> list[dict[str, object]]:
        """Load video metadata and statistics for the selected recent uploads."""

        response = await self._request(
            "/videos",
            params={
                "part": "snippet,statistics",
                "id": ",".join(video_ids),
                "key": self.api_key,
            },
        )
        return response.get("items", [])

    async def _request(self, path: str, *, params: dict[str, object]) -> dict[str, object]:
        """Execute one YouTube Data API request with quota-aware retry handling."""

        for attempt in range(1, self.max_retries + 1):
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            ) as client:
                response = await client.get(path, params=params)

            if response.status_code == 404:
                raise YouTubeChannelNotFoundError("YouTube-Ressource wurde nicht gefunden.")

            if self._is_quota_error(response):
                if attempt < self.max_retries:
                    delay_seconds = self.backoff_base_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "youtube_quota_backoff",
                        path=path,
                        attempt=attempt,
                        delay_seconds=delay_seconds,
                        status_code=response.status_code,
                    )
                    await asyncio.sleep(delay_seconds)
                    continue
                raise YouTubeQuotaExceededError(
                    f"YouTube API Quota/Rate-Limit erreicht: {response.status_code} {response.text}"
                )

            if response.status_code >= 400:
                raise YouTubeDataAPIError(
                    f"YouTube Data API Fehler {response.status_code}: {response.text}"
                )

            payload = response.json()
            if not isinstance(payload, dict):
                raise YouTubeDataAPIError(
                    "YouTube Data API Antwort hat kein gueltiges JSON-Objekt geliefert."
                )
            return payload

        raise YouTubeQuotaExceededError(
            "YouTube API Quota/Rate-Limit konnte nicht wiederholt werden."
        )

    def _build_content_record(self, item: dict[str, object]) -> HarvestedContentRecord:
        """Map one YouTube video resource to a harvested content record."""

        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        video_id = item.get("id")

        return HarvestedContentRecord(
            platform_content_id=str(video_id) if video_id else None,
            content_type="video",
            url=f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
            title=snippet.get("title"),
            caption=snippet.get("description"),
            published_at=snippet.get("publishedAt"),
            view_count=self._parse_optional_int(statistics.get("viewCount")),
            like_count=self._parse_optional_int(statistics.get("likeCount")),
            comment_count=self._parse_optional_int(statistics.get("commentCount")),
            hashtags=list(snippet.get("tags", [])[:10]) if snippet.get("tags") else [],
            raw_payload=item,
        )

    def _average_stat(self, videos: list[dict[str, object]], field_name: str) -> int | None:
        """Average one integer statistic across the harvested recent videos."""

        values = [
            self._parse_optional_int(item.get("statistics", {}).get(field_name)) for item in videos
        ]
        valid_values = [value for value in values if value is not None]
        if not valid_values:
            return None
        return int(sum(valid_values) / len(valid_values))

    def _calculate_engagement_rate(
        self,
        videos: list[dict[str, object]],
    ) -> Decimal | None:
        """Estimate engagement from recent likes and comments over views."""

        total_views = 0
        total_interactions = 0
        for item in videos:
            statistics = item.get("statistics", {})
            views = self._parse_optional_int(statistics.get("viewCount")) or 0
            likes = self._parse_optional_int(statistics.get("likeCount")) or 0
            comments = self._parse_optional_int(statistics.get("commentCount")) or 0
            total_views += views
            total_interactions += likes + comments

        if total_views <= 0:
            return None

        rate = Decimal(total_interactions) / Decimal(total_views)
        return rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def _is_quota_error(self, response: httpx.Response) -> bool:
        """Return whether the response indicates quota or rate-limit exhaustion."""

        if response.status_code == 429:
            return True
        if response.status_code != 403:
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        reasons = {
            error.get("reason")
            for error in payload.get("error", {}).get("errors", [])
            if isinstance(error, dict)
        }
        return any(
            reason in {"quotaExceeded", "rateLimitExceeded", "userRateLimitExceeded"}
            for reason in reasons
        )

    def _normalize_custom_url(self, value: object) -> str | None:
        """Normalize the channel custom URL into a handle-like string."""

        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip().removeprefix("@")

    def _parse_optional_int(self, value: object) -> int | None:
        """Convert YouTube numeric strings into integers when present."""

        if value in {None, ""}:
            return None
        try:
            return int(str(value))
        except ValueError as exc:
            raise YouTubeDataAPIError(f"Unerwarteter Integer-Wert von YouTube: {value}") from exc

    def _require_api_key(self) -> None:
        """Fail fast when the configured API key is missing."""

        if not self.api_key:
            raise YouTubeConfigurationError(
                "YOUTUBE_DATA_API_KEY fehlt. "
                "Bitte in .env setzen, bevor ein echter YouTube-Import laeuft."
            )
