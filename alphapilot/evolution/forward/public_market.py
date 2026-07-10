"""Public-only market adapter for local forward observation."""

from __future__ import annotations

import pandas as pd

from alphapilot.data_foundation.okx_public import OkxPublicClient


class OkxForwardPublicMarket:
    def __init__(self, client: OkxPublicClient | None = None) -> None:
        self.client = client or OkxPublicClient()

    def completed_candles(
        self, instrument_id: str, timeframe: str, *, limit: int = 300
    ) -> pd.DataFrame:
        return self.client.latest_completed_candles(
            instrument_id=instrument_id,
            timeframe=timeframe,
            limit=limit,
        )
