# Implementation Tasks: 做空网格标的量化筛选系统

**Feature**: `001-short-grid-screening`
**Branch**: `001-short-grid-screening`
**Generated**: 2025-12-03
**Status**: Ready for Implementation

## Overview

本文档定义了实现做空网格标的量化筛选系统的完整任务清单。系统通过三维筛选框架（波动率、趋势、资金/持仓）对币安永续合约市场进行量化筛选，计算GSS评分，最终在终端输出Top 5最适合做空网格的标的。

## 任务统计

- **总任务数**: 53个任务
- **Phase 1 (Setup)**: 5个任务
- **Phase 2 (Foundational)**: 8个任务
- **Phase 3 (US1 Core)**: 35个任务
- **Phase 4 (Polish)**: 5个任务
- **预估MVP完成时间**: Phase 1-3 (US1)

---

## Phase 1: Setup & Infrastructure (项目初始化)

**目标**: 建立项目基础结构和依赖环境

### 任务清单

- [X] T001 创建grid_trading Django app: `django-admin startapp grid_trading`
- [X] T002 创建grid_trading/services/目录并添加__init__.py
- [X] T003 创建grid_trading/models/目录并添加__init__.py
- [X] T004 创建grid_trading/utils/目录并添加__init__.py
- [X] T005 创建grid_trading/management/commands/目录并添加__init__.py
- [X] T006 在Django settings.py的INSTALLED_APPS中注册'grid_trading' app
- [X] T007 更新environment.yml添加scipy>=1.11.0, numpy>=1.24.0, pandas>=2.0.0依赖
- [X] T008 运行`conda env update -f environment.yml`安装新依赖
- [X] T009 创建tests/grid_trading目录结构: unit/, integration/, e2e/子目录及__init__.py

**验收标准**:
- Django能识别grid_trading app
- scipy, numpy, pandas成功安装且版本符合要求
- 测试目录结构完整

---

## Phase 2: Foundational Components (基础组件)

**目标**: 实现通用的基础组件和工具函数，这些组件会被所有后续功能使用

### 任务清单

- [X] T010 实现MarketSymbol数据类在grid_trading/models/market_symbol.py (FR-001相关)
  - 定义dataclass包含symbol, exchange, contract_type, listing_date, current_price等字段
  - 实现passes_initial_filter()方法用于初筛验证

- [X] T011 实现VolatilityMetrics数据类在grid_trading/models/volatility_metrics.py (FR-005, FR-006, FR-010.1)
  - 定义dataclass包含natr, ker, vdr, natr_percentile, inv_ker_percentile字段
  - 实现passes_filter()方法
  - 实现warning_flags属性生成警告和优势标记

- [X] T012 实现TrendMetrics数据类在grid_trading/models/trend_metrics.py (FR-011, FR-012, FR-015.1)
  - 定义dataclass包含norm_slope, r_squared, hurst_exponent, z_score, is_strong_uptrend字段
  - 实现passes_filter()方法
  - 实现calculate_trend_score()方法计算趋势评分
  - 实现warning_flags属性

- [X] T013 实现MicrostructureMetrics数据类在grid_trading/models/microstructure_metrics.py (FR-016至FR-021.1)
  - 定义dataclass包含ovr, funding_rate, cvd, cvd_roc, has_cvd_divergence字段
  - 实现passes_filter()方法
  - 实现calculate_micro_score()方法
  - 实现warning_flags属性

- [X] T014 实现ScreeningResult数据类在grid_trading/models/screening_result.py (FR-022, FR-028至FR-032)
  - 定义dataclass整合三维指标
  - 实现from_metrics()工厂方法
  - 实现to_terminal_row()方法用于终端输出格式化

- [X] T015 实现参数验证器在grid_trading/utils/validators.py (FR-027, FR-035)
  - validate_weights()验证权重总和=1.0
  - validate_top_n()验证Top N范围3-10
  - validate_min_volume()验证流动性阈值
  - validate_min_days()验证上市天数

- [X] T016 实现终端输出格式化工具在grid_trading/utils/formatters.py (FR-031至FR-033, FR-036, FR-037)
  - format_config_output()输出配置信息
  - format_pipeline_progress()输出Pipeline进度
  - format_results_table()格式化结果表格
  - format_execution_summary()输出执行摘要

- [X] T017 实现日志配置在grid_trading/utils/__init__.py (FR-041)
  - 配置Django logger
  - 定义INFO/WARNING/ERROR日志级别输出格式

**验收标准**:
- 所有数据模型类可正常导入和实例化
- 参数验证器对无效输入正确抛出异常
- 终端格式化工具输出清晰对齐

---

## Phase 3: User Story 1 - 通过命令筛选出适合的做空网格标的 (Priority: P1)

**用户故事**: 作为量化交易员,我需要运行命令行工具筛选币安永续合约市场中最适合做空网格的标的,通过三维筛选框架计算GSS评分,最终在终端输出Top 5标的及详细指标。

**独立测试**: 运行命令`python manage.py screen_short_grid`,验证终端输出包含Top 5标的代码、GSS得分、三维指标明细和推荐网格参数,完成时间<60秒。

### 3.1 币安Futures API客户端 (Step 1: 数据获取)

- [X] T018 [US1] 实现BinanceFuturesClient基础类在grid_trading/services/binance_futures_client.py (FR-001)
  - 复用monitor/api_clients/binance.py的请求模式
  - 配置Futures API基础URL: https://fapi.binance.com
  - 实现@retry装饰器用于API重试 (FR-040)
  - 实现速率限制装饰器 (1200权重/分钟)

- [X] T019 [US1] 实现fetch_exchange_info()方法获取合约列表 (FR-001)
  - 调用/fapi/v1/exchangeInfo端点
  - 解析返回JSON提取USDT本位永续合约
  - 提取symbol和listing_date字段

- [X] T020 [US1] 实现fetch_24h_ticker()方法获取Ticker数据 (FR-002)
  - 调用/fapi/v1/ticker/24hr端点 (权重40)
  - 提取volume_24h, current_price字段
  - 返回Dict[symbol, ticker_data]

- [X] T021 [US1] 实现fetch_funding_rate()方法获取资金费率 (FR-017)
  - 调用/fapi/v1/fundingRate端点 (权重1)
  - 提取funding_rate, next_funding_time字段
  - 返回Dict[symbol, funding_data]

- [X] T022 [US1] 实现fetch_open_interest()方法获取持仓量 (FR-016)
  - 调用/fapi/v1/openInterest端点 (权重1/标的)
  - 批量请求策略: 每批5个标的,并发3
  - 返回Dict[symbol, open_interest]

- [X] T023 [US1] 实现fetch_klines()方法获取K线数据 (FR-005)
  - 调用/fapi/v1/klines端点
  - 支持interval参数: 1m/4h/1d
  - 提取OHLC + volume + takerBuyBaseAssetVolume (FR-020)
  - 实现并发获取: 每批20个标的,并发3
  - 处理数据缺失edge case (FR-039)

- [X] T024 [US1] 实现fetch_all_market_data()方法整合数据获取 (FR-001至FR-004)
  - 并行调用fetch_exchange_info, fetch_24h_ticker, fetch_funding_rate
  - 执行初筛: 流动性>50M USDT, 上市>30天
  - 对通过初筛的标的并行获取K线和持仓量
  - 返回List[MarketSymbol]
  - 输出初筛统计: 总标的数、通过数、被过滤数 (FR-004)

### 3.2 技术指标计算器 (Step 2: 三维指标计算)

#### 3.2.1 波动率指标 (Volatility Dimension)

- [X] T025 [P] [US1] 实现calculate_natr()在grid_trading/services/indicator_calculator.py (FR-005)
  - 计算真实波幅TR: max(H-L, |H-C_prev|, |L-C_prev|)
  - EMA计算ATR(14)
  - 归一化: NATR = ATR(14) / Close × 100
  - NumPy向量化实现
  - 单元测试: 与TA-Lib误差<0.1% (SC-002)

- [X] T026 [P] [US1] 实现calculate_ker()在grid_trading/services/indicator_calculator.py (FR-006)
  - Direction = |Close_t - Close_{t-10}|
  - Volatility = Σ|Close_{t-i} - Close_{t-i-1}|
  - KER = Direction / Volatility
  - 处理除零edge case

- [X] T027 [P] [US1] 实现calculate_vdr()在grid_trading/services/indicator_calculator.py (FR-010.1)
  - 获取240根1分钟K线
  - 计算CIV = Σ |Close_i - Open_i| / Open_i
  - 计算Displacement = |Close_final - Close_initial| / Close_initial
  - VDR = CIV / Displacement
  - 处理除零: 返回float('inf')
  - Edge case: 1分钟K线数据不足时降级跳过,记录WARNING

- [X] T028 [P] [US1] 实现calculate_percentile_rank()在grid_trading/services/indicator_calculator.py (FR-010)
  - 使用numpy.percentile()
  - 将NATR和(1-KER)转换为0-1排名
  - 返回Dict[symbol, (natr_percentile, inv_ker_percentile)]

#### 3.2.2 趋势指标 (Trend Dimension)

- [X] T029 [P] [US1] 实现calculate_linear_regression()在grid_trading/services/indicator_calculator.py (FR-011)
  - 使用scipy.stats.linregress()
  - 计算标准化斜率: NormSlope = (m / Close_t) × 10000
  - 计算判定系数R²
  - 返回(norm_slope, r_squared)

- [X] T030 [P] [US1] 实现calculate_hurst_exponent()在grid_trading/services/indicator_calculator.py (FR-012)
  - 按research.md中R/S分析算法实现
  - 窗口大小: [10, 20, 30, 50, 100]
  - 线性回归log(R/S) vs log(n)
  - 返回斜率作为Hurst指数
  - Edge case: 数据不足返回0.5 (随机游走)

- [X] T031 [P] [US1] 实现calculate_z_score()在grid_trading/services/indicator_calculator.py (FR-015.1)
  - 计算MA_20: 20周期简单移动平均
  - 计算StdDev_20: 20周期标准差
  - Z_Score = (Close_t - MA_20) / StdDev_20
  - 处理除零: 返回0.0

#### 3.2.3 微观结构指标 (Microstructure Dimension)

- [X] T032 [P] [US1] 实现calculate_ovr()在grid_trading/services/indicator_calculator.py (FR-016)
  - OVR = OpenInterest / 24h Volume
  - 处理除零: 返回0.0

- [X] T033 [P] [US1] 实现calculate_cvd()在grid_trading/services/indicator_calculator.py (FR-020)
  - Delta = TakerBuyVolume - (TotalVolume - TakerBuyVolume)
  - CVD_t = CVD_{t-1} + Delta_t
  - NumPy累积和: np.cumsum()
  - 返回CVD序列

- [X] T034 [P] [US1] 实现detect_cvd_divergence()在grid_trading/services/indicator_calculator.py (FR-021)
  - 窗口期=20
  - price_high_idx = np.argmax(prices[-20:])
  - cvd_high_idx = np.argmax(cvd[-20:])
  - 背离条件: price_high_idx == 19 and cvd_high_idx < 19
  - 返回(cvd_value, has_divergence)

- [X] T035 [P] [US1] 实现calculate_cvd_roc()在grid_trading/services/indicator_calculator.py (FR-021.1)
  - 5周期变化率: CVD_ROC = (CVD_t - CVD_{t-5}) / |CVD_{t-5}|
  - 处理除零: 返回0.0
  - 返回百分比

- [X] T036 [US1] 实现calculate_all_indicators()整合所有指标计算 (FR-005至FR-021.1)
  - 输入: MarketSymbol, klines_4h, klines_1m, klines_1d, klines_1h
  - 调用所有指标计算函数
  - 构建并返回(VolatilityMetrics, TrendMetrics, MicrostructureMetrics)元组
  - 实现ThreadPoolExecutor并行计算 (max_workers=4)
  - 性能目标: 单标的<100ms

### 3.3 评分模型 (Step 3: 加权评分)

- [X] T037 [US1] 实现ScoringModel类在grid_trading/services/scoring_model.py (FR-022至FR-027.1)
  - __init__()接收权重参数w1, w2, w3, w4
  - 验证权重总和=1.0 (FR-027)

- [X] T038 [US1] 实现calculate_gss_score()方法在ScoringModel (FR-022至FR-025)
  - GSS = w₁·Rank(NATR) + w₂·Rank(1-KER) + w₃·I_Trend + w₄·I_Micro
  - 调用TrendMetrics.calculate_trend_score(ker)传入KER用于Z-Score加分 (FR-024)
  - 调用MicrostructureMetrics.calculate_micro_score(vdr)传入VDR (FR-025)
  - 趋势否决机制: 强上升趋势返回GSS=0 (FR-014, SC-007)

- [X] T039 [US1] 实现apply_market_cap_boost()方法在ScoringModel (FR-027.1)
  - 检查market_cap_rank是否在20-100
  - 应用1.2倍加权系数
  - Edge case: 市值数据缺失时返回原GSS

- [X] T040 [US1] 实现calculate_grid_parameters()方法在ScoringModel (FR-030)
  - 计算ATR_daily (基于24小时K线, period=14)
  - 计算ATR_hourly (基于1小时K线, period=14)
  - Upper Limit = Current Price + 2 × ATR_daily
  - Lower Limit = Current Price - 3 × ATR_daily
  - Grid Count = (Upper - Lower) / (0.5 × ATR_hourly)
  - 返回(upper_limit, lower_limit, grid_count)

- [X] T041 [US1] 实现score_and_rank()方法在ScoringModel (FR-028, FR-029)
  - 输入: List[(MarketSymbol, VolatilityMetrics, TrendMetrics, MicrostructureMetrics)]
  - 对所有标的计算GSS评分
  - 应用市值排名加权
  - 按GSS降序排序
  - 提取Top N标的
  - 构建ScreeningResult列表
  - 返回List[ScreeningResult]

### 3.4 筛选引擎 (Step 4: Pipeline主流程)

- [X] T042 [US1] 实现ScreeningEngine类在grid_trading/services/screening_engine.py
  - __init__()接收配置参数: top_n, weights, min_volume, min_days, interval

- [X] T043 [US1] 实现run_screening()主方法在ScreeningEngine
  - Pipeline流程:
    1. 调用BinanceFuturesClient.fetch_all_market_data()获取并初筛数据 (FR-001至FR-004)
    2. 并行调用indicator_calculator.calculate_all_indicators()计算三维指标
    3. 调用ScoringModel.score_and_rank()评分排序 (FR-022至FR-029)
    4. 调用ScoringModel.calculate_grid_parameters()计算网格参数 (FR-030)
    5. 返回List[ScreeningResult]
  - 性能监控: 记录每个阶段耗时
  - 总执行时间<60秒 (SC-001)

- [X] T044 [US1] 实现错误处理和降级逻辑在ScreeningEngine
  - API限流429错误: 自动重试最多60秒 (FR-040)
  - K线数据不足: 跳过标的,记录WARNING (FR-039)
  - TakerBuyVolume缺失: CVD降级为简化计算 (FR-042)
  - 1分钟K线缺失: VDR计算跳过,记录WARNING
  - 全市场无合格标的: 输出明确提示 (SC-008)

### 3.5 Django Management Command (Step 5: 命令行接口)

- [X] T045 [US1] 创建Django Management Command在grid_trading/management/commands/screen_short_grid.py (FR-034)
  - 继承BaseCommand
  - 实现add_arguments()添加命令行参数 (FR-035)
    - --top-n (int, default=5, choices=[3-10])
    - --weights (str, default="0.2,0.2,0.3,0.3")
    - --min-volume (float, default=50000000)
    - --min-days (int, default=30)
    - --interval (str, default="4h", choices=["1h", "4h", "1d"])
    - --verbosity (int, Django标准)

- [X] T046 [US1] 实现handle()方法在screen_short_grid命令
  - 解析并验证命令行参数 (调用validators)
  - 输出配置信息 (FR-036)
  - 创建ScreeningEngine实例
  - 调用run_screening()执行筛选
  - 调用formatters格式化输出 (FR-031至FR-033)
  - 输出执行摘要: 扫描时长、总标的数、通过数、Top N数 (FR-037)
  - 错误处理: 捕获CommandError并友好提示

- [X] T047 [US1] 实现输出格式化在screen_short_grid.handle()
  - 步骤1输出: 全市场扫描与初筛统计 (FR-004)
  - 步骤2输出: 三维指标计算进度 (FR-033)
  - 步骤3输出: 加权评分与排序 (FR-028)
  - 步骤4输出: 格式化表格展示Top N标的 (FR-031)
    - 列: Rank, Symbol, Price, NATR, KER, VDR, H, Z-Score, Slope, R², OVR, Funding, CVD, CVD_ROC, GSS, Grid Upper, Grid Lower, Flags
    - 警告/优势标记显示 (FR-032):
      - ⚠️ 极端波动 (NATR>10%)
      - ⚠️ 高OVR (OVR>2.0)
      - ⚠️ 逼空风险 (Funding>0.1%)
      - ⚠️ CVD异常买盘 (CVD_ROC>50%)
      - ✓ 高VDR - 完美震荡 (VDR>10.0)
      - ✓ 假突破优势 (Z_Score>2.0 且 KER<0.3)

### 3.6 测试 (User Story 1测试)

- [X] T048 [P] [US1] 编写单元测试在tests/grid_trading/unit/test_indicator_calculator.py
  - test_calculate_natr_accuracy: 与TA-Lib对比误差<0.1%
  - test_calculate_ker_edge_cases: 除零、窗口不足
  - test_calculate_vdr_with_missing_data: 1分钟K线缺失降级
  - test_calculate_hurst_exponent: 已知均值回归序列返回H<0.5
  - test_calculate_z_score: 布林带上轨返回Z>2.0
  - test_calculate_cvd_divergence: 背离检测准确性

- [X] T049 [P] [US1] 编写单元测试在tests/grid_trading/unit/test_scoring_model.py
  - test_gss_calculation: 验证GSS公式正确性
  - test_trend_veto_mechanism: 强上升趋势GSS=0 (SC-007)
  - test_weights_validation: 权重总和≠1.0抛出异常
  - test_market_cap_boost: 排名20-100应用1.2倍系数
  - test_grid_parameters_calculation: 网格上下限和格数计算

- [X] T050 [P] [US1] 编写单元测试在tests/grid_trading/unit/test_validators.py
  - test_validate_weights_sum: 总和≠1.0抛出异常
  - test_validate_top_n_range: 超出3-10范围抛出异常
  - test_validate_min_volume: 负数或零抛出异常

- [X] T051 [P] [US1] 编写集成测试在tests/grid_trading/integration/test_binance_client.py
  - test_fetch_all_market_data_success: 真实API调用成功
  - test_api_rate_limit_retry: 429错误重试机制 (需mock)
  - test_initial_filter_logic: 初筛条件验证

- [X] T052 [P] [US1] 编写集成测试在tests/grid_trading/integration/test_screening_engine.py
  - test_end_to_end_screening_pipeline: 完整Pipeline流程 (需mock API)
  - test_performance_under_60s: 500+标的<60秒 (SC-001)
  - test_empty_results_handling: 全市场无合格标的提示 (SC-008)

- [X] T053 [US1] 编写端到端测试在tests/grid_trading/e2e/test_screen_command.py
  - test_command_execution: 运行命令验证输出包含Top 5标的
  - test_custom_parameters: 测试--top-n, --weights参数生效
  - test_output_format: 验证表格格式化和警告标记正确

**Phase 3验收标准**:
- ✅ 运行`python manage.py screen_short_grid`成功输出Top 5标的
- ✅ 终端输出包含: 排名、GSS得分、NATR/KER/VDR/H/Z-Score/OVR/Funding/CVD_ROC、推荐网格参数
- ✅ 执行时间<60秒 (500+标的)
- ✅ 警告/优势标记正确显示
- ✅ 所有单元测试和集成测试通过
- ✅ NATR计算精度与TA-Lib误差<0.1%
- ✅ 强上升趋势标的GSS=0

---

## Phase 4: Polish & Cross-Cutting Concerns (优化与完善)

**目标**: 代码质量提升、文档完善和性能优化

### 任务清单

- [X] T054 代码格式化和Linting
  - 运行black格式化所有Python文件
  - 运行flake8检查代码质量
  - 修复所有Linting警告

- [X] T055 性能优化验证
  - 使用cProfile分析性能瓶颈
  - 验证NumPy向量化计算性能
  - 验证ThreadPoolExecutor并发效果
  - 确保60秒性能目标达成 (SC-001)

- [X] T056 日志审查与优化
  - 确保所有关键步骤有INFO日志
  - 确保异常情况有WARNING/ERROR日志
  - 验证日志格式清晰易读

- [X] T057 文档更新
  - 更新README.md添加使用说明
  - 更新quickstart.md补充真实案例
  - 添加代码注释说明复杂算法（Hurst指数R/S分析）

- [ ] T058 提交代码并创建PR
  - 提交信息: "feat(grid_trading): 实现做空网格标的量化筛选系统"
  - 包含: 完整功能实现、单元测试、集成测试、端到端测试
  - PR描述: 链接spec.md和quickstart.md

**验收标准**:
- 代码通过格式化和Linting检查
- 性能达标（60秒完成500+标的筛选）
- 文档完善且准确

---

## Dependencies & Execution Order

### 依赖关系图

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← 必须完成才能进入Phase 3
    ↓
Phase 3 (US1 Core)
    ├─ 3.1 API Client → 3.2 Indicator Calculator → 3.3 Scoring Model → 3.4 Screening Engine → 3.5 Command
    └─ 3.6 Tests (并行)
    ↓
Phase 4 (Polish)
```

### 并行执行机会

**Phase 2内部并行** (T010-T017可部分并行):
- T010, T011, T012, T013, T014 (数据模型) 可同时开发
- T015 (validators) 和 T016 (formatters) 可同时开发

**Phase 3.2内部并行** (T025-T035可完全并行):
- T025, T026, T027 (波动率指标) 互不依赖
- T029, T030, T031 (趋势指标) 互不依赖
- T032, T033, T034, T035 (微观结构指标) 互不依赖

**Phase 3.6测试并行** (T048-T053可完全并行):
- 所有测试文件互不依赖，可同时编写

---

## MVP Scope Definition

**MVP包含**: Phase 1 + Phase 2 + Phase 3 (User Story 1)

**MVP输出物**:
1. ✅ 可执行的Django Management Command
2. ✅ 完整的三维筛选框架实现
3. ✅ GSS评分模型
4. ✅ 终端格式化输出Top 5标的
5. ✅ 推荐网格参数计算
6. ✅ 单元测试、集成测试、端到端测试
7. ✅ 60秒性能目标达成

**MVP验证标准**:
- 用户可运行`python manage.py screen_short_grid`获取筛选结果
- 输出包含所有必需指标和警告/优势标记
- 性能满足<60秒要求
- 测试覆盖率达标

---

## Implementation Strategy

### 推荐实施顺序

1. **第1周**: Phase 1 (Setup) + Phase 2 (Foundational)
   - 建立项目结构
   - 实现所有数据模型和工具函数
   - 为后续开发打好基础

2. **第2-3周**: Phase 3.1-3.4 (核心逻辑)
   - 实现API客户端
   - 实现指标计算器（最复杂部分，需仔细验证）
   - 实现评分模型
   - 实现筛选引擎

3. **第4周**: Phase 3.5-3.6 (Command + Tests)
   - 实现Django Command
   - 编写全面测试
   - 验证性能目标

4. **第5周**: Phase 4 (Polish)
   - 优化性能
   - 完善文档
   - Code Review和提交

### 关键里程碑

- **Milestone 1** (Day 5): Phase 2完成，所有基础组件可用
- **Milestone 2** (Day 15): Phase 3.1-3.2完成，API和指标计算可用
- **Milestone 3** (Day 22): Phase 3.3-3.4完成，完整Pipeline可用
- **Milestone 4** (Day 28): Phase 3完成，MVP功能完整且测试通过
- **Milestone 5** (Day 35): Phase 4完成，代码优化并提交PR

---

## Success Criteria Mapping

| Success Criteria | 相关任务 | 验证方式 |
|-----------------|---------|---------|
| SC-001: 60秒完成500+标的扫描 | T043, T055 | 端到端性能测试 |
| SC-002: NATR精度<0.1%误差 | T025, T048 | 单元测试对比TA-Lib |
| SC-003: Top 5满足筛选条件 | T041, T047, T053 | 端到端测试验证 |
| SC-004: API成功率≥99% | T018-T024, T051 | 集成测试+重试机制 |
| SC-005: 输出清晰易读 | T016, T047 | 手动验证+用户反馈 |
| SC-006: 参数可配置 | T015, T045, T050 | 单元测试验证 |
| SC-007: 强趋势GSS=0 | T038, T049 | 单元测试验证 |
| SC-008: 无合格标的明确提示 | T044, T052 | 集成测试验证 |
| SC-009: VDR计算准确性 | T027, T048 | 单元测试验证 |
| SC-010: Z-Score识别准确性 | T031, T048 | 单元测试验证 |
| SC-011: CVD_ROC预警有效性 | T035, T048 | 单元测试验证 |

---

## Notes

- **测试策略**: 采用TDD，先写失败的测试，再实现功能使测试通过
- **并行开发**: Phase 3.2的指标计算器各函数互不依赖，可多人并行开发
- **性能监控**: 在开发过程中持续关注性能，避免最后才发现性能问题
- **代码复用**: 优先复用monitor/api_clients/binance.py的成熟代码模式
- **错误处理**: 所有API调用和计算函数都要有完善的错误处理和降级逻辑
- **日志记录**: 关键步骤输出INFO日志，异常情况输出WARNING/ERROR日志

---

**生成时间**: 2025-12-03
**文档版本**: v1.0
**状态**: ✅ Ready for Implementation
