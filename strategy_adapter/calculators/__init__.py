"""
策略计算器模块

提供各类策略所需的指标计算器实现。
"""

from strategy_adapter.calculators.empirical_cdf_calculator import EmpiricalCDFCalculator

__all__ = [
    'EmpiricalCDFCalculator',
]
