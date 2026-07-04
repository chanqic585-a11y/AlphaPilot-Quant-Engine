"""Alpha factor research design specs.

V13.4.20 keeps this package research-only. It defines schemas and static
design specifications, but it does not load exchange data, run backtests, or
create strategy entries.
"""

from alphapilot.factors.factor_evaluation_schema import build_factor_evaluation_design
from alphapilot.factors.factor_operator_spec import build_factor_operator_subset
from alphapilot.factors.factor_schema import (
    FactorDataPanelConfig,
    FactorDataPanelReport,
    FactorDataField,
    FactorDataPanelSchema,
    FactorDataRow,
    FactorEvaluationMetric,
    ManualFactorSpec,
)
from alphapilot.factors.manual_factor_library import build_manual_factor_library_v01, manual_factor_output_columns

__all__ = [
    "FactorDataPanelConfig",
    "FactorDataPanelReport",
    "FactorDataField",
    "FactorDataPanelSchema",
    "FactorDataRow",
    "FactorEvaluationMetric",
    "ManualFactorSpec",
    "build_factor_evaluation_design",
    "build_factor_operator_subset",
    "build_manual_factor_library_v01",
    "manual_factor_output_columns",
]
