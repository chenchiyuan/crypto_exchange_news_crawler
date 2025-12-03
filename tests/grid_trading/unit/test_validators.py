"""
validators 单元测试

测试覆盖: T050
"""

import pytest
from django.core.management.base import CommandError
from grid_trading.utils.validators import (
    validate_weights,
    validate_top_n,
    validate_min_volume,
    validate_min_days,
)


def test_validate_weights_valid():
    """测试有效权重"""
    weights = validate_weights("0.2,0.2,0.3,0.3")
    assert len(weights) == 4
    assert sum(weights) == pytest.approx(1.0, abs=1e-6)


def test_validate_weights_invalid_sum():
    """测试权重总和≠1.0"""
    with pytest.raises(CommandError, match="权重总和必须=1.0"):
        validate_weights("0.3,0.3,0.3,0.3")


def test_validate_top_n_out_of_range():
    """测试Top N超范围"""
    with pytest.raises(CommandError, match="必须在3-10之间"):
        validate_top_n(15)

    with pytest.raises(CommandError, match="必须在3-10之间"):
        validate_top_n(2)


def test_validate_min_volume_negative():
    """测试负数流动性阈值"""
    with pytest.raises(CommandError, match="必须大于0"):
        validate_min_volume(-1000)


def test_validate_min_days_negative():
    """测试负数上市天数"""
    with pytest.raises(CommandError, match="必须大于0"):
        validate_min_days(-10)
