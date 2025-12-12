# Implementation Plan: 合约分析详情页

**Branch**: `007-contract-detail-page` | **Date**: 2025-12-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-contract-detail-page/spec.md`

## Summary

为做空网格筛选系统的每日筛选结果(/screening/daily/)添加合约详情页功能。用户点击合约的"详情"按钮后，跳转到独立的详情页(/screening/daily/<date>/<symbol>)，展示该合约的完整分析数据(20+指标覆盖4个维度)、K线图(支持15m/1h/4h/1d多周期切换)、以及关键技术指标标记(EMA均线、VPA信号、规则6/7触发点)。

技术方案采用Django SSR + 异步JavaScript图表加载，使用分批渲染策略优化性能(第一阶段<500ms显示K线骨架，第二阶段<1.5s叠加均线，第三阶段<2s叠加信号标记)。本版本专注于桌面网页版，不考虑移动端适配。

## Technical Context

**Language/Version**: Python 3.12 + Django 4.2.8
**Primary Dependencies**:
  - 后端: Django 4.2.8, python-binance 1.0.19, pandas 2.0+, numpy 1.24+
  - 前端: ECharts 5.5+ (或Lightweight Charts 4.x) - K线图表库
  - 数据服务: 复用现有KlineCache、IndicatorCalculator服务
**Storage**: SQLite (开发) / PostgreSQL 14+ (生产)，复用KlineData表、ScreeningResultModel表、ScreeningRecord表
**Testing**: pytest, Django TestCase
**Target Platform**: 桌面网页浏览器(Chrome、Firefox、Safari、Edge)，最低分辨率1280×720
**Project Type**: Web application (Django SSR + JavaScript前端图表)
**Performance Goals**:
  - 页面初始加载<3秒(FR-024)
  - K线图首次可见<500ms，完整渲染<2s(FR-025)
  - 支持300根K线+2条EMA均线的流畅交互(拖动、缩放、Tooltip)
**Constraints**:
  - K线数据来源于历史快照(screening_date时刻的数据)，非实时最新价格
  - 不考虑移动端适配，专注桌面版本
  - 指标计算可能失败，必须显示"计算失败"+Tooltip说明原因(FR-028)
**Scale/Scope**:
  - 支持500+合约的详情页访问
  - 每个详情页展示20+指标、300根K线、多周期切换(4种)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 核心原则合规性

✅ **零假设原则**: 规格澄清阶段已解决所有关键决策点(6个澄清问题)
✅ **小步提交**: 计划采用增量开发，每个Phase独立可测试
✅ **借鉴现有代码**: 复用grid_trading/views.py的路由模式、models.py的数据结构
✅ **简单至上**: 避免过度抽象，优先使用Django标准模式(CBV或FBV)
✅ **测试驱动**: 每个API endpoint和关键服务函数都需要测试覆盖

### 量化系统原则合规性

✅ **数据可追溯**: K线数据来自KlineData表的历史快照，可追溯到screening_date
✅ **指标透明度**: 所有指标计算失败必须显示原因(FR-028)，支持用户诊断
⚠️ **风险控制**: 详情页仅展示分析数据，不涉及交易执行，无风险控制要求
N/A **回测验证**: 此功能为展示层，不涉及策略逻辑，无需回测

### 项目特定约束

✅ **Django模式一致性**: 遵循grid_trading应用的现有Views/URLs/Models结构
✅ **性能约束**: 分批渲染策略符合宪法的"务实主义"原则
✅ **可测试性**: Django TestCase可测试视图逻辑，Selenium可测试前端交互(可选)

**结论**: 通过Constitution Check，无违规项，可进入Phase 0研究阶段。

## Project Structure

### Documentation (this feature)

```text
specs/007-contract-detail-page/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── api-contract.yaml       # API endpoint定义(OpenAPI 3.0)
│   └── data-contract.yaml      # 前后端数据契约
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Django应用结构 (Web application)

grid_trading/                           # 现有Django应用(扩展)
├── views.py                            # [扩展] 新增详情页视图函数
├── urls.py                             # [扩展] 新增详情页路由
├── templates/
│   └── grid_trading/
│       ├── screening_daily.html        # [新增] 日历筛选列表页
│       └── screening_detail.html       # [新增] 合约详情页模板
├── static/
│   └── grid_trading/
│       ├── js/
│       │   ├── screening_daily.js      # [新增] 日历列表页交互
│       │   └── screening_detail.js     # [新增] 详情页K线图渲染
│       └── css/
│           └── screening_detail.css    # [新增] 详情页样式
├── services/
│   ├── kline_cache.py                  # [复用] K线数据缓存服务
│   ├── indicator_calculator.py         # [复用] 技术指标计算
│   └── detail_page_service.py          # [新增] 详情页数据聚合服务
└── tests/
    └── test_detail_page.py             # [新增] 详情页单元测试

# 前端图表库
# 选项A: ECharts (推荐)
#   - 优点: 功能强大、中文文档完善、支持Canvas渲染
#   - 缺点: 体积较大(~300KB gzipped)
# 选项B: Lightweight Charts
#   - 优点: 轻量级(~40KB)、专为金融K线设计、TradingView官方开源
#   - 缺点: 功能相对简单、社区生态小
```

**Structure Decision**:
采用Django单体应用扩展模式，在现有grid_trading应用内新增详情页相关的Views、Templates、Static文件。前端图表库推荐使用**Lightweight Charts**（原因：轻量级、专为金融图表优化、符合"简单至上"原则），如果发现功能不足再升级为ECharts。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无宪法违规项，本表格留空。

---

## Phase 0: Research & Unknowns Resolution

### Research Tasks

#### R1: K线图表库选择 (Charting Library Selection)

**目标**: 确定最适合的JavaScript K线图表库

**需要调研的点**:
- Lightweight Charts vs ECharts性能对比(300根K线+2条EMA均线)
- 分批渲染支持情况(是否支持增量添加Series)
- 桌面端交互支持(拖动、缩放、Tooltip、悬停)
- VPA信号标记的实现方式(自定义Marker或Annotation)
- 多周期切换的实现复杂度

**输出**:
- 推荐图表库及理由
- 代码示例(初始化、数据加载、EMA叠加、信号标记)
- 性能测试结果(300根K线渲染时间)

#### R2: Django历史数据查询模式 (Historical Data Query Pattern)

**目标**: 确定如何从数据库查询特定日期的筛选结果和K线数据

**需要调研的点**:
- ScreeningRecord表的screening_date字段查询逻辑
- KlineData表的时间范围过滤(open_time < screening_date + 1day)
- 多个related objects的eager loading优化(select_related / prefetch_related)
- 404场景的处理(日期不存在、合约不存在)

**输出**:
- Django ORM查询代码示例
- 性能优化建议(N+1查询避免)
- 错误处理模式

#### R3: 分批渲染前端实现策略 (Progressive Rendering Strategy)

**目标**: 设计前端JavaScript的分批渲染流程

**需要调研的点**:
- 阶段1: K线蜡烛图渲染(Promise异步)
- 阶段2: EMA均线计算+叠加(Web Worker可选)
- 阶段3: VPA信号标记(Marker/Annotation API)
- 阶段间的数据依赖关系和错误恢复

**输出**:
- JavaScript伪代码流程
- 阶段时间分配建议
- 用户体验优化建议(Loading spinner、渐进显示)

#### R4: 指标计算失败的Tooltip实现 (Tooltip for Failed Indicators)

**目标**: 确定如何在前端展示"计算失败"的指标+Tooltip

**需要调研的点**:
- HTML/CSS的Tooltip实现(纯CSS vs JavaScript库)
- 图标选择(question-circle的Unicode或Font Awesome)
- 后端如何返回错误信息(扩展to_dict()方法)

**输出**:
- HTML/CSS代码示例
- 前后端数据契约(JSON格式)

### Dependencies & Best Practices

#### D1: Django Static Files最佳实践

**调研内容**:
- collectstatic的使用(开发vs生产)
- CDN加载图表库 vs 本地打包
- 缓存策略(ETag、Cache-Control)

#### D2: K线图表的国际标准颜色方案

**调研内容**:
- 绿涨红跌的色值推荐(TradingView、Binance使用的RGB值)
- 色盲友好的辅助设计(纹理、边框)

#### D3: Django模板继承与组件化

**调研内容**:
- base.html的继承模式
- 可复用的指标展示组件(Jinja2 macro或Django inclusion tag)

---

## Phase 1: Design & Contracts

### Data Model Extensions

#### 无新增Model
本功能复用现有数据模型，无需创建新的Model类：
- **ScreeningRecord**: 存储筛选元数据
- **ScreeningResultModel**: 存储合约分析结果(20+指标)
- **KlineData**: 存储K线历史数据

#### ScreeningResultModel扩展 (可选)
如果需要支持"计算失败"的错误信息持久化：
```python
# grid_trading/models.py (可选扩展)
class ScreeningResultModel:
    # 新增字段(可选)
    indicator_errors = models.JSONField(
        '指标计算错误信息',
        default=dict,
        help_text='存储计算失败的指标及原因 {\"rsi_15m\": \"数据不足\", ...}'
    )
```

**决策**: 初期不新增字段，在to_dict()方法中动态判断None值并生成错误信息。如果后续发现需要持久化错误日志，再添加indicator_errors字段。

### API Contracts

#### API-1: GET /screening/daily/ (日历筛选列表页)

**描述**: 展示所有筛选日期的列表，用户可以选择日期查看当天的筛选结果

**Request**:
```http
GET /grid_trading/screening/daily/
```

**Response** (HTML渲染):
```django
{# screening_daily.html #}
- 日历选择器(DatePicker)
- 筛选记录列表(按screening_date分组)
- 每个日期显示: 日期、筛选数量、平均GSS得分
```

**实现要点**:
- 使用Django ORM查询ScreeningRecord.objects.values('screening_date').distinct()
- 按screening_date倒序排列(最新日期在前)

---

#### API-2: GET /screening/daily/<date>/ (某日筛选结果列表)

**描述**: 展示指定日期的所有筛选合约，每行显示合约symbol、price、综合指数、排名，以及"详情"按钮

**Request**:
```http
GET /grid_trading/screening/daily/2024-12-05/
```

**Response** (HTML渲染):
```django
{# screening_daily.html (复用) #}
- 日期标题: "2024-12-05 筛选结果"
- 表格: symbol | price | GSS | rank | [详情按钮]
- 分页器(如果结果超过50条)
```

**实现要点**:
- 查询: ScreeningRecord.objects.get(screening_date=date).results.all()
- 如果日期不存在: 返回404页面(参见API-5)

---

#### API-3: GET /screening/daily/<date>/<symbol>/ (合约详情页)

**描述**: 展示指定日期、指定合约的完整分析详情页，包括20+指标、K线图、网格参数、挂单建议

**Request**:
```http
GET /grid_trading/screening/daily/2024-12-05/ZENUSDT/
```

**Response** (HTML渲染):
```django
{# screening_detail.html #}
- 基本信息区域(symbol、price、rank、GSS)
- 指标明细区域(4个维度分组展示)
- K线图区域(ECharts/Lightweight Charts)
- 网格参数区域
- 挂单建议区域
```

**数据流程**:
1. Django View查询ScreeningResultModel.objects.get(record__screening_date=date, symbol=symbol)
2. 调用detail_page_service.prepare_detail_data()聚合所有数据
3. 渲染模板，将数据以JSON形式嵌入`<script>`标签供前端JavaScript使用

**错误处理**:
- 日期不存在: 返回404(参见API-5)
- 合约不存在: 返回404
- 指标计算失败: 显示"计算失败"+Tooltip(FR-028)

---

#### API-4: GET /api/screening/<date>/<symbol>/klines/ (K线数据API)

**描述**: 为详情页前端提供K线数据的JSON API，支持多周期切换

**Request**:
```http
GET /api/screening/2024-12-05/ZENUSDT/klines/?interval=4h&limit=300
```

**Query Parameters**:
- `interval` (required): 时间周期，可选值: 15m, 1h, 4h, 1d
- `limit` (optional): K线数量，默认值: {15m: 100, 1h: 50, 4h: 300, 1d: 30}

**Response**:
```json
{
  "symbol": "ZENUSDT",
  "interval": "4h",
  "screening_date": "2024-12-05",
  "klines": [
    {
      "open_time": 1701705600000,  // Unix timestamp (ms)
      "open": 123.45,
      "high": 125.67,
      "low": 122.34,
      "close": 124.56,
      "volume": 123456.78
    },
    // ... 300根K线
  ],
  "ema99": [123.1, 123.2, ...],  // EMA99值数组
  "ema20": [124.5, 124.6, ...],  // EMA20值数组
  "vpa_signals": [
    {
      "open_time": 1701705600000,
      "pattern": "急刹车",  // 或"金针探底"、"攻城锤"、"阳包阴"
      "direction": "bullish"  // or "bearish"
    }
  ],
  "rule_signals": [
    {
      "open_time": 1701705600000,
      "rule_id": 6,  // 规则6止盈 或 规则7止损
      "timeframe": "15m",  // 或"1h"
      "rsi_value": 18.5,
      "description": "规则6触发: 急刹车+RSI超卖"
    }
  ],
  "warnings": [
    "数据不足，仅显示20根K线(需要300根)"  // 如果K线数不足
  ]
}
```

**实现要点**:
- 调用KlineCache.get_klines(symbol, interval, limit, end_time=screening_date + 1day)
- 调用IndicatorCalculator.calculate_ema_slope()计算EMA99和EMA20
- 调用VPA检测服务识别VPA模式(可选，如果Phase 1时间紧张可延后到P3)
- 调用RuleEngine检测规则6/7触发点(可选)

---

#### API-5: 404错误页面

**描述**: 友好的404页面，显示错误说明和导航帮助(FR-027)

**触发场景**:
- URL中的日期不存在筛选记录
- URL中的合约在该日期无筛选记录

**Response** (HTML渲染):
```django
{# 404.html #}
<div class="error-page">
  <h1>404 - 记录未找到</h1>
  <p>该日期(2024-12-05)的合约(ZENUSDT)无筛选记录</p>
  <button onclick="window.location='/grid_trading/screening/daily/'">
    返回筛选列表
  </button>
  <h3>查看其他日期:</h3>
  <ul>
    <li><a href="/grid_trading/screening/daily/2024-12-04/">2024-12-04</a></li>
    <li><a href="/grid_trading/screening/daily/2024-12-03/">2024-12-03</a></li>
    ...
  </ul>
</div>
```

**实现要点**:
- Django View返回`HttpResponseNotFound(render(request, '404.html', context))`
- context包含: 请求的日期、合约、最近5个有数据的日期列表

---

### Frontend Chart Integration

#### Chart Library Decision
**推荐**: Lightweight Charts 4.x

**理由**:
1. 轻量级(~40KB gzipped)，加载速度快
2. 专为金融K线设计，API简洁
3. 支持增量添加Series，便于分批渲染
4. 支持自定义Marker，便于VPA信号标记
5. 开源且活跃维护(TradingView官方)

**备选**: 如果发现Lightweight Charts功能不足，升级为ECharts 5.5+

#### Progressive Rendering Workflow

```javascript
// screening_detail.js

// ========== 阶段1: 渲染K线蜡烛图 (<500ms) ==========
async function renderStage1(chartContainer) {
  const chart = LightweightCharts.createChart(chartContainer, {
    layout: { backgroundColor: '#ffffff', textColor: '#333' },
    grid: { vertLines: { color: '#e1e1e1' }, horzLines: { color: '#e1e1e1' } },
    timeScale: { timeVisible: true, secondsVisible: false }
  });

  const candlestickSeries = chart.addCandlestickSeries({
    upColor: '#26a69a',    // 绿色(上涨)
    downColor: '#ef5350',  // 红色(下跌)
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350'
  });

  // 加载K线数据(从API-4获取)
  const response = await fetch(`/api/screening/${date}/${symbol}/klines/?interval=4h&limit=300`);
  const data = await response.json();

  candlestickSeries.setData(data.klines);

  // 如果数据不足，显示警告横幅
  if (data.warnings && data.warnings.length > 0) {
    showWarningBanner(data.warnings[0]);
  }

  return { chart, candlestickSeries, data };
}

// ========== 阶段2: 叠加EMA均线 (<1.5s cumulative) ==========
async function renderStage2(chart, data) {
  // EMA99均线(蓝色)
  const ema99Series = chart.addLineSeries({
    color: '#2196F3',
    lineWidth: 2,
    title: 'EMA99'
  });
  ema99Series.setData(data.ema99.map((value, index) => ({
    time: data.klines[index].open_time / 1000,  // 转为秒级时间戳
    value: value
  })));

  // EMA20均线(橙色)
  const ema20Series = chart.addLineSeries({
    color: '#FF9800',
    lineWidth: 2,
    title: 'EMA20'
  });
  ema20Series.setData(data.ema20.map((value, index) => ({
    time: data.klines[index].open_time / 1000,
    value: value
  })));

  // 标注当前价格(水平虚线)
  const currentPrice = data.klines[data.klines.length - 1].close;
  chart.addPriceLine({
    price: currentPrice,
    color: '#2962FF',
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: '当前价格'
  });
}

// ========== 阶段3: 叠加VPA标记和规则信号 (<2s cumulative) ==========
async function renderStage3(candlestickSeries, data) {
  // VPA信号标记
  data.vpa_signals.forEach(signal => {
    candlestickSeries.setMarkers([
      ...candlestickSeries.markers(),  // 保留已有标记
      {
        time: signal.open_time / 1000,
        position: signal.direction === 'bullish' ? 'belowBar' : 'aboveBar',
        color: signal.direction === 'bullish' ? '#26a69a' : '#ef5350',
        shape: 'circle',
        text: signal.pattern,
        size: 1
      }
    ]);
  });

  // 规则6/7触发信号
  data.rule_signals.forEach(signal => {
    candlestickSeries.setMarkers([
      ...candlestickSeries.markers(),
      {
        time: signal.open_time / 1000,
        position: signal.rule_id === 6 ? 'belowBar' : 'aboveBar',
        color: signal.rule_id === 6 ? '#4CAF50' : '#F44336',
        shape: signal.rule_id === 6 ? 'arrowUp' : 'arrowDown',
        text: `规则${signal.rule_id}`,
        size: 2
      }
    ]);
  });
}

// ========== 主渲染流程 ==========
async function renderChart() {
  try {
    const { chart, candlestickSeries, data } = await renderStage1(document.getElementById('chart'));
    await renderStage2(chart, data);
    await renderStage3(candlestickSeries, data);
  } catch (error) {
    console.error('图表渲染失败:', error);
    showErrorMessage('K线图加载失败，请刷新页面重试');
  }
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', renderChart);
```

---

### URL Routing Design

```python
# grid_trading/urls.py (扩展)
from django.urls import path
from . import views

app_name = 'grid_trading'

urlpatterns = [
    # 现有路由...

    # ========== 新增: 日历筛选与详情页路由 ==========

    # 日历筛选主页(显示所有日期)
    path('screening/daily/', views.screening_daily_index, name='screening_daily_index'),

    # 某日筛选结果列表
    path('screening/daily/<str:date>/', views.screening_daily_detail, name='screening_daily_detail'),

    # 合约详情页
    path('screening/daily/<str:date>/<str:symbol>/', views.contract_detail, name='contract_detail'),

    # ========== API路由(JSON) ==========

    # K线数据API
    path('api/screening/<str:date>/<str:symbol>/klines/', views.api_klines, name='api_klines'),
]
```

**说明**:
- 使用`str:date`捕获日期参数(格式: YYYY-MM-DD)，View内部使用`datetime.strptime(date, '%Y-%m-%d')`解析
- 使用`str:symbol`捕获合约代码(如ZENUSDT)
- API路由返回JsonResponse，HTML路由返回render()

---

## Phase 2: Implementation Roadmap

*此部分由 /speckit.tasks 命令生成，不在 /speckit.plan 的输出范围内*

参见 `tasks.md` (将由 /speckit.tasks 生成)

---

## Quickstart Guide

*See `quickstart.md` for developer onboarding instructions*

---

## Notes

- 本计划遵循宪法的"借鉴现有代码"原则，最大程度复用grid_trading应用的现有结构和服务
- K线图表库推荐Lightweight Charts，但在Phase 0研究后可能调整为ECharts
- 分批渲染策略是性能优化的关键，确保用户快速看到首屏内容
- 指标计算失败的Tooltip实现需要前后端协作，后端返回错误信息，前端展示
- VPA信号和规则6/7标记是P3功能，Phase 1可以先实现基础K线图，后续迭代再添加信号标记
