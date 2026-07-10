from __future__ import annotations

import unittest

from alphapilot.evolution.data_lineage.point_in_time_validator import (
    DynamicUniverseEvidence,
    FieldAvailability,
    validate_point_in_time,
)


CUTOFF = "2026-01-10T00:00:00+00:00"


class PointInTimeValidatorTests(unittest.TestCase):
    def test_valid_fields_and_historical_universe_snapshot_pass(self) -> None:
        result = validate_point_in_time(
            required_fields=["close", "funding_rate"],
            field_metadata={
                "close": FieldAvailability("close", availableAt="candle_close", delayBars=0),
                "funding_rate": FieldAvailability(
                    "funding_rate", availableAt="publication_time", delayBars=1
                ),
            },
            evaluation_cutoff=CUTOFF,
            data_snapshot_manifest={
                "dataSnapshotId": "snapshot_1",
                "pointInTimeCutoff": "2026-01-09T23:00:00+00:00",
            },
            dynamic_universe=DynamicUniverseEvidence(
                enabled=True,
                snapshotId="snapshot_1",
                snapshotAsOf="2026-01-09T23:00:00+00:00",
            ),
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.checkedFields, ["close", "funding_rate"])
        self.assertTrue(result.dynamicUniverseValidated)

    def test_missing_metadata_and_forward_label_fail_closed(self) -> None:
        missing = validate_point_in_time(
            required_fields=["close"],
            field_metadata={},
            evaluation_cutoff=CUTOFF,
        )
        label = validate_point_in_time(
            required_fields=["forward_return_12"],
            field_metadata={
                "forward_return_12": FieldAvailability(
                    "forward_return_12", role="forward_label", availableAt="future"
                )
            },
            evaluation_cutoff=CUTOFF,
        )

        self.assertIn("missing_availability_metadata", [item.code for item in missing.issues])
        self.assertIn("forward_label_as_factor_input", [item.code for item in label.issues])

    def test_future_column_injection_is_rejected(self) -> None:
        result = validate_point_in_time(
            required_fields=["close", "future_leak"],
            field_metadata={
                "close": FieldAvailability("close", availableAt="candle_close", delayBars=0),
                "future_leak": FieldAvailability(
                    "future_leak",
                    availableAt="2026-01-11T00:00:00+00:00",
                    relativeOffsetBars=1,
                ),
            },
            evaluation_cutoff=CUTOFF,
        )

        codes = [item.code for item in result.issues]
        self.assertFalse(result.valid)
        self.assertIn("future_offset_forbidden", codes)
        self.assertIn("field_not_available_at_cutoff", codes)

    def test_dynamic_universe_requires_historical_snapshot(self) -> None:
        missing = validate_point_in_time(
            required_fields=["close"],
            field_metadata={"close": FieldAvailability("close", delayBars=0)},
            evaluation_cutoff=CUTOFF,
            dynamic_universe=DynamicUniverseEvidence(enabled=True),
        )
        future = validate_point_in_time(
            required_fields=["close"],
            field_metadata={"close": FieldAvailability("close", delayBars=0)},
            evaluation_cutoff=CUTOFF,
            dynamic_universe=DynamicUniverseEvidence(
                enabled=True,
                snapshotId="snapshot_future",
                snapshotAsOf="2026-01-11T00:00:00+00:00",
            ),
        )

        self.assertIn("dynamic_universe_snapshot_required", [item.code for item in missing.issues])
        self.assertIn("dynamic_universe_snapshot_from_future", [item.code for item in future.issues])

    def test_data_snapshot_cutoff_cannot_exceed_evaluation_cutoff(self) -> None:
        result = validate_point_in_time(
            required_fields=["close"],
            field_metadata={"close": FieldAvailability("close", delayBars=0)},
            evaluation_cutoff=CUTOFF,
            data_snapshot_manifest={
                "dataSnapshotId": "future_snapshot",
                "pointInTimeCutoff": "2026-01-12T00:00:00+00:00",
            },
        )

        self.assertIn("data_snapshot_from_future", [item.code for item in result.issues])

    def test_unknown_availability_policy_fails_closed(self) -> None:
        result = validate_point_in_time(
            required_fields=["close"],
            field_metadata={
                "close": FieldAvailability("close", availableAt="mystery_policy")
            },
            evaluation_cutoff=CUTOFF,
        )

        self.assertIn("invalid_availability_policy", [item.code for item in result.issues])


if __name__ == "__main__":
    unittest.main()
