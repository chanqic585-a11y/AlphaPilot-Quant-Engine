"""Policy records for adopting or rejecting external research material."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


ADOPTION_STATUSES = frozenset(
    {
        "适配采用",
        "参考后重写",
        "仅文档参考",
        "阶段 4 参考",
        "拒绝采用",
        "许可证阻塞",
        "等待审查",
    }
)


@dataclass(frozen=True)
class AdoptionRecord:
    source: str
    frozen_sha: str
    source_module: str
    target_module: str
    copied_code: bool
    license_name: str
    status: str
    adoption_reason: str
    rejection_reason: str
    test_plan: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        return {
            "来源": value["source"],
            "固定SHA": value["frozen_sha"],
            "原模块": value["source_module"],
            "目标AlphaPilot模块": value["target_module"],
            "是否复制代码": value["copied_code"],
            "License": value["license_name"],
            "状态": value["status"],
            "采用理由": value["adoption_reason"],
            "拒绝理由": value["rejection_reason"],
            "测试计划": value["test_plan"],
        }


def validate_adoption_matrix(records: Iterable[AdoptionRecord]) -> list[str]:
    errors: list[str] = []
    for record in records:
        if record.status not in ADOPTION_STATUSES:
            errors.append(f"{record.source}: unknown adoption status")
        if record.copied_code and record.status == "许可证阻塞":
            errors.append(f"{record.source}: blocked-license source cannot copy code")
        if record.copied_code and not record.license_name.strip():
            errors.append(f"{record.source}: copied code requires an identified license")
        if record.status in {"拒绝采用", "许可证阻塞"} and not record.rejection_reason:
            errors.append(f"{record.source}: rejected adoption requires a reason")
    return errors
