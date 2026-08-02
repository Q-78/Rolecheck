from __future__ import annotations

from rolecheck.normalization import DetectedLanguage, RoleContractNormalizer
from rolecheck.schemas import SourceType


def test_chinese_sections_and_fullwidth_punctuation_are_parsed() -> None:
    prompt = (
        "你是一名审阅员。\n"
        "## 目标\n"
        "评估草稿。\n"
        "## 职责\n"
        "\uff081\uff09核对事实\n"
        "\uff082\uff09检查引用\n"
        "## 成功标准\n"
        "- 每项问题都有证据\n"
        "## 输出\n"
        "- 结构化审阅报告\n"
        "## 禁止行为\n"
        "- 不得编造证据\n"
    )
    result = RoleContractNormalizer().normalize(
        role_id="reviewer", source_initializer="manual", raw_prompt=prompt
    )
    assert result.detected_language is DetectedLanguage.CHINESE
    assert result.draft.role_name == "审阅员"
    assert result.draft.goal == "评估草稿。"
    assert result.draft.responsibilities == ["核对事实", "检查引用"]
    assert result.draft.prohibited_behaviors == ["不得编造证据"]
    assert result.draft.outputs is not None
    assert result.draft.outputs[0].description == "结构化审阅报告"


def test_chinese_inline_directives_use_conservative_rules() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt="必须核对事实。\n不得编造证据。",
    )
    assert result.draft.responsibilities == ["必须核对事实。"]
    assert result.draft.prohibited_behaviors == ["不得编造证据。"]


def test_mixed_language_prompt_is_reported_without_translation() -> None:
    prompt = "目标\uff1aReview the draft.\n输出\uff1aJSON report {findings}"
    result = RoleContractNormalizer().normalize(
        role_id="reviewer", source_initializer="manual", raw_prompt=prompt
    )
    assert result.detected_language is DetectedLanguage.MIXED
    assert result.draft.goal == "Review the draft."
    assert result.draft.outputs is not None
    assert result.draft.outputs[0].description == "JSON report {findings}"
    assert result.draft.outputs[0].required_fields is None


def test_explicit_empty_list_is_distinct_from_missing() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="config",
        raw_prompt="",
        explicit_fields={"responsibilities": []},
    )
    assert result.draft.responsibilities == []
    assert "responsibilities" not in result.missing_fields
    metadata = next(
        item for item in result.field_metadata if item.field_path == "responsibilities"
    )
    assert metadata.status is SourceType.EXPLICIT


def test_nfkc_matching_does_not_change_source_offsets() -> None:
    prompt = "\uff27\uff4f\uff41\uff4c\uff1aReview the draft."
    result = RoleContractNormalizer().normalize(
        role_id="reviewer", source_initializer="manual", raw_prompt=prompt
    )
    assert result.draft.goal == "Review the draft."
    metadata = next(item for item in result.field_metadata if item.field_path == "goal")
    assert metadata.source_spans[0].text == "Review the draft."
