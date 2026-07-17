# S01 strategy definition

```json
{
  "candidateId": "s01_bear_idiosyncratic_selloff_recovery_4h",
  "diagnosticOnly": false,
  "exitPolicy": {
    "initialStopMayWiden": false,
    "maximumHoldBars": 24,
    "mode": "hybrid",
    "parameters": {
      "partialAtR": 0.7,
      "partialFraction": 0.4,
      "remainderMode": "structure",
      "structureRule": {
        "absoluteZscoreMaximum": 0.35,
        "kind": "residual_neutral_zone"
      }
    },
    "version": "advisory_r_exit_policy_v1"
  },
  "exitPolicyHash": "exit_policy_aa415db5c0527ec941e87a41eb3779413b2dce6cb6577f00356823fb5be56ba3",
  "familyId": "idiosyncratic_selloff_recovery",
  "semanticFingerprint": "advisory_r_semantic_e5ee388e5f99ba3cacf9cc75f4052538cc9baa910f69ccd18739e988589cbd14",
  "strategyDefinitionHash": "advisory_r_strategy_062a7c3c3bd7b9f8f741c9506a40efabd3225bd57645f093eda0f86901ac2c37",
  "strategyType": "event",
  "timeframe": "4h",
  "variantId": "S01",
  "strategyId": "s01_bear_idiosyncratic_selloff_recovery_4h",
  "displayNameZh": "S01 熊市特异性急跌修复",
  "sourceCampaignId": "advisory_r_v16_correction_8ec939e8f7ce17a3d259c72c134d02",
  "sourceCandidateId": "s01_bear_idiosyncratic_selloff_recovery_4h",
  "parameterChangesAcrossV17": 0,
  "exitPolicyChangesAcrossV17": 0,
  "BearDefinitionChangesAcrossV17": 0,
  "resultIdentityInvalid": false
}
```
