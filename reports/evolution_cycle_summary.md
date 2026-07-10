# AlphaPilot V13.13.0 Evolution and ML

This cycle performs bounded AST research and stops at shadow research.
It does not fabricate factor values or training labels when registered data is missing.

## Summary

- Cycle: `evolution_cycle_cefd2536455ac979ddbb3d9c55372920eea6da65c59651f9ab48592f9a4f4596`
- Seed factors: 11
- Generated candidates: 48
- Semantic unique: 48
- Newly registered factor definitions: 0
- Correlation filter: blocked_missing_factor_values
- Model training: blocked_missing_registered_training_dataset
- Strategy candidates: 0
- Demo releases: 0
- Maximum lifecycle stage: shadow_research

## Generated Research Factors

| Candidate | Mutation | Expression |
| --- | --- | --- |
| `factor_candidate_00a4c620e26c0812befe9f7d473684bbf9a71c6367f9b6fbb920bf8e97039aa8` | field | `safe_divide(safe_subtract(returns_1,lower_band),safe_subtract(upper_band,lower_band))` |
| `factor_candidate_04f39445e2be2c256317a2c8e306b9ebae7860a067a0206f557c73f80b2f6498` | cross | `safe_add(safe_add(cross_sectional_rank(safe_divide(close,rolling_max(high,24))),cross_sectional_rank(safe_divide(volume,rolling_mean(volume,24)))),safe_divide(rolling_mean(volume,24),rolling_mean(volume,72)))` |
| `factor_candidate_0521fc1b3069f2b7246113aacb09a18842977311422a332b54f938f2155724f8` | field | `safe_multiply(-1,safe_divide(delta(returns_1,3),lag(returns_1,3)))` |
| `factor_candidate_0784fae8d26c5c723e9879464e8646c4b11ac31ecda92e1053dce6bf719e0d20` | cross | `safe_multiply(cross_sectional_rank(quote_volume),safe_divide(rolling_mean(volume,24),rolling_mean(volume,72)))` |
| `factor_candidate_07ea53931cc214c0d43eb99533faa599e3ee6b4003d16e97f0f69726a8e50f4c` | window | `safe_add(cross_sectional_rank(safe_divide(close,rolling_max(high,6))),cross_sectional_rank(safe_divide(volume,rolling_mean(volume,6))))` |
| `factor_candidate_08e4841af389fba6cb434c3a2e1c86a141948e3c71c144e2389607be88e73ada` | cross | `safe_add(cross_sectional_rank(quote_volume),rolling_std(returns_1,72))` |
| `factor_candidate_118d01c424108a85caefef8bac39d490d65ec2f48ba628c6c7441ed3a86d13df` | cross | `safe_multiply(safe_divide(atr,close),safe_divide(delta(close,12),lag(close,12)))` |
| `factor_candidate_13adf435cf52fd96601e69f323ea574deaf5d127815c7e6cd89510a9adf61962` | cross | `safe_multiply(safe_divide(atr,close),safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)))` |
| `factor_candidate_14cf841455a99ec9930fdc44149e5bfed6d98aef454e03da07676bf930b17c59` | cross | `safe_multiply(rolling_std(returns_1,24),safe_divide(delta(close,12),lag(close,12)))` |
| `factor_candidate_18534e45061294a746dd51858d9377aff146fda7da4480a16e27fe9d4d36ef79` | cross | `safe_add(rolling_std(returns_1,24),safe_divide(delta(close,12),lag(close,12)))` |
| `factor_candidate_1a994a783137248ace4f976af8e5231ad35e9c93df642a2bcc0c0c366f6befac` | window | `safe_divide(rolling_mean(volume,72),rolling_mean(volume,72))` |
| `factor_candidate_1b0ef035b3bcfe1818325b41fdeccacfed53d4434c7f8d0a517d60832fc34142` | cross | `safe_add(cross_sectional_rank(quote_volume),safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)))` |
| `factor_candidate_1d6115759b17665f3e62c85b23e0783b3797ef7863f84ffe4e78776df5457b4c` | cross | `safe_add(safe_divide(atr,close),safe_divide(delta(close,3),lag(close,3)))` |
| `factor_candidate_21362d7a4f36a23fa9d9862ebfea59b578a73d64a5d1b7870c1f7e1b237c519e` | cross | `safe_add(cross_sectional_rank(quote_volume),rolling_std(returns_1,24))` |
| `factor_candidate_227534c7a6a637263368a37f67c43bbd4ffe50a0fea7607aad4a02f294bd7b9c` | cross | `safe_multiply(safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)),safe_divide(volume,rolling_mean(volume,24)))` |
| `factor_candidate_23206aced9a212fcbc3a3d7d01757d3ab894fe4338917a43f4d8797c059e3384` | cross | `safe_multiply(safe_divide(rolling_mean(volume,24),rolling_mean(volume,72)),safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)))` |
| `factor_candidate_284539915a944086362130b1cf8eec1fa9b37bfeb0d512e6263240715f2e02f1` | cross | `safe_add(safe_add(cross_sectional_rank(safe_divide(close,rolling_max(high,24))),cross_sectional_rank(safe_divide(volume,rolling_mean(volume,24)))),safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)))` |
| `factor_candidate_2a44c3a2fd8ce91eeb9138164cd3656e660e36c64e99f493dd316b18eba4abb3` | cross | `safe_add(rolling_std(returns_1,24),safe_multiply(-1,safe_divide(delta(close,3),lag(close,3))))` |
| `factor_candidate_2c7b5da597193def1b75169767fd3f841e2f31b3cb70aab42b8f376cd428d2bb` | window | `safe_divide(rolling_mean(volume,48),rolling_mean(volume,48))` |
| `factor_candidate_2cb483416aee12f69b9d217c0aaf215e5a2965fac96d8aa57c48a12a987b3903` | cross | `safe_add(safe_divide(delta(close,3),lag(close,3)),safe_divide(volume,rolling_mean(volume,24)))` |
| `factor_candidate_2d314e9e40fc4c3791e5450b1eab5faa6b3ad55c3dac64add258dc9828a004cb` | cross | `safe_multiply(rolling_std(returns_1,72),safe_multiply(-1,safe_divide(delta(close,3),lag(close,3))))` |
| `factor_candidate_30fc8ef76501bc05808057a4f40eb9e0c2c6405b135b0eaf963cd6af5487eba5` | cross | `safe_add(safe_divide(delta(close,12),lag(close,12)),safe_multiply(-1,safe_divide(delta(close,3),lag(close,3))))` |
| `factor_candidate_335b60274c926ad2e4491207cc695cfcae29fe495e615590fe0a556ab896a02f` | cross | `safe_multiply(cross_sectional_rank(quote_volume),safe_divide(volume,rolling_mean(volume,24)))` |
| `factor_candidate_3512a9e57f48e14813b2480fe07477cb0e1308e5c267e846b6449e088f2bd52b` | cross | `safe_add(safe_divide(atr,close),safe_divide(rolling_mean(volume,24),rolling_mean(volume,72)))` |
| `factor_candidate_361cf78817094e769d0b82bdb61b27d284efc210e0cf60505d7d4050295e3af9` | cross | `safe_multiply(safe_add(cross_sectional_rank(safe_divide(close,rolling_max(high,24))),cross_sectional_rank(safe_divide(volume,rolling_mean(volume,24)))),safe_divide(delta(close,3),lag(close,3)))` |
| `factor_candidate_36da6eef8200f1912a43051aad927c2bbcaf6b58b8a43aa547e6123e2c5b8ad6` | cross | `safe_add(safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)),safe_divide(volume,rolling_mean(volume,24)))` |
| `factor_candidate_389cf62cc7dd02184094f1dc1621fdd6bca356e0813edab15f714e28ca5ec156` | cross | `safe_add(safe_divide(delta(close,12),lag(close,12)),safe_divide(delta(close,3),lag(close,3)))` |
| `factor_candidate_38d40413bd6de5ba87254e1a18a6b7e00198d2fb3c76fede041644d5baa900b2` | field | `safe_multiply(-1,safe_divide(delta(volume,3),lag(volume,3)))` |
| `factor_candidate_38e847a11a055dda0e04013527a9d2e39bea3711599336c79c3823b981cadddc` | cross | `safe_multiply(cross_sectional_rank(quote_volume),safe_multiply(-1,safe_divide(delta(close,3),lag(close,3))))` |
| `factor_candidate_39122dfc766007a412797359ab233bcb2e07b3f92ccc143f1e965e223a738e87` | window | `safe_multiply(-1,safe_divide(delta(close,48),lag(close,48)))` |
| `factor_candidate_3a37d3d86c9729018440e863cfa177d8ee1f5a604a54f00fcc7932d2b18eaf80` | field | `safe_divide(delta(returns_1,3),lag(returns_1,3))` |
| `factor_candidate_3bf42869461413dddbb3037b95e07bbf0001607adcd5bfa59d86ab78850a649e` | cross | `safe_add(safe_divide(atr,close),safe_multiply(-1,safe_divide(delta(close,3),lag(close,3))))` |
| `factor_candidate_3e4859c7484dc6421bb702c787f41bfd718073b711c8796bde8b41c580fcc94d` | cross | `safe_add(safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)),safe_multiply(-1,safe_divide(delta(close,3),lag(close,3))))` |
| `factor_candidate_3f25d46603e7f247a3c352464cb58f1b6342dc5eeac8da653f5cbdb3518ffd9b` | window | `safe_divide(rolling_mean(volume,6),rolling_mean(volume,6))` |
| `factor_candidate_4197d79539ac3ee5cb16fe9ac4618fcb794f3e09c158a4572272497af3688aeb` | cross | `safe_add(rolling_std(returns_1,72),safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)))` |
| `factor_candidate_42ea018d10d9e4f2946deb75f6ec75cee060fa4b794c1345b62e7ce14d43cb3b` | cross | `safe_add(safe_divide(atr,close),safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band)))` |
| `factor_candidate_46184eeaf38a47b05eeb0204bce635c11bc841d2655a45cc9ddfb5bb39a1ab8e` | cross | `safe_multiply(rolling_std(returns_1,72),safe_divide(volume,rolling_mean(volume,24)))` |
| `factor_candidate_463615b37796073763a40bd1181ad5086e808a0d770c688d446d37e8e62ebc0c` | cross | `safe_add(safe_add(cross_sectional_rank(safe_divide(close,rolling_max(high,24))),cross_sectional_rank(safe_divide(volume,rolling_mean(volume,24)))),safe_divide(volume,rolling_mean(volume,24)))` |
| `factor_candidate_47a172d8a29fa5066970edc269f82dc9dbd2314f1c596adb5ea8cd7d35a5b995` | window | `safe_divide(delta(close,48),lag(close,48))` |
| `factor_candidate_49e9510a760f2fa0e01f3e56e6c4250c45e98bf5e54e036c5c3f16297f97d04a` | field | `safe_add(cross_sectional_rank(safe_divide(returns_1,rolling_max(high,24))),cross_sectional_rank(safe_divide(volume,rolling_mean(volume,24))))` |
| `factor_candidate_4b51822ea9c0d347be289be27d55912258201ab64f3081eacd2a271320195431` | cross | `safe_multiply(safe_add(cross_sectional_rank(safe_divide(close,rolling_max(high,24))),cross_sectional_rank(safe_divide(volume,rolling_mean(volume,24)))),safe_divide(delta(close,12),lag(close,12)))` |
| `factor_candidate_4c4f5b64e95d711b1951cdbe3b5bbf5792f42a640c243ffc5e056848b36655d4` | cross | `safe_multiply(cross_sectional_rank(quote_volume),safe_divide(delta(close,12),lag(close,12)))` |
| `factor_candidate_4db400aa09471452dd5094f0eabbfbb8ceec6dd50b4fd574c9166371f4417dfc` | window | `safe_divide(volume,rolling_mean(volume,6))` |
| `factor_candidate_4e747fc347abf6fa9fea4fcff3642f49aac32a9cb6fd2a1e412b36c0bfc207ae` | cross | `safe_add(rolling_std(returns_1,72),safe_divide(delta(close,12),lag(close,12)))` |
| `factor_candidate_50de1a6e45bb67e45aa55399f861fbecb5fa34ef8398993dfa86c8fef3fb943b` | cross | `safe_multiply(rolling_std(returns_1,24),safe_divide(delta(close,3),lag(close,3)))` |
| `factor_candidate_513921d21b5d2123bc3768fa9901f905c2a231fdc75aa091533adaaa489361f9` | field | `safe_divide(quote_volume,rolling_mean(quote_volume,24))` |
| `factor_candidate_544ba1e6a733a4b30db8288df278b655f6e12e22f4b13db4c831c70f0fa3adba` | cross | `safe_add(rolling_std(returns_1,72),safe_multiply(-1,safe_divide(delta(close,3),lag(close,3))))` |
| `factor_candidate_56130cebfcab0b35b7442dd4f9c8dc8ae3bea0b7c9f9b293ed84b86b73246d98` | cross | `safe_multiply(safe_divide(delta(close,12),lag(close,12)),safe_multiply(-1,safe_divide(delta(close,3),lag(close,3))))` |

## Boundary

The Bandit allocates research units only. Model training is blocked until a
registered point-in-time FactorRun, materialized feature matrix, binary label
set, and purged walk-forward manifest are available. No StrategyCandidate,
DemoRelease, live release, or order is created by this cycle.
