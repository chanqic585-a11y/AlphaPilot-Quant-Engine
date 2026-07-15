from alphapilot.research_screening.campaign_runner import (
    assign_event_partition,
    benjamini_hochberg,
    build_event_contract,
)


BOUNDARY = {
    "developmentStart": "2020-01-01T00:00:00+00:00",
    "developmentEnd": "2021-01-01T00:00:00+00:00",
    "walkForwardStart": "2021-01-01T00:00:00+00:00",
    "walkForwardEnd": "2022-01-01T00:00:00+00:00",
    "holdoutStart": "2022-01-01T00:00:00+00:00",
    "holdoutEnd": "2023-01-01T00:00:00+00:00",
    "walkForwardFolds": [
        {"foldId": "fold_001", "start": "2021-01-01T00:00:00+00:00", "end": "2021-03-15T00:00:00+00:00"},
        {"foldId": "fold_002", "start": "2021-03-15T00:00:00+00:00", "end": "2021-05-27T00:00:00+00:00"},
        {"foldId": "fold_003", "start": "2021-05-27T00:00:00+00:00", "end": "2021-08-08T00:00:00+00:00"},
        {"foldId": "fold_004", "start": "2021-08-08T00:00:00+00:00", "end": "2021-10-20T00:00:00+00:00"},
        {"foldId": "fold_005", "start": "2021-10-20T00:00:00+00:00", "end": "2022-01-01T00:00:00+00:00"},
    ],
}


def test_partition_assignment_applies_embargo_before_each_boundary() -> None:
    assert assign_event_partition(
        "2020-06-01T00:00:00+00:00", BOUNDARY, timeframe="1h", maximum_hold_bars=24
    ) == ("development", "")
    assert assign_event_partition(
        "2020-12-31T12:00:00+00:00", BOUNDARY, timeframe="1h", maximum_hold_bars=24
    ) == ("embargo", "")
    assert assign_event_partition(
        "2021-04-01T00:00:00+00:00", BOUNDARY, timeframe="1h", maximum_hold_bars=24
    ) == ("walk_forward", "fold_002")
    assert assign_event_partition(
        "2022-06-01T00:00:00+00:00", BOUNDARY, timeframe="1h", maximum_hold_bars=24
    ) == ("holdout", "")


def test_event_contract_contains_required_identity_and_evidence_fields() -> None:
    event = build_event_contract(
        raw_event={
            "signalTimestamp": "2021-04-01T00:00:00+00:00",
            "entryTimestamp": "2021-04-01T01:00:00+00:00",
            "exitTimestamp": "2021-04-01T04:00:00+00:00",
            "grossR": 2.0,
            "feesR": 0.1,
            "slippageR": 0.1,
            "fundingR": 0.0,
            "spreadProxyR": 0.1,
            "netR": 1.7,
        },
        candidate={
            "candidateId": "candidate_a",
            "familyId": "family_a",
            "marketMechanismId": "mechanism_a",
            "direction": "long",
            "timeframe": "1h",
            "maximumHoldBars": 24,
            "factorConfirmations": [],
            "factorRanking": [],
            "factorVetoes": [],
            "definitionHash": "candidate_definition_hash",
        },
        symbol="BTC-USDT-SWAP",
        data_hash="data_hash",
        split="walk_forward",
        fold_id="fold_002",
    )

    assert event["hypothesisId"] == "candidate_a"
    assert event["variantId"] == "candidate_a"
    assert event["coreMechanism"] == "mechanism_a"
    assert event["factorRoles"] == {"confirmation": [], "ranking": [], "veto": []}
    assert event["entryReference"] == "next_bar_open"
    assert event["split"] == "walk_forward"
    assert event["foldId"] == "fold_002"
    assert event["dataHash"] == "data_hash"


def test_benjamini_hochberg_is_monotonic_and_bounded() -> None:
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.8])

    assert len(adjusted) == 4
    assert all(0 <= value <= 1 for value in adjusted)
    assert adjusted[0] <= adjusted[1]
    assert adjusted[0] <= adjusted[2]
