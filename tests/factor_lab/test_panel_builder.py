from pathlib import Path

import pandas as pd

from alphapilot.factor_lab.panel_builder import build_factor_panel


def test_panel_builder_preserves_nan_and_wide_shape(tmp_path: Path) -> None:
    first = tmp_path / "BTC.parquet"
    second = tmp_path / "ETH.parquet"
    dates = pd.to_datetime(["2024-01-01T00:00Z", "2024-01-02T00:00Z"])
    pd.DataFrame(
        {"date": dates, "open": [1.0, 2.0], "high": [2.0, 3.0], "low": [0.5, 1.5], "close": [1.5, 2.5], "volume": [10.0, 20.0]}
    ).to_parquet(first, index=False)
    pd.DataFrame(
        {"date": dates[:1], "open": [3.0], "high": [4.0], "low": [2.0], "close": [3.5], "volume": [30.0]}
    ).to_parquet(second, index=False)

    panel = build_factor_panel({"BTC-USDT-SWAP": first, "ETH-USDT-SWAP": second})

    assert panel.close.shape == (2, 2)
    assert pd.isna(panel.close.loc[dates[1], "ETH-USDT-SWAP"])
    assert panel.returns.columns.tolist() == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
