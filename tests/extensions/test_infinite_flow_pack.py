"""预制无限流薄包冒烟（plan §6 Task 1）：真包即 TC-EX 素材源，四例锚定
parse 合法四组 / digest 稳定 / hooks 恰一条规则 / 组模型 required-Optional 形状。"""
from pathlib import Path

import pytest
from pydantic import ValidationError

from snowel_core.extensions.discovery import parse_manifest
from snowel_core.extensions.mounting import Registry, build_group_models, load_hooks

# 真包（R3 主锚）：tests/extensions → tests → 仓库根
PACK_DIR = Path(__file__).parents[2] / "extensions" / "infinite-flow"
GROUPS = {"flow_space_seniority", "flow_rank_track",
          "flow_abilities", "flow_blindspot"}


def test_pack_manifest_parses_clean():
    manifest, warns = parse_manifest(PACK_DIR)
    assert manifest is not None          # 零致命警告（致命 = manifest 为 None）
    assert warns == []                   # 全字段在映射表内，连建议性警告也无
    assert manifest.name == "infinite-flow"
    assert manifest.version == "1.0.0"
    assert set(manifest.raw["groups"]) == GROUPS


def test_pack_digest_stable():
    first, _ = parse_manifest(PACK_DIR)
    second, _ = parse_manifest(PACK_DIR)
    assert first is not None and second is not None
    assert first.schema_digest == second.schema_digest  # 内容即身份


def test_pack_hook_loads_single_rule():
    entries, warns = load_hooks(PACK_DIR)
    assert warns == []
    assert [(name, tiers) for name, _, tiers in entries] == [
        ("flow_rank_track_direction_required", ("full",))]  # R2 默认档
    # EX-② 名字前缀示范：包规则名一律 <组前缀>_
    assert entries[0][0].startswith("flow_")
    # 载荷上限裁决：Registry 注册面只有 rule()
    assert [n for n in dir(Registry) if not n.startswith("_")] == ["rule"]


def test_pack_group_models_build():
    manifest, _ = parse_manifest(PACK_DIR)
    models = build_group_models(manifest)
    assert set(models) == GROUPS

    with pytest.raises(ValidationError):  # required 字段缺构造即炸（§4.1 逐项）
        models["flow_space_seniority"](cycles=17)
    with pytest.raises(ValidationError):
        models["flow_rank_track"](peak_rank=10000)
    with pytest.raises(ValidationError):
        models["flow_abilities"](source="副本奖励")
    with pytest.raises(ValidationError):
        models["flow_blindspot"](exploited=True)

    with pytest.raises(ValidationError):  # enum 字段非法值即炸
        models["flow_space_seniority"](entered_at="首夜", status="retired")
    with pytest.raises(ValidationError):
        models["flow_rank_track"](current_rank=1, direction="sideways")

    senior = models["flow_space_seniority"](entered_at="首夜")
    assert senior.status is None          # optional 字段缺省 None
    track = models["flow_rank_track"](current_rank=480000)
    assert track.direction is None        # direction 刻意 optional（R2 规则管语义）
    assert models["flow_rank_track"](
        current_rank=1, direction="held").direction == "held"

    abilities = models["flow_abilities"](abilities=["时滞"])
    assert abilities.abilities == ["时滞"]
    blind = models["flow_blindspot"](description="已死过一次", exploited=True)
    assert blind.exploited is True
    with pytest.raises(ValidationError):  # pattern 示范在 description（EX-①）
        models["flow_blindspot"](description="")
