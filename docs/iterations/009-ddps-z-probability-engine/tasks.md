# 任务计划：动态偏离概率空间 2.0 (DDPS-Z)

## 文档信息
| 属性 | 值 |
|------|-----|
| 迭代编号 | 009 |
| 创建日期 | 2025-01-05 |
| 任务总数 | 14 |
| 状态 | 待执行 |

---

## 任务概览

| 阶段 | 任务数 | 预估工作量 |
|------|--------|-----------|
| 阶段1：基础设施 | 2 | 轻量 |
| 阶段2：计算引擎 | 4 | 核心 |
| 阶段3：服务层 | 2 | 中等 |
| 阶段4：API层 | 3 | 中等 |
| 阶段5：命令行 | 1 | 轻量 |
| 阶段6：前端 | 2 | 中等 |

---

## 架构决策影响

根据P4阶段确认的架构决策，以下PRD功能点**不需要实现**：
- ~~FP-009 DDPSResult模型~~ → 不持久化计算结果
- ~~FP-010 DDPSDeviationHistory模型~~ → 纯实时计算
- ~~FP-011 结果持久化服务~~ → 不需要
- ~~FP-013 全量扫描~~ → 按需计算，无定时扫描

---

## 阶段1：基础设施

### TASK-009-001：创建ddps_z Django App

**描述**：创建新的Django应用，配置基础文件结构

**功能点映射**：基础设施

**实现内容**：
```bash
python manage.py startapp ddps_z
```

创建目录结构：
```
ddps_z/
├── __init__.py
├── apps.py
├── urls.py
├── calculators/
│   └── __init__.py
├── services/
│   └── __init__.py
└── tests/
    └── __init__.py
```

**验收标准**：
- [ ] App创建成功
- [ ] 目录结构完整
- [ ] apps.py配置正确

**依赖**：无

**状态**：⬜ 待执行

---

### TASK-009-002：配置URL路由和Settings

**描述**：在项目settings中注册App，配置URL路由

**功能点映射**：基础设施

**实现内容**：
1. 在`listing_monitor_project/settings.py`中添加`ddps_z`到INSTALLED_APPS
2. 创建`ddps_z/urls.py`路由配置
3. 在`listing_monitor_project/urls.py`中include ddps_z路由
4. 添加DDPS配置参数到settings

**配置参数**：
```python
# settings.py
DDPS_CONFIG = {
    'EMA_PERIOD': 25,
    'EWMA_WINDOW_N': 180,
    'DEFAULT_INTERVAL': '4h',
    'RVOL_THRESHOLD': 2.0,
    'MIN_KLINES_REQUIRED': 180,
    'Z_SCORE_OVERSOLD': -1.64,
    'Z_SCORE_OVERBOUGHT': 1.64,
}
```

**验收标准**：
- [ ] App注册成功
- [ ] /ddps-z/ 路由可访问
- [ ] 配置参数可正确读取

**依赖**：TASK-009-001

**状态**：⬜ 待执行

---

## 阶段2：计算引擎

### TASK-009-003：实现EMACalculator

**描述**：实现EMA(25)指数移动平均线计算器

**功能点映射**：FP-001

**实现内容**：
```python
# ddps_z/calculators/ema_calculator.py
class EMACalculator:
    def __init__(self, period: int = 25):
        self.period = period

    def calculate(self, prices: List[Decimal]) -> List[Decimal]:
        """计算EMA序列"""
        pass

    def calculate_single(self, prices: List[Decimal]) -> Decimal:
        """计算最新EMA值"""
        pass
```

**算法**：
- EMA_t = Price_t × α + EMA_{t-1} × (1-α)
- α = 2 / (period + 1) = 2/26 ≈ 0.0769

**验收标准**：
- [ ] 给定K线序列，计算结果误差<0.01%
- [ ] 处理数据不足情况（返回None或抛出异常）
- [ ] 单元测试通过

**依赖**：TASK-009-001

**状态**：⬜ 待执行

---

### TASK-009-004：实现EWMACalculator

**描述**：实现EWMA计算器，计算偏离率D_t、动态均值μ_t和动态波动率σ_t

**功能点映射**：FP-002, FP-003, FP-004

**实现内容**：
```python
# ddps_z/calculators/ewma_calculator.py
class EWMACalculator:
    def __init__(self, window_n: int = 180):
        self.window_n = window_n
        self.alpha = 2 / (window_n + 1)  # ≈ 0.011

    def calculate_deviation(self, price: Decimal, ema: Decimal) -> Decimal:
        """计算基础偏离率 D_t = (Price - EMA) / EMA"""
        pass

    def calculate_ewma_mean(self, deviations: List[Decimal]) -> Decimal:
        """计算EWMA均值 μ_t"""
        pass

    def calculate_ewma_volatility(self, deviations: List[Decimal], mu: Decimal) -> Decimal:
        """计算EWMA波动率 σ_t = sqrt(EWMA((D_t - μ_t)²))"""
        pass

    def calculate_all(self, prices: List[Decimal], emas: List[Decimal]) -> dict:
        """一次性计算所有EWMA指标"""
        pass
```

**验收标准**：
- [ ] 偏离率计算准确，符号正确
- [ ] EWMA均值平滑效果明显
- [ ] 波动率始终为正值
- [ ] 单元测试通过

**依赖**：TASK-009-003

**状态**：⬜ 待执行

---

### TASK-009-005：实现ZScoreCalculator

**描述**：实现Z-Score计算和分位数映射

**功能点映射**：FP-005, FP-006

**实现内容**：
```python
# ddps_z/calculators/zscore_calculator.py
class ZScoreCalculator:
    def calculate_zscore(self, d_t: Decimal, mu_t: Decimal, sigma_t: Decimal) -> Decimal:
        """计算Z-Score: Z_t = (D_t - μ_t) / σ_t"""
        pass

    def zscore_to_percentile(self, z_score: float) -> float:
        """将Z-Score映射到百分位数(0-100)，基于正态分布假设"""
        # 使用scipy.stats.norm.cdf
        pass

    def get_signal_text(self, z_score: float, percentile: float) -> str:
        """生成信号解读文本"""
        # Z = -2.8 → "当前偏离超越 99% 的历史时刻"
        pass
```

**验收标准**：
- [ ] Z值大部分在[-3, 3]范围内
- [ ] Z=-1.64对应约5%分位
- [ ] Z=1.64对应约95%分位
- [ ] 信号文本生成正确
- [ ] 单元测试通过

**依赖**：TASK-009-004

**状态**：⬜ 待执行

---

### TASK-009-006：实现SignalEvaluator

**描述**：实现量价验证逻辑，判断信号强度

**功能点映射**：FP-008

**实现内容**：
```python
# ddps_z/calculators/signal_evaluator.py
from volume_trap.detectors.rvol_calculator import RVOLCalculator

class SignalEvaluator:
    def __init__(self, rvol_threshold: float = 2.0,
                 z_oversold: float = -1.64,
                 z_overbought: float = 1.64):
        self.rvol_threshold = rvol_threshold
        self.z_oversold = z_oversold
        self.z_overbought = z_overbought

    def evaluate(self, z_score: float, rvol: float) -> dict:
        """
        评估信号
        返回: {
            'signal': 'buy' | 'sell' | 'none',
            'strength': 'strong' | 'weak' | 'none',
            'reason': str
        }
        """
        pass
```

**信号规则**：
| 条件 | 信号 | 强度 |
|------|------|------|
| Z ≤ -1.64 且 RVOL ≥ 2 | buy | strong |
| Z ≤ -1.64 且 RVOL < 2 | buy | weak |
| Z ≥ 1.64 且 RVOL ≥ 2 | sell | strong |
| Z ≥ 1.64 且 RVOL < 2 | sell | weak |
| 其他 | none | none |

**验收标准**：
- [ ] 正确复用RVOLCalculator
- [ ] 各状态判断正确
- [ ] 单元测试覆盖所有分支

**依赖**：TASK-009-005

**状态**：⬜ 待执行

---

## 阶段3：服务层

### TASK-009-007：实现DDPSService

**描述**：实现业务编排服务，协调各计算器完成完整计算流程

**功能点映射**：FP-014（数据不足处理）

**实现内容**：
```python
# ddps_z/services/ddps_service.py
class DDPSService:
    def __init__(self):
        self.ema_calc = EMACalculator()
        self.ewma_calc = EWMACalculator()
        self.zscore_calc = ZScoreCalculator()
        self.signal_eval = SignalEvaluator()

    def calculate(self, symbol: str, interval: str = '4h') -> dict:
        """
        完整计算流程
        返回: {
            'symbol': str,
            'interval': str,
            'timestamp': datetime,
            'price': Decimal,
            'ema25': Decimal,
            'deviation_d': Decimal,
            'ewma_mu': Decimal,
            'ewma_sigma': Decimal,
            'z_score': float,
            'percentile': float,
            'rvol': float,
            'signal': str,
            'signal_strength': str,
            'signal_text': str,
            'data_sufficient': bool
        }
        """
        pass

    def _get_klines(self, symbol: str, interval: str, limit: int = 200) -> QuerySet:
        """获取K线数据"""
        pass

    def _check_data_sufficient(self, klines_count: int) -> bool:
        """检查数据是否充足（≥180根）"""
        pass
```

**验收标准**：
- [ ] 完整计算流程可执行
- [ ] 数据不足时返回警告而非错误
- [ ] 返回结果包含所有必要字段

**依赖**：TASK-009-003 ~ TASK-009-006

**状态**：⬜ 待执行

---

### TASK-009-008：实现ChartDataService

**描述**：实现图表数据格式化服务，生成K线图+分位数带数据

**功能点映射**：FP-016（部分）

**实现内容**：
```python
# ddps_z/services/chart_data_service.py
class ChartDataService:
    def get_chart_data(self, symbol: str, interval: str = '4h', limit: int = 200) -> dict:
        """
        获取图表数据
        返回: {
            'symbol': str,
            'interval': str,
            'candles': [{t, o, h, l, c, v}, ...],
            'ema25': [float, ...],
            'quantile_bands': {
                'p5': [float, ...],
                'p10': [float, ...],
                'p50': [float, ...],
                'p90': [float, ...],
                'p95': [float, ...]
            },
            'current_z_score': float
        }
        """
        pass

    def _calculate_quantile_bands(self, emas: List, sigmas: List) -> dict:
        """计算分位数带（基于EMA和波动率）"""
        # p5 = EMA + Z(-1.64) * sigma * EMA
        # p95 = EMA + Z(1.64) * sigma * EMA
        pass
```

**验收标准**：
- [ ] 返回格式符合前端需求
- [ ] 分位数带随波动率变化
- [ ] 性能：200根K线<100ms

**依赖**：TASK-009-007

**状态**：⬜ 待执行

---

## 阶段4：API层

### TASK-009-009：实现ContractListAPI

**描述**：实现合约列表API，返回所有活跃合约

**功能点映射**：FP-015（部分）

**实现内容**：
```python
# ddps_z/api_views.py
class ContractListAPIView(APIView):
    def get(self, request):
        """
        GET /api/ddps-z/contracts/
        返回所有活跃合约，按市值排序
        """
        contracts = FuturesContract.objects.filter(status='active').order_by('-market_cap')
        return Response({
            'contracts': [{'symbol': c.symbol, 'market_cap': c.market_cap} for c in contracts],
            'total': contracts.count()
        })
```

**验收标准**：
- [ ] 返回所有活跃合约
- [ ] 按市值降序排序
- [ ] 响应时间<500ms

**依赖**：TASK-009-002

**状态**：⬜ 待执行

---

### TASK-009-010：实现DDPSCalculateAPI

**描述**：实现DDPS计算API，触发实时计算并返回结果

**功能点映射**：FP-001~008

**实现内容**：
```python
# ddps_z/api_views.py
class DDPSCalculateAPIView(APIView):
    def get(self, request):
        """
        GET /api/ddps-z/calculate/?symbol=ETHUSDT&interval=4h
        实时计算并返回Z-Score结果
        """
        symbol = request.query_params.get('symbol')
        interval = request.query_params.get('interval', '4h')

        service = DDPSService()
        result = service.calculate(symbol, interval)

        return Response(result)
```

**验收标准**：
- [ ] 支持symbol和interval参数
- [ ] 返回完整计算结果
- [ ] 响应时间<100ms

**依赖**：TASK-009-007

**状态**：⬜ 待执行

---

### TASK-009-011：实现KLineChartAPI

**描述**：实现K线图表数据API

**功能点映射**：FP-016（部分）

**实现内容**：
```python
# ddps_z/api_views.py
class KLineChartAPIView(APIView):
    def get(self, request):
        """
        GET /api/ddps-z/chart/?symbol=ETHUSDT&interval=4h&limit=200
        返回带分位数带的K线图表数据
        """
        symbol = request.query_params.get('symbol')
        interval = request.query_params.get('interval', '4h')
        limit = int(request.query_params.get('limit', 200))

        service = ChartDataService()
        result = service.get_chart_data(symbol, interval, limit)

        return Response(result)
```

**验收标准**：
- [ ] 返回K线OHLCV数据
- [ ] 返回EMA25序列
- [ ] 返回分位数带数据
- [ ] 响应时间<100ms

**依赖**：TASK-009-008

**状态**：⬜ 待执行

---

## 阶段5：命令行

### TASK-009-012：实现scan_ddps命令

**描述**：实现CLI命令，支持指定交易对计算并输出结果

**功能点映射**：FP-012

**实现内容**：
```python
# ddps_z/management/commands/scan_ddps.py
class Command(BaseCommand):
    help = '计算指定交易对的DDPS Z-Score'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', required=True, help='交易对代码')
        parser.add_argument('--interval', default='4h', help='K线周期')

    def handle(self, *args, **options):
        symbol = options['symbol']
        interval = options['interval']

        service = DDPSService()
        result = service.calculate(symbol, interval)

        self._print_result(result)
```

**输出示例**：
```
=== DDPS-Z 计算结果 ===
交易对: ETHUSDT
周期: 4h
时间: 2025-01-05 12:00:00

价格: 3450.25
EMA25: 3500.00
偏离率: -1.42%

Z-Score: -0.608
分位数: 27.2%
信号: 中性

RVOL: 1.5x
量价验证: 无信号
```

**验收标准**：
- [ ] 支持--symbol和--interval参数
- [ ] 输出格式清晰易读
- [ ] 数据不足时显示警告

**依赖**：TASK-009-007

**状态**：⬜ 待执行

---

## 阶段6：前端

### TASK-009-013：实现Dashboard页面

**描述**：实现DDPS Dashboard，展示所有交易对列表

**功能点映射**：FP-015

**实现内容**：
1. 创建`ddps_z/templates/ddps_z/dashboard.html`
2. 单页展示所有交易对（不分页）
3. 默认按市值排序
4. 前端关键字搜索过滤
5. 点击跳转到详情页

**页面结构**：
```html
<!-- dashboard.html -->
<div class="ddps-dashboard">
    <h1>DDPS-Z 概率空间</h1>

    <!-- 搜索框 -->
    <input type="text" id="search" placeholder="搜索交易对...">

    <!-- 交易对列表 -->
    <div class="contract-list">
        {% for contract in contracts %}
        <div class="contract-item" data-symbol="{{ contract.symbol }}">
            <span class="symbol">{{ contract.symbol }}</span>
            <span class="market-cap">{{ contract.market_cap|filesizeformat }}</span>
        </div>
        {% endfor %}
    </div>
</div>

<script>
// 前端搜索过滤
document.getElementById('search').addEventListener('input', function(e) {
    const keyword = e.target.value.toLowerCase();
    document.querySelectorAll('.contract-item').forEach(item => {
        const symbol = item.dataset.symbol.toLowerCase();
        item.style.display = symbol.includes(keyword) ? '' : 'none';
    });
});
</script>
```

**验收标准**：
- [ ] 展示所有活跃合约
- [ ] 按市值降序排序
- [ ] 前端搜索过滤正常
- [ ] 点击可跳转详情页

**依赖**：TASK-009-009

**状态**：⬜ 待执行

---

### TASK-009-014：实现合约详情页（K线图+分位数带）

**描述**：实现合约详情页，展示K线图和分位数带

**功能点映射**：FP-016

**实现内容**：
1. 创建`ddps_z/templates/ddps_z/detail.html`
2. 使用Chart.js渲染K线图
3. 叠加分位数带（区域填充）
4. 显示当前Z-Score和信号状态

**页面结构**：
```html
<!-- detail.html -->
<div class="ddps-detail">
    <h1>{{ symbol }} - DDPS分析</h1>

    <!-- Z-Score显示 -->
    <div class="zscore-panel">
        <div class="zscore-value">Z = {{ z_score }}</div>
        <div class="percentile">分位: {{ percentile }}%</div>
        <div class="signal-text">{{ signal_text }}</div>
    </div>

    <!-- K线图 -->
    <canvas id="kline-chart"></canvas>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
// 渲染K线图+分位数带
// 复用现有Chart.js配置，添加分位数带区域填充
</script>
```

**验收标准**：
- [ ] K线图正确渲染
- [ ] 分位数带以区域填充显示
- [ ] Z-Score和信号文本正确显示
- [ ] 页面加载<2秒

**依赖**：TASK-009-010, TASK-009-011

**状态**：⬜ 待执行

---

## 任务依赖图

```
TASK-001 (创建App)
    │
    └──▶ TASK-002 (配置路由)
            │
            ├──▶ TASK-003 (EMACalculator)
            │       │
            │       └──▶ TASK-004 (EWMACalculator)
            │               │
            │               └──▶ TASK-005 (ZScoreCalculator)
            │                       │
            │                       └──▶ TASK-006 (SignalEvaluator)
            │                               │
            │                               └──▶ TASK-007 (DDPSService)
            │                                       │
            │                                       ├──▶ TASK-008 (ChartDataService)
            │                                       │       │
            │                                       │       └──▶ TASK-011 (KLineChartAPI)
            │                                       │               │
            │                                       │               └──▶ TASK-014 (详情页)
            │                                       │
            │                                       ├──▶ TASK-010 (DDPSCalculateAPI)
            │                                       │       │
            │                                       │       └──▶ TASK-014 (详情页)
            │                                       │
            │                                       └──▶ TASK-012 (scan_ddps命令)
            │
            └──▶ TASK-009 (ContractListAPI)
                    │
                    └──▶ TASK-013 (Dashboard页面)
```

---

## 执行顺序建议

| 顺序 | 任务ID | 任务名称 | 预估 |
|------|--------|---------|------|
| 1 | TASK-009-001 | 创建ddps_z Django App | 5分钟 |
| 2 | TASK-009-002 | 配置URL路由和Settings | 10分钟 |
| 3 | TASK-009-003 | 实现EMACalculator | 20分钟 |
| 4 | TASK-009-004 | 实现EWMACalculator | 30分钟 |
| 5 | TASK-009-005 | 实现ZScoreCalculator | 20分钟 |
| 6 | TASK-009-006 | 实现SignalEvaluator | 15分钟 |
| 7 | TASK-009-007 | 实现DDPSService | 30分钟 |
| 8 | TASK-009-008 | 实现ChartDataService | 25分钟 |
| 9 | TASK-009-009 | 实现ContractListAPI | 10分钟 |
| 10 | TASK-009-010 | 实现DDPSCalculateAPI | 10分钟 |
| 11 | TASK-009-011 | 实现KLineChartAPI | 10分钟 |
| 12 | TASK-009-012 | 实现scan_ddps命令 | 15分钟 |
| 13 | TASK-009-013 | 实现Dashboard页面 | 30分钟 |
| 14 | TASK-009-014 | 实现合约详情页 | 45分钟 |

---

## 验收清单

### 功能验收
- [ ] 输入任意交易对，能正确计算Z-Score
- [ ] Z-Score范围合理（大多数在-3到+3之间）
- [ ] 分位数带能随波动率自动扩张/收缩
- [ ] 量价验证能正确区分强确认/弱信号
- [ ] Dashboard能展示所有合约并支持搜索
- [ ] K线图能正确渲染分位数带

### 性能验收
- [ ] 单币种计算时间 < 100ms
- [ ] Dashboard加载 < 500ms
- [ ] K线图渲染 < 500ms

### 代码质量
- [ ] 所有计算器有单元测试
- [ ] API有集成测试
- [ ] 代码符合项目规范
