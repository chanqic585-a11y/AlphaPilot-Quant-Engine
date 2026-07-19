from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from alphapilot.scripts.backfill_v36_okx_funding_history import run


class _Client:
    def historical_market_data(self, **_: object) -> list[dict[str, object]]:
        return [
            {
                "details": [
                    {
                        "groupDetails": [
                            {
                                "filename": (
                                    "BTC-USDT-SWAP-fundingrates-2025-01.zip"
                                ),
                                "url": (
                                    "https://static.okx.com/funding/"
                                    "BTC-USDT-SWAP-fundingrates-2025-01.zip"
                                ),
                            }
                        ]
                    }
                ]
            }
        ]


def _archive() -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "BTC-USDT-SWAP-fundingrates-2025-01.csv",
            "instrument_name,funding_rate,funding_time\n"
            "BTC-USDT-SWAP,0.0001,1735689600000\n",
        )
    return stream.getvalue()


def test_cli_run_backfills_requested_instrument(tmp_path: Path) -> None:
    result = run(
        [
            "--warehouse-root",
            str(tmp_path),
            "--begin",
            "2025-01-01T00:00:00Z",
            "--end",
            "2025-01-31T00:00:00Z",
            "--observed-at",
            "2026-07-19T00:00:00Z",
            "--instrument-id",
            "BTC-USDT-SWAP",
        ],
        client=_Client(),
        archive_loader=lambda _: _archive(),
    )

    assert result["status"] == "completed"
    assert result["completedArchiveCount"] == 1
    assert result["publicDataOnly"] is True
    assert Path(str(result["manifestPath"])).is_file()
