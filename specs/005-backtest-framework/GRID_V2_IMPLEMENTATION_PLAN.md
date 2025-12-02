# 网格策略 V2.0 实施计划

**创建时间**: 2025-11-30
**更新时间**: 2025-11-30
**状态**: 进行中
**基准文档**: [specs/GRID_STRATEGY_V2_CONFIRMATION.md](../GRID_STRATEGY_V2_CONFIRMATION.md)

---

## 📋 实施概览

本计划将实现完整的箱体网格交易策略 V2.0，包括：
- ✅ 动态网格计算（集成FourPeaksAnalyzer）
- ✅ 渐进式买入/卖出算法（指数衰减权重函数）
- ✅ 独立仓位管理（现金约束+理论上限）
- ✅ 分级止盈（R1/R2比例分配）
- ✅ 双向止损机制（多头/空头对称）
- ✅ 完整的回测框架集成

---

## 🎯 阶段划分

### 阶段 1: GridPosition 数据模型（已完成）
**目标**: 创建支持R1/R2分级止盈的GridPosition模型
**验收标准**:
- [x] GridPosition 模型创建完成
- [x] 支持R1/R2分级止盈字段
- [x] 数据库迁移文件生成
- [x] 模型包含zone边界字段

**关键字段**:
- `buy_level`: 支撑位层级（support_1/support_2）
- `sell_target_r1_*`: 压力位1卖出目标（价格、比例、已卖数量、区间）
- `sell_target_r2_*`: 压力位2卖出目标（价格、比例、已卖数量、区间）
- `buy_zone_weight`: 买入时的权重（指数衰减）
- `status`: open/partial/closed

**状态**: ✅ 已完成

---

## 阶段 2: 网格计算服务 - 集成 FourPeaksAnalyzer

**目标**: 创建动态网格价格计算服务，复用现有成交量分析算法

**验收标准**:
- [x] DynamicGridCalculator 服务创建
- [x] 成功调用 FourPeaksAnalyzer.analyze()
- [x] 正确提取4个关键层级价格
- [x] 单元测试覆盖核心逻辑

**实现要点**:
```python
# backtest/services/dynamic_grid_calculator.py (新建)
from vp_squeeze.services.four_peaks_analyzer import FourPeaksAnalyzer

class DynamicGridCalculator:
    """动态网格价格计算器 - 基于多周期成交量分析"""

    def __init__(self):
        self.analyzer = FourPeaksAnalyzer()

    def calculate_grid_levels(
        self,
        symbol: str,
        current_time: datetime,
        current_price: float
    ) -> Dict[str, float]:
        """
        计算4个网格层级价格

        Returns:
            {
                'resistance_2': 3300,
                'resistance_1': 3100,
                'support_1': 2900,
                'support_2': 2700
            }
        """
        # 1. 调用 FourPeaksAnalyzer 分析
        analysis = self.analyzer.analyze(
            symbol=symbol,
            current_time=current_time
        )

        # 2. 提取4个关键层级
        key_levels = analysis.key_levels  # List[KeyLevel]

        # 3. 分类并返回
        result = {}
        for level in key_levels:
            if level.level_type == 'resistance2':
                result['resistance_2'] = level.price
            elif level.level_type == 'resistance1':
                result['resistance_1'] = level.price
            elif level.level_type == 'support1':
                result['support_1'] = level.price
            elif level.level_type == 'support2':
                result['support_2'] = level.price

        return result
```

**依赖**:
- vp_squeeze/services/four_peaks_analyzer.py (已存在)
- vp_squeeze/services/binance_kline_service.py (已存在)

**测试**:
```python
# tests/backtest/test_dynamic_grid_calculator.py
def test_calculate_grid_levels():
    calc = DynamicGridCalculator()
    levels = calc.calculate_grid_levels(
        symbol='ETHUSDT',
        current_time=datetime.now(),
        current_price=3000
    )

    assert 'support_1' in levels
    assert 'support_2' in levels
    assert 'resistance_1' in levels
    assert 'resistance_2' in levels
    assert levels['support_1'] < levels['resistance_1']
```

**状态**: 未开始

---

## 阶段 3: 网格策略核心 - GridStrategyV2

**目标**: 实现支持重复激活的4层网格交易策略

**验收标准**:
- [x] GridStrategyV2 类实现完成
- [x] 买入逻辑：支撑位触发，记录卖出目标价
- [x] 卖出逻辑：查询 sell_target_price，重新激活网格
- [x] 网格状态管理正确
- [x] 回测运行成功，交易次数显著增加（>10次/180天）

**实现要点**:

```python
# backtest/services/grid_strategy_v2.py (新建)

class GridLevel:
    """单个网格的运行时状态"""
    def __init__(self, level_name: str, weight: int, allocated_amount: float):
        self.level_name = level_name  # 'support_1', 'support_2'
        self.weight = weight
        self.allocated_amount = allocated_amount
        self.status = 'available'  # 'available' | 'filled'
        self.current_position_id: Optional[int] = None

    def is_available(self) -> bool:
        return self.status == 'available'

    def activate(self):
        """重新激活（卖出后调用）"""
        self.status = 'available'
        self.current_position_id = None


class GridStrategyV2:
    """动态4层网格策略 - 支持重复激活"""

    def __init__(self, config: dict, backtest_result_id: int):
        self.config = config
        self.backtest_result_id = backtest_result_id

        # 初始化4个网格
        total_weight = 10  # 3+2+2+3
        self.grids = {
            'support_2': GridLevel('support_2', 3, config['initial_cash'] * 0.3),
            'support_1': GridLevel('support_1', 2, config['initial_cash'] * 0.2),
            'resistance_1': GridLevel('resistance_1', 2, config['initial_cash'] * 0.2),
            'resistance_2': GridLevel('resistance_2', 3, config['initial_cash'] * 0.3),
        }

        self.grid_calculator = DynamicGridCalculator()
        self.cash = config['initial_cash']
        self.fee_rate = config.get('commission', 0.001)

    def on_new_bar(
        self,
        current_time: datetime,
        current_price: float,
        prev_price: float,
        df_history: pd.DataFrame
    ):
        """每根K线调用一次"""

        # 1. 动态计算当前网格价格
        grid_prices = self.grid_calculator.calculate_grid_levels(
            symbol=self.config['symbol'],
            current_time=current_time,
            current_price=current_price
        )

        # 2. 检查买入信号（价格下穿支撑位）
        self._check_buy_signals(
            current_price, prev_price,
            grid_prices, current_time
        )

        # 3. 检查卖出信号（价格上穿压力位）
        self._check_sell_signals(
            current_price, prev_price,
            current_time
        )

    def _check_buy_signals(
        self,
        current_price: float,
        prev_price: float,
        grid_prices: Dict[str, float],
        current_time: datetime
    ):
        """检查支撑位买入"""

        # 遍历支撑位网格
        for level_name in ['support_1', 'support_2']:
            grid = self.grids[level_name]
            trigger_price = grid_prices[level_name]

            # 检查：价格下穿 && 网格可用
            if prev_price > trigger_price >= current_price and grid.is_available():
                # 执行买入
                self._execute_buy(
                    grid=grid,
                    buy_price=current_price,
                    sell_target_price=grid_prices['resistance_1'],  # 动态目标价
                    current_time=current_time
                )

    def _execute_buy(
        self,
        grid: GridLevel,
        buy_price: float,
        sell_target_price: float,
        current_time: datetime
    ):
        """执行买入操作"""

        if self.cash < grid.allocated_amount:
            return  # 资金不足

        # 计算买入数量
        amount = grid.allocated_amount / buy_price
        cost = grid.allocated_amount

        # 扣除资金
        self.cash -= cost

        # ⭐ 创建持仓记录（关键：记录卖出目标价）
        position = GridPosition.objects.create(
            backtest_result_id=self.backtest_result_id,
            grid_level=grid.level_name,
            buy_price=buy_price,
            buy_time=current_time,
            amount=amount,
            cost=cost,
            sell_target_price=sell_target_price,  # ← 动态记录
            status='open'
        )

        # 更新网格状态
        grid.status = 'filled'
        grid.current_position_id = position.id

    def _check_sell_signals(
        self,
        current_price: float,
        prev_price: float,
        current_time: datetime
    ):
        """检查是否触发卖出"""

        # 查找所有卖出目标价 <= 当前价格的未平仓持仓
        positions = GridPosition.objects.filter(
            backtest_result_id=self.backtest_result_id,
            status='open',
            sell_target_price__lte=current_price
        )

        for pos in positions:
            self._execute_sell(pos, current_price, current_time)

    def _execute_sell(
        self,
        position: GridPosition,
        sell_price: float,
        current_time: datetime
    ):
        """执行卖出操作"""

        # 计算收益
        revenue_before_fee = position.amount * sell_price
        fee = revenue_before_fee * self.fee_rate
        revenue = revenue_before_fee - fee
        pnl = revenue - position.cost

        # 更新数据库
        position.sell_price = sell_price
        position.sell_time = current_time
        position.revenue = revenue
        position.pnl = pnl
        position.status = 'closed'
        position.save()

        # 增加现金
        self.cash += revenue

        # ⭐⭐⭐ 关键：重新激活对应网格
        grid = self.grids[position.grid_level]
        grid.activate()  # 可以再次买入！
```

**测试场景**:
1. 价格震荡：2900 → 2700 → 3100 → 2900 → 3100
2. 预期：支撑位1触发2次买入，压力位1触发2次卖出
3. 验证：GridPosition 记录 >= 2条，且都已平仓

**状态**: 未开始

---

## 阶段 4: 回测引擎集成

**目标**: 将 GridStrategyV2 集成到现有回测系统

**验收标准**:
- [x] BacktestEngine 支持 'grid_v2' 策略类型
- [x] 配置参数正确传递
- [x] 回测结果正确保存
- [x] Web API 支持新策略

**实现要点**:

```python
# backtest/services/backtest_engine.py (修改)

class BacktestEngine:
    def run_backtest(self, config: dict) -> dict:
        # ...

        if config['strategy_type'] == 'grid_v2':
            # 创建回测结果记录
            backtest_result = BacktestResult.objects.create(
                symbol=config['symbol'],
                # ...
            )

            # 初始化策略
            strategy = GridStrategyV2(
                config=config,
                backtest_result_id=backtest_result.id
            )

            # 运行回测
            for i in range(1, len(df)):
                current_bar = df.iloc[i]
                prev_bar = df.iloc[i-1]

                strategy.on_new_bar(
                    current_time=current_bar['timestamp'],
                    current_price=current_bar['close'],
                    prev_price=prev_bar['close'],
                    df_history=df.iloc[:i]
                )

            # 计算最终结果
            result = self._calculate_metrics(strategy, df)

            # 保存结果
            backtest_result.total_return = result['total_return']
            backtest_result.save()

            return result
```

**配置示例**:
```python
config = {
    'symbol': 'ETHUSDT',
    'interval': '4h',
    'days': 180,
    'initial_cash': 10000,
    'strategy_type': 'grid_v2',  # ← 新策略
    'commission': 0.001,
}
```

**测试**:
```bash
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v2 \
  --days 180
```

**状态**: 未开始

---

## 阶段 5: Web界面和测试验证

**目标**: 更新Web界面支持新策略，并进行完整测试

**验收标准**:
- [x] Web界面下拉菜单添加 "Grid V2 (动态4层)"
- [x] API 正确处理 strategy_type=grid_v2
- [x] 回测结果正确展示
- [x] 交易次数显著增加（对比旧策略）
- [x] 生成对比分析报告

**实现要点**:

```html
<!-- backtest/templates/backtest/index.html (修改) -->
<select id="strategyType">
  <option value="grid">Grid (经典网格)</option>
  <option value="grid_v2" selected>Grid V2 (动态4层)</option>
  <option value="buy_hold">买入持有</option>
</select>
```

```python
# backtest/views.py (修改)
def run_backtest_api(request):
    # ...
    strategy_type = data.get('strategy_type', 'grid_v2')  # 默认使用V2
    # ...
```

**对比测试**:
```bash
# 运行旧策略
python manage.py run_backtest --symbol ETHUSDT --interval 4h --strategy grid

# 运行新策略
python manage.py run_backtest --symbol ETHUSDT --interval 4h --strategy grid_v2

# 生成对比报告
python manage.py compare_results --strategies grid grid_v2
```

**预期结果**:
| 指标 | Grid V1 (旧) | Grid V2 (新) | 改进 |
|------|-------------|-------------|------|
| 交易次数 | 4 | 20-40 | +400% |
| 总收益率 | 23.97% | > 20% | 保持 |
| 夏普比率 | 2.44 | > 2.0 | 保持 |
| 最大回撤 | 0.11% | < 1% | 可控 |

**状态**: 未开始

---

## 总体进度

- [ ] 阶段 1: 数据模型层 (0%)
- [ ] 阶段 2: 网格计算服务 (0%)
- [ ] 阶段 3: 网格策略核心 (0%)
- [ ] 阶段 4: 回测引擎集成 (0%)
- [ ] 阶段 5: Web界面和测试 (0%)

**总进度**: 0/5 (0%)

---

## 关键风险与缓解

**风险1**: FourPeaksAnalyzer 可能返回不足4个层级
- **缓解**: 添加降级逻辑，使用固定百分比作为备选

**风险2**: 网格重复激活导致资金不足
- **缓解**: 严格检查 cash >= allocated_amount

**风险3**: 动态价格变化过大，目标价格失效
- **缓解**: 记录历史价格，分析价格变化率

---

## 下一步行动

1. **立即开始**: 阶段 1 - 创建 GridPosition 模型
2. **依赖确认**: 验证 FourPeaksAnalyzer 可正常调用
3. **测试数据**: 准备 ETHUSDT 180天 4h 数据

**开始时间**: 2025-11-30
