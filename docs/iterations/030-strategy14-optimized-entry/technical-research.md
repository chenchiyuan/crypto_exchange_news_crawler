# 技术调研: 策略14-优化买入策略

## 文档信息
- **版本**: 1.0
- **创建日期**: 2026-01-11
- **迭代编号**: 030

## 1. 架构兼容性评估

### 现有架构复用
| 组件 | 复用方式 | 修改需求 |
|------|----------|----------|
| DoublingPositionStrategy | 继承/复制 | 修改价格和金额计算 |
| LimitOrderPriceCalculator | 扩展 | 新增first_gap参数 |
| LimitOrderManager | 直接复用 | 无需修改 |
| StrategyFactory | 扩展 | 添加strategy_id=14分支 |
| run_strategy_backtest | 扩展 | 添加策略14识别 |

### 代码结构
```
strategy_adapter/
├── strategies/
│   ├── __init__.py              # 添加导出
│   └── optimized_entry_strategy.py  # 新建
├── core/
│   └── strategy_factory.py      # 添加strategy_id=14
└── management/commands/
    └── run_strategy_backtest.py # 添加策略14识别
```

## 2. 技术选型

- **基类**: 基于DoublingPositionStrategy修改
- **价格计算**: 内置计算，不复用LimitOrderPriceCalculator
- **金额计算**: 动态计算，支持第5档剩余资金

## 3. 技术风险

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 第5档资金不足 | 低 | 最小金额保护 |
| 价格计算精度 | 低 | 使用Decimal |

## Q-Gate 3: ✅ 通过
