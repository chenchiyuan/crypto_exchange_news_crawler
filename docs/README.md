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
├── 📊 回测系统
│   ├── BACKTEST_SYSTEM_GUIDE.md          # 回测系统完整指南
│   ├── BACKTEST_API_GUIDE.md             # Web回测API使用
│   ├── WEB_BACKTEST_PLAYER_GUIDE.md      # Web回测播放器使用
│   └── BACKTEST_OPTIMIZATION_GUIDE.md    # 参数优化指南
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
├── 📮 推送通知系统
│   ├── FOUR_PEAKS_PUSH_GUIDE.md          # 四峰推送指南
│   ├── NOTIFICATION_SETUP.md             # 通知设置文档
│   └── ALERT_PUSH_SERVICE.md             # 告警推送服务
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

### 📊 回测系统 (重点)
- **[回测系统指南](./BACKTEST_SYSTEM_GUIDE.md)** - 回测框架完整使用
- **[Web回测API](./BACKTEST_API_GUIDE.md)** - API接口使用
- **[Web回测播放器](./WEB_BACKTEST_PLAYER_GUIDE.md)** - 可视化回测播放器
- **[参数优化](./BACKTEST_OPTIMIZATION_GUIDE.md)** - 参数网格搜索和优化

### 🐦 Twitter分析系统
- **[使用指南](./USAGE_GUIDE.md)** - Twitter功能完整使用说明
- **[直接分析模式](./DIRECT_ANALYSIS_GUIDE.md)** - AI直接分析模式
- **[Twitter过滤](./TWITTER_FILTER_GUIDE.md)** - 推文时间过滤功能
- **[集成方案](./twitter-integration-solution.md)** - 技术方案文档

### 📈 VP Squeeze分析
- **[VP Squeeze指南](./VP_SQUEEZE_GUIDE.md)** - 成交量价格分析
- **[箱体置信度](./VP_SQUEEZE_BOX_CONFIDENCE.md)** - 置信度分析算法
- **[VWAP分析](./VWAP_ANALYSIS_GUIDE.md)** - 加权平均价格分析

## 📖 使用方式

### 新用户（推荐阅读顺序）
1. **[项目概览](./PROJECT_OVERVIEW.md)** - 先了解整体架构和功能
2. **[网格交易指南](./GRID_TRADING_GUIDE.md)** - 学习网格交易系统
3. **[回测系统指南](./BACKTEST_SYSTEM_GUIDE.md)** - 学习回测验证
4. **[使用指南](./USAGE_GUIDE.md)** - 学习Twitter分析

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
| v3.0.0 | 2025-12-02 | 新增网格交易V3、回测系统、完善文档结构 |
| v2.0.0 | 2025-11-30 | 实现回测框架，优化Twitter分析 |
| v1.0.0 | 2025-11-17 | 初始版本，Twitter集成 |

---
最后更新：2025-12-02
