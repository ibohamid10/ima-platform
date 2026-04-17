"""Tests for the YouTube Data API harvester."""

from __future__ import annotations

from decimal import Decimal

import respx
from httpx import Response

from ima.harvesters.exceptions import YouTubeChannelNotFoundError, YouTubeConfigurationError
from ima.harvesters.schemas import YouTubeChannelHarvestRequest
from ima.harvesters.youtube_data_api import YouTubeDataAPIHarvester


async def test_youtube_harvester_requires_api_key() -> None:
    """The live YouTube harvester should fail fast when no API key is configured."""

    harvester = YouTubeDataAPIHarvester(api_key="", base_url="https://example.test")

    try:
        await harvester.harvest_channel(YouTubeChannelHarvestRequest(channel_id="UC123"))
    except YouTubeConfigurationError:
        return

    raise AssertionError("Expected YouTubeConfigurationError when no API key is configured.")


@respx.mock
async def test_youtube_harvester_builds_harvested_creator_record() -> None:
    """The harvester should compose channel, playlist, and video resources into one source record."""

    base_url = "https://example.test"
    harvester = YouTubeDataAPIHarvester(api_key="yt-key", base_url=base_url)

    respx.get(f"{base_url}/channels").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "UC123",
                        "snippet": {
                            "title": "Test Creator",
                            "description": "Hyrox coach and nutrition creator from Vienna.",
                            "customUrl": "@testcreator",
                        },
                        "statistics": {
                            "subscriberCount": "210000",
                        },
                        "contentDetails": {
                            "relatedPlaylists": {
                                "uploads": "UU123",
                            }
                        },
                        "brandingSettings": {
                            "channel": {
                                "defaultLanguage": "en",
                            }
                        },
                    }
                ]
            },
        )
    )
    respx.get(f"{base_url}/playlistItems").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "contentDetails": {"videoId": "vid-1"},
                    },
                    {
                        "contentDetails": {"videoId": "vid-2"},
                    },
                ]
            },
        )
    )
    respx.get(f"{base_url}/videos").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "vid-1",
                        "snippet": {
                            "title": "Hyrox race prep",
                            "description": "Training and race prep.",
                            "publishedAt": "2026-04-16T08:00:00Z",
                            "tags": ["hyrox", "fitness", "training"],
                        },
                        "statistics": {
                            "viewCount": "20000",
                            "likeCount": "1200",
                            "commentCount": "100",
                        },
                    },
                    {
                        "id": "vid-2",
                        "snippet": {
                            "title": "What I eat in race week",
                            "description": "Nutrition and recovery.",
                            "publishedAt": "2026-04-15T08:00:00Z",
                            "tags": ["nutrition", "food"],
                        },
                        "statistics": {
                            "viewCount": "10000",
                            "likeCount": "600",
                            "commentCount": "50",
                        },
                    },
                ]
            },
        )
    )

    result = await harvester.harvest_channel(
        YouTubeChannelHarvestRequest(channel_id="UC123", max_videos=5)
    )

    assert result.platform == "youtube"
    assert result.handle == "testcreator"
    assert result.external_id == "UC123"
    assert result.follower_count == 210000
    assert result.primary_language == "en"
    assert result.metric_snapshot is not None
    assert result.metric_snapshot.average_views_30d == 15000
    assert result.metric_snapshot.average_likes_30d == 900
    assert result.metric_snapshot.average_comments_30d == 75
    assert result.metric_snapshot.engagement_rate_30d == Decimal("0.0650")
    assert len(result.content_items) == 2
    assert result.content_items[0].platform_content_id == "vid-1"


@respx.mock
async def test_youtube_harvester_raises_when_channel_missing() -> None:
    """A missing channel response should become a domain-specific not-found error."""

    base_url = "https://example.test"
    harvester = YouTubeDataAPIHarvester(api_key="yt-key", base_url=base_url)

    respx.get(f"{base_url}/channels").mock(return_value=Response(200, json={"items": []}))

    try:
        await harvester.harvest_channel(YouTubeChannelHarvestRequest(channel_id="UC404"))
    except YouTubeChannelNotFoundError:
        return

    raise AssertionError("Expected YouTubeChannelNotFoundError for an empty channel response.")
