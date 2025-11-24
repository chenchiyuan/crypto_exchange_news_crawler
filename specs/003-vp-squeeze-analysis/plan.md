# Implementation Plan: VP-Squeeze算法支撑压力位计算服务

**Branch**: `003-vp-squeeze-analysis` | **Date**: 2025-11-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-vp-squeeze-analysis/spec.md`

## Summary

实现VP-Squeeze算法技术分析服务，通过币安现货API获取K线数据，计算Bollinger Bands和Keltner Channels识别盘整状态（Squeeze），并使用Volume Profile计算支撑位（VAL）和压力位（VAH）。交付为Django management command `vp_analysis`，支持批量分析和JSON输出。

## Technical Context

**Language/Version**: Python 3.12 (项目现有)
**Primary Dependencies**: Django 4.2.8, requests (调用币安API)
**Storage**: SQLite (开发) - 新建VPSqueezeResult模型
**Testing**: pytest (待配置，项目tests/目录已存在)
**Target Platform**: Linux server / macOS
**Project Type**: Django单体应用 - 新增vp_squeeze app
**Performance Goals**: 单币种分析<5秒，批量10币种无性能下降
**Constraints**: 纯Python实现技术指标计算，无NumPy依赖
**Scale/Scope**: TOP 10主流币种，支持1m-1M多周期

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|-----|------|------|
| 零假设原则 | ✅ PASS | 所有需求已通过20个Q&A澄清确认 |
| 小步提交 | ✅ PASS | 计划分阶段实现，每阶段可独立测试 |
| 借鉴现有代码 | ✅ PASS | 复用monitor/twitter app的服务层结构 |
| 简单至上 | ✅ PASS | 纯Python实现，无额外依赖 |
| 测试驱动 | ✅ PASS | 先写测试，后实现 |
| SOLID原则 | ✅ PASS | 服务层分离：数据获取、指标计算、结果输出 |

**Gate Result**: ✅ PASS - 可进入Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/003-vp-squeeze-analysis/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no REST API)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
vp_squeeze/                      # 新建Django app
├── __init__.py
├── apps.py
├── models.py                    # VPSqueezeResult模型
├── admin.py                     # Admin配置
├── services/                    # 服务层
│   ├── __init__.py
│   ├── binance_kline_service.py # 币安K线数据获取
│   ├── indicators/              # 技术指标计算
│   │   ├── __init__.py
│   │   ├── bollinger_bands.py   # BB计算
│   │   ├── keltner_channels.py  # KC计算
│   │   ├── volume_profile.py    # VP计算
│   │   └── utils.py             # SMA/EMA/ATR等基础函数
│   └── vp_squeeze_analyzer.py   # 核心分析器（整合所有指标）
├── management/
│   └── commands/
│       └── vp_analysis.py       # Django command入口
└── migrations/

tests/
├── vp_squeeze/
│   ├── __init__.py
│   ├── test_indicators.py       # 技术指标单元测试
│   ├── test_binance_service.py  # 数据获取测试
│   └── test_analyzer.py         # 集成测试
```

**Structure Decision**: 新建独立`vp_squeeze/` Django app，遵循项目现有的app组织方式（monitor/twitter），服务层按职责分离。

## Complexity Tracking

> 无违规项需要记录
