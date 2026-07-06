# AlphaPilot V13.5.22 Alpha191 Factor Extraction

This report extracts Alpha191 factor metadata from a user-provided local PDF.
It stores categories, operator tags, required fields, implementation notes, and citation metadata only.
It does not copy full formulas or long source explanations.

## Source Metadata

- title: Alpha 191 因子公式小白学习手册
- sourceType: user_provided_local_pdf_text_extraction
- citation: User-provided local PDF: Alpha191因子公式小白学习手册.pdf, reviewed on 2026-07-06.
- copyrightPolicy: Only URL/path metadata, source summary, citation, categories, operator tags, and short implementation notes are stored; full formulas and long explanations are not copied.

## Extraction Summary

- factorCount: 191
- formulaTextStored: False
- longSourceTextStored: False
- manualReviewFactorCount: 6

## Category Counts

- 量价相关/协同: 47
- 波动振幅/日内结构: 29
- 动量反转/均值回复: 46
- 排序位置/相对强弱: 6
- 成交量/资金活跃: 36
- 市场联动/回归: 8
- 综合价格形态: 13
- 条件统计/规则触发: 6

## Implementation Priority Counts

- high: 123
- medium: 62
- low: 6

## Top Operator Tags

- delay: 76
- rank: 68
- mean: 62
- sum: 49
- corr: 45
- max: 41
- conditional: 32
- sma: 32
- delta: 27
- min: 27
- ts_rank: 17
- decay_linear: 17
- std: 15
- count: 6
- log: 5

## Candidate Clusters

- btc_beta_residual: factors=8, priority={'medium': 8}, next=Use for BTC/ETH beta and residual filters, not equity-index assumptions.
- event_condition_trigger: factors=6, priority={'medium': 6}, next=Use as explicit event gates with walk-forward validation.
- liquidity_activity: factors=36, priority={'high': 36}, next=Use as liquidity gates and thin-market filters before signal selection.
- momentum_reversal: factors=46, priority={'high': 44, 'low': 2}, next=Use as candidate exhaustion and rebound features for fixed 2R historical replay.
- price_pattern_composite: factors=13, priority={'low': 1, 'medium': 12}, next=Use as explainability features in the factor panel before strategy gating.
- relative_strength_rank: factors=6, priority={'medium': 6}, next=Use for universe-wide rank features after dynamic universe quality checks.
- volatility_range_structure: factors=29, priority={'high': 27, 'low': 2}, next=Use as failed-breakout, wick, range compression, and volatility context.
- volume_price_correlation: factors=47, priority={'high': 16, 'low': 1, 'medium': 30}, next=Add as volume-price confirmation overlays for existing high-reward event filters.

## Decision

- alpha191MetadataExtracted: True
- readyForFactorImplementationSpec: True
- exchangeDryRunApproved: False
- liveTradingApproved: False
- nextAction: Design a small crypto-safe Alpha191-inspired factor implementation subset, then evaluate it against existing V13.5 local paper candidate gates.

## Safety Boundary

- Research metadata only.
- No full formula copying.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
