# 📚 项目文档目录

本文档目录包含项目的完整文档，按功能分类组织。

## 📁 目录结构

```
docs/
├── README.md                             # 本文档（文档索引）
│
├── 📋 项目概览
│   ├── PROJECT_OVERVIEW.md               # 项目完整概览 (V3.0)
│   ├── PROJECT_SUMMARY.md                # Twitter集成项目总结
│   └── COMPLETE_DEMO.md                  # 完整演示文档
│
├── 🚀 快速开始
│   ├── QUICKSTART.md                     # 快速使用指南
│   └── USAGE_GUIDE.md                    # Twitter + 网格交易 使用指南
│
├── 💹 网格交易系统
│   ├── GRID_TRADING_GUIDE.md             # 网格交易完整指南 (V1/V2/V3)
│   ├── GRID_V2_EDGE_CASES.md             # Grid V2 边界情况处理
│   └── GRID_V3_IMPLEMENTATION.md         # Grid V3 挂单系统实现
│
├── 📈 选币筛选系统
│   ├── DAILY_SCREENING_GUIDE.md          # ⭐ 日历选币Dashboard指南
│   ├── SCREENING_QUICKSTART.md           # 筛选快速入门
│   ├── SCREENING_WORKFLOW.md             # 筛选工作流程
│   ├── MARKET_INDICATORS_GUIDE.md        # 市场指标详解 (VDR/KER/OVR/CVD)
│   ├── SCREENING_DRAWDOWN_INDICATOR.md   # 高点回落指标
│   ├── UPDATE_MARKET_DATA_SCRIPT.md      # 市场数据更新脚本
│   └── features/                         # 筛选系统功能实现文档 ⭐ 新增
│       ├── SCREENING_UNIFICATION_COMPLETION.md    # 筛选命令统一(screen_contracts)
│       ├── MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md  # 资金流数据库集成
│       └── KLINE_CACHE_AND_MONEY_FLOW_FIXES.md   # K线缓存优化与资金流显示修复
│
├── 📊 回测系统
│   ├── BACKTEST_SYSTEM_GUIDE.md          # 回测系统完整指南
│   ├── WEB_BACKTEST_API_GUIDE.md         # Web回测API使用
│   ├── WEB_BACKTEST_PLAYER_GUIDE.md      # Web回测播放器使用
│   └── HOW_TO_VIEW_BACKTEST_RESULTS.md   # 回测结果查看指南
│
├── 🐦 Twitter 分析功能
│   ├── DIRECT_ANALYSIS_GUIDE.md          # 直接分析模式指南
│   ├── TWITTER_FILTER_GUIDE.md           # Twitter 过滤功能指南
│   └── twitter-integration-solution.md   # Twitter集成解决方案
│
├── 📈 VP Squeeze 分析
│   ├── VP_SQUEEZE_GUIDE.md               # VP Squeeze分析指南
│   ├── VP_SQUEEZE_BOX_CONFIDENCE.md      # 箱体置信度分析
│   └── VWAP_ANALYSIS_GUIDE.md            # VWAP分析指南
│
├── 🔔 价格监控系统 ⭐ 新增
│   └── features/price-alert-monitor/
│       ├── README.md                      # 功能总结与概览
│       ├── ARCHITECTURE.md                # 系统架构设计
│       ├── RUN_GUIDE.md                   # 运行指南
│       ├── ADMIN_GUIDE.md                 # 管理员指南
│       ├── STARTUP_GUIDE.md               # 启动指南
│       ├── PUSH_FORMAT_V3.md              # 推送格式v3.0
│       ├── BATCH_PUSH_FEATURE.md          # 批量推送功能
│       ├── VOLATILITY_ENHANCEMENT.md      # 波动率增强
│       ├── BUGFIX_PUSH_FAILURE.md         # Bug修复报告
│       └── BUGFIX_VOLATILITY_AND_DUPLICATE.md  # 防重复修复
│
├── 📮 推送通知系统
│   ├── FOUR_PEAKS_PUSH_GUIDE.md          # 四峰推送指南
│   ├── NOTIFICATION_SETUP.md             # 通知设置文档
│   └── ALERT_PUSH_SERVICE.md             # 新币上线告警
│
└── 🔧 系统配置与部署
    ├── CONDA_SETUP.md                    # Conda环境设置
    ├── DJANGO_ADMIN_GUIDE.md             # Django管理指南
    ├── DAILY_SUMMARY_GUIDE.md            # 每日汇总脚本指南
    └── batch_fetch_guide.md              # 批量抓取指南
```

## 🎯 核心文档

### 💡 项目概览
- **[项目概览](./PROJECT_OVERVIEW.md)** - 项目完整介绍、架构、功能模块 (重要！)
- **[项目总结](./PROJECT_SUMMARY.md)** - Twitter集成功能总结
- **[完整演示](./COMPLETE_DEMO.md)** - 系统功能演示

### 💹 网格交易系统 (重点)
- **[网格交易指南](./GRID_TRADING_GUIDE.md)** - 网格交易系统完整使用说明 (V1/V2/V3对比)
- **[挂单位置优化算法](./entry_algorithm_final.md)** - 做空挂单算法（v3.0最终版）✅ 已实施
- **[网格参数计算原理](./grid_parameters_analysis.md)** - ATR自适应网格参数详解
- **[网格数量优化](./grid_optimization_summary.md)** - 100层网格限制优化方案
- **[Grid V2边界情况](./GRID_V2_EDGE_CASES.md)** - V2策略边界案例分析
- **[Grid V3实现报告](./GRID_V3_IMPLEMENTATION.md)** - 挂单系统实现细节

📁 **归档文档**: 历史版本算法演进请查看 [archive/entry-optimization-evolution/](./archive/entry-optimization-evolution/)

### 📈 选币筛选系统 (重点) ⭐
- **[日历选币Dashboard](./DAILY_SCREENING_GUIDE.md)** - 按交易日筛选标的
  - 默认筛选条件：VDR≥6, 振幅≥50%, EMA99斜率≤-10, 资费≥-10%, 交易量≥5M
  - 前端动态筛选，实时显示 X/531 个标的
  - 支持历史回溯和批量分析
- **[筛选快速入门](./SCREENING_QUICKSTART.md)** - 5分钟上手指南
- **[筛选工作流程](./SCREENING_WORKFLOW.md)** - 完整筛选流程
- **[市场指标详解](./MARKET_INDICATORS_GUIDE.md)** - VDR/KER/OVR/CVD指标原理
- **[筛选命令统一](./features/SCREENING_UNIFICATION_COMPLETION.md)** - ⭐ screen_contracts统一命令
- **[资金流集成](./features/MONEY_FLOW_DATABASE_INTEGRATION_COMPLETE.md)** - 24小时资金流分析
- **[K线缓存与资金流修复](./features/KLINE_CACHE_AND_MONEY_FLOW_FIXES.md)** - 智能增量获取与显示修复

### 📊 回测系统 (重点)
- **[回测系统指南](./BACKTEST_SYSTEM_GUIDE.md)** - 回测框架完整使用
- **[Web回测API](./WEB_BACKTEST_API_GUIDE.md)** - API接口使用
- **[Web回测播放器](./WEB_BACKTEST_PLAYER_GUIDE.md)** - 可视化回测播放器
- **[回测结果查看](./HOW_TO_VIEW_BACKTEST_RESULTS.md)** - 数据可视化分析

### 🐦 Twitter分析系统
- **[使用指南](./USAGE_GUIDE.md)** - Twitter功能完整使用说明
- **[直接分析模式](./DIRECT_ANALYSIS_GUIDE.md)** - AI直接分析模式
- **[Twitter过滤](./TWITTER_FILTER_GUIDE.md)** - 推文时间过滤功能
- **[集成方案](./twitter-integration-solution.md)** - 技术方案文档

### 📈 VP Squeeze分析
- **[VP Squeeze指南](./VP_SQUEEZE_GUIDE.md)** - 成交量价格分析
- **[箱体置信度](./VP_SQUEEZE_BOX_CONFIDENCE.md)** - 置信度分析算法
- **[VWAP分析](./VWAP_ANALYSIS_GUIDE.md)** - 加权平均价格分析

### 🔔 价格监控系统 (新增) ⭐
- **[价格监控功能总结](./features/price-alert-monitor/README.md)** - 完整功能概览
- **[系统架构](./features/price-alert-monitor/ARCHITECTURE.md)** - 架构设计与数据流
- **[运行指南](./features/price-alert-monitor/RUN_GUIDE.md)** - 日常运维操作
- **[管理员指南](./features/price-alert-monitor/ADMIN_GUIDE.md)** - Django Admin使用
- **[启动指南](./features/price-alert-monitor/STARTUP_GUIDE.md)** - 快速启动
- **[推送格式v3.0](./features/price-alert-monitor/PUSH_FORMAT_V3.md)** - 专业交易分析格式
- **[批量推送功能](./features/price-alert-monitor/BATCH_PUSH_FEATURE.md)** - 批量推送优化

**核心特性**:
- ✅ 5种价格触发规则（7天新高/新低、MA20/MA99、分布极值）
- ✅ 批量推送模式（减少89-99%推送频率）
- ✅ 波动率排序（15m振幅累计）
- ✅ 防重复推送（60分钟间隔）
- ✅ 上涨/下跌分类（专业交易分析）
- ✅ 快速判断建议（智能生成操作建议）

## 📖 使用方式

### 新用户（推荐阅读顺序）
1. **[项目概览](./PROJECT_OVERVIEW.md)** - 先了解整体架构和功能
2. **[价格监控系统](./features/price-alert-monitor/README.md)** - ⭐ 实时价格触发告警
3. **[日历选币Dashboard](./DAILY_SCREENING_GUIDE.md)** - ⭐ 学习如何筛选优质标的
4. **[网格交易指南](./GRID_TRADING_GUIDE.md)** - 学习网格交易系统
5. **[回测系统指南](./BACKTEST_SYSTEM_GUIDE.md)** - 学习回测验证

### 高级用户
1. **策略研究**: [网格交易指南](./GRID_TRADING_GUIDE.md) + [回测优化](./BACKTEST_OPTIMIZATION_GUIDE.md)
2. **实时监控**: [使用指南](./USAGE_GUIDE.md) + [Django Admin](./DJANGO_ADMIN_GUIDE.md)
3. **数据分析**: [VP Squeeze指南](./VP_SQUEEZE_GUIDE.md) + [Twitter分析](./USAGE_GUIDE.md)

### 开发者
1. **技术架构**: [项目概览](./PROJECT_OVERVIEW.md) + specs/ 目录
2. **API使用**: [Web回测API](./BACKTEST_API_GUIDE.md)
3. **系统配置**: [Conda环境](./CONDA_SETUP.md) + [Django Admin](./DJANGO_ADMIN_GUIDE.md)

### 运维部署
1. **系统配置**: [Conda环境](./CONDA_SETUP.md) + 通知设置
2. **数据管理**: [批量抓取](./batch_fetch_guide.md) + [每日汇总](./DAILY_SUMMARY_GUIDE.md)
3. **故障排查**: 查看各类故障排查文档

## 🔗 相关链接

- **项目根目录**: `/Users/chenchiyuan/projects/crypto_exchange_news_crawler/`
- **源码目录**:
  - 网格交易: `backtest/`
  - Twitter分析: `twitter/`
  - VP Squeeze: `vp_squeeze/`
- **技术规范**: `specs/` 目录
- **配置文件**: `config/backtest.yaml`

## 📊 模块特性对比

### 网格交易策略对比

| 特性 | V1 (经典网格) | V2 (动态4层) | V3 (挂单系统) |
|------|--------------|--------------|---------------|
| 网格类型 | 固定价格 | 动态计算 | 动态计算 |
| 网格层级 | 2层 | 4层 | 4层 |
| 重复激活 | ❌ | ✅ | ✅ |
| 资金管理 | 简单 | 现金约束 | 三重约束 |
| 挂单功能 | ❌ | ❌ | ✅ |
| 资金锁定 | ❌ | ❌ | ✅ |
| 分级止盈 | ❌ | ✅ | ✅ |

### 回测系统特性

| 功能 | 状态 | 说明 |
|------|------|------|
| 历史数据回测 | ✅ | 基于vectorbt专业回测 |
| Web可视化 | ✅ | 交互式图表和回放 |
| 参数优化 | ✅ | 网格搜索和热力图 |
| 多策略支持 | ✅ | grid/grid_v2/grid_v3 |
| 实时回放 | ✅ | 动态回测过程展示 |

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v3.3.0 | 2024-12-10 | ⭐ 筛选命令统一(screen_contracts)、资金流集成、K线缓存智能增量获取优化 |
| v3.2.0 | 2024-12-09 | ⭐ 新增价格监控系统(v3.0.1)、文档结构重组、清理临时文件 |
| v3.1.0 | 2024-12-08 | 新增日历选币Dashboard、前端动态筛选、文档重组 |
| v3.0.0 | 2024-12-02 | 新增网格交易V3、回测系统、完善文档结构 |
| v2.0.0 | 2024-11-30 | 实现回测框架，优化Twitter分析 |
| v1.0.0 | 2024-11-17 | 初始版本，Twitter集成 |

---
最后更新：2024-12-10
