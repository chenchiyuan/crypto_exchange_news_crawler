# 筛选系统功能实现文档

本目录包含筛选系统的核心功能实现文档。

## 📁 目录结构

### 筛选命令统一 (screen_contracts)

**主文档**:
- **[SCREENING_UNIFICATION_COMPLETION.md](./SCREENING_UNIFICATION_COMPLETION.md)** - ✅ 完成报告
  - 统一的`screen_contracts`命令
  - 支持实时/单日/批量三种模式
  - 替代旧的`screen_simple`和`screen_by_date`命令

**设计文档**:
- **[SCREENING_UNIFICATION_SOLUTION.md](./SCREENING_UNIFICATION_SOLUTION.md)** - 方案设计与对比

### 资金流分析功能

**主文档**:
- **[MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md](./MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md)** - ✅ 完成报告
  - 24小时资金流分析
  - 数据库持久化
  - 包含大单净流入、资金流强度、大单主导度三个指标

**设计与实现文档**:
- **[MONEY_FLOW_ANALYSIS_SOLUTION.md](./MONEY_FLOW_ANALYSIS_SOLUTION.md)** - 资金流分析方案设计
- **[MONEY_FLOW_FEATURE_SUMMARY.md](./MONEY_FLOW_FEATURE_SUMMARY.md)** - 功能总结
- **[MONEY_FLOW_IN_SCREEN_CONTRACTS.md](./MONEY_FLOW_IN_SCREEN_CONTRACTS.md)** - 在screen_contracts中的集成
- **[MONEY_FLOW_DATABASE_INTEGRATION.md](./MONEY_FLOW_DATABASE_INTEGRATION.md)** - 数据库集成过程文档

### K线缓存与资金流修复

**主文档**:
- **[KLINE_CACHE_AND_MONEY_FLOW_FIXES.md](./KLINE_CACHE_AND_MONEY_FLOW_FIXES.md)** - ✅ 完成报告
  - K线缓存智能增量获取优化
  - 资金流数据显示修复（screening_date字段问题）
  - 两个关键问题的完整修复过程

### 迁移指南

- **[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)** - 从旧命令迁移到新命令的指南

### 价格监控系统

详见子目录 **[price-alert-monitor/](./price-alert-monitor/)**

---

## 🎯 快速导航

### 我是新用户
1. 阅读 **[SCREENING_UNIFICATION_COMPLETION.md](./SCREENING_UNIFICATION_COMPLETION.md)** - 了解统一筛选命令
2. 阅读 **[MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md](./MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md)** - 了解资金流功能

### 我想使用筛选功能
- **命令**: `python manage.py screen_contracts`
- **参数**: 查看 [SCREENING_UNIFICATION_COMPLETION.md](./SCREENING_UNIFICATION_COMPLETION.md) 的使用指南部分

### 我想了解资金流分析
- **指标说明**: 查看 [MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md](./MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md) 的数据分析应用部分
- **数据查询**: 查看同一文档的使用指南部分

### 我遇到了问题
- **K线数据不足**: 查看 [KLINE_CACHE_AND_MONEY_FLOW_FIXES.md](./KLINE_CACHE_AND_MONEY_FLOW_FIXES.md) 的Part 1
- **资金流显示为0**: 查看 [KLINE_CACHE_AND_MONEY_FLOW_FIXES.md](./KLINE_CACHE_AND_MONEY_FLOW_FIXES.md) 的Part 2

---

## 📊 功能状态

| 功能 | 状态 | 完成日期 | 文档 |
|------|------|----------|------|
| screen_contracts统一命令 | ✅ 已完成 | 2025-12-10 | [SCREENING_UNIFICATION_COMPLETION.md](./SCREENING_UNIFICATION_COMPLETION.md) |
| 资金流数据库集成 | ✅ 已完成 | 2025-12-10 | [MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md](./MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md) |
| K线缓存智能增量获取 | ✅ 已完成 | 2025-12-10 | [KLINE_CACHE_AND_MONEY_FLOW_FIXES.md](./KLINE_CACHE_AND_MONEY_FLOW_FIXES.md) |
| 资金流显示修复 | ✅ 已完成 | 2025-12-10 | [KLINE_CACHE_AND_MONEY_FLOW_FIXES.md](./KLINE_CACHE_AND_MONEY_FLOW_FIXES.md) |

---

## 🔗 相关文档

- **上级目录**: [docs/README.md](../README.md) - 项目文档总索引
- **筛选系统使用指南**: [docs/DAILY_SCREENING_GUIDE.md](../DAILY_SCREENING_GUIDE.md)
- **网格策略算法**: [docs/GRID_STRATEGY_ALGORITHM.md](../GRID_STRATEGY_ALGORITHM.md)

---

**最后更新**: 2025-12-10
