"""Build the complete Alpha191 metadata registry with fail-closed formulas."""

from __future__ import annotations

from alphapilot.evolution.registry.hashing import stable_hash

from .manual_reference import MANUAL_SHA256, REVIEWED_FORMULAS
from .schema import Alpha191Factor


def build_alpha191_registry() -> list[Alpha191Factor]:
    records: list[Alpha191Factor] = []
    for number in range(1, 192):
        reviewed = REVIEWED_FORMULAS.get(number)
        core = {
            "factorId": f"alpha191_{number:03d}",
            "manualSha256": MANUAL_SHA256,
            "manualFormula": reviewed["manual"] if reviewed else None,
            "canonicalFormula": reviewed["canonical"] if reviewed else None,
            "cryptoAdaptation": "reviewed_time_span_mapping" if reviewed else "unresolved",
        }
        records.append(
            Alpha191Factor(
                factor_id=core["factorId"],
                display_name_zh=f"Alpha{number:03d}",
                category_zh=str(reviewed["category"]) if reviewed else "待人工分类",
                manual_page=int(reviewed["page"]) if reviewed else None,
                manual_formula=str(reviewed["manual"]) if reviewed else None,
                vibe_reference=None,
                alpha101_reference=None,
                canonical_formula=str(reviewed["canonical"]) if reviewed else None,
                required_columns=tuple(reviewed["columns"]) if reviewed else (),
                required_operators=tuple(reviewed["operators"]) if reviewed else (),
                windows=tuple(reviewed["windows"]) if reviewed else (),
                cross_sectional=False,
                time_series=bool(reviewed),
                requires_benchmark=False,
                formula_status="一致" if reviewed else "待人工确认",
                crypto_adaptation_status="已审查" if reviewed else "待人工确认",
                implementation_hash=stable_hash(core, prefix="factor_impl"),
                notes_zh=(
                    "公式已对照固定哈希手册；窗口按经济时间跨度映射，禁止机械映射到 5m。"
                    if reviewed
                    else "未完成人工公式与加密适配审查，不可执行。"
                ),
            )
        )
    return records
