"""Temporal client helpers configured for the local IMA stack."""

from __future__ import annotations

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from ima.config import settings


async def get_temporal_client() -> Client:
    """Create a Temporal client that can serialize Pydantic payloads."""

    return await Client.connect(
        settings.temporal_address,
        namespace="default",
        data_converter=pydantic_data_converter,
    )
