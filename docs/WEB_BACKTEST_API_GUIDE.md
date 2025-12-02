# 网格交易回测Web可视化系统使用指南

## 🚀 快速启动

### 1. 启动服务器

```bash
# 方式一：使用启动脚本（推荐）
./start_web_backtest.sh

# 方式二：手动启动
python manage.py runserver 8001
```

### 2. 访问系统

在浏览器中打开：
```
http://127.0.0.1:8001/backtest/
```

## 📊 功能特性

### ✅ 已完成功能

1. **智能数据管理**
   - 优先使用数据库中的历史数据
   - 数据不足时自动从Binance API获取
   - 支持批量获取（突破1000条限制）

2. **策略配置**
   - 交易对选择（如：ETHUSDT, BTCUSDT）
   - 时间周期选择（1h, 4h, 1d）
   - 回测天数设置
   - 初始资金配置
   - 网格参数调整：
     * 网格步长（grid_step_pct）
     * 网格层数（grid_levels）
     * 订单大小（order_size_pct）
     * 止损百分比（stop_loss_pct）

3. **可视化展示**
   - 价格K线图表（Chart.js）
   - 买卖信号标记
   - 网格线显示
   - 止损线显示
   - 权益曲线
   - 实时统计数据

4. **回放控制**
   - 播放/暂停按钮
   - 时间轴滑块
   - 速度调节（0.5x - 5x）
   - 逐帧查看

5. **交易分析**
   - 交易日志展示
   - 盈亏统计
   - 胜率计算
   - 风险指标（最大回撤、夏普比率）

## 🧪 API测试

系统提供了RESTful API接口，可以通过编程方式调用：

### 运行回测API

```bash
python test_backtest_api.py
```

**API端点**: `POST /backtest/api/run/`

**请求参数示例**:
```json
{
    "symbol": "ETHUSDT",
    "interval": "4h",
    "days": 180,
    "initial_cash": 10000,
    "strategy_type": "grid",
    "grid_step_pct": 2.0,
    "grid_levels": 10,
    "order_size_pct": 10.0,
    "stop_loss_pct": 15.0
}
```

**响应数据结构**:
```json
{
    "success": true,
    "result": {
        "total_return": 23.97,
        "sharpe_ratio": 2.44,
        "max_drawdown": 0.11,
        "win_rate": 100.00,
        "total_trades": 4,
        "profitable_trades": 4,
        "losing_trades": 0
    },
    "data": {
        "prices": [...],
        "signals": [...],
        "positions": [...],
        "equity": [...],
        "trades": [...]
    },
    "grid_info": {
        "base_price": 3500.00,
        "levels": [...],
        "stop_loss_price": 2975.00
    }
}
```

## 📝 使用流程

### 步骤1：配置回测参数

在Web界面左侧配置面板中设置：
1. 选择交易对（如ETHUSDT）
2. 选择时间周期（如4h）
3. 设置回测天数（如180天）
4. 设置初始资金（如10000）
5. 配置网格参数：
   - 网格步长：2%（推荐1-3%）
   - 网格层数：10（推荐5-20）
   - 止损：15%（推荐10-20%）

### 步骤2：运行回测

1. 点击"运行回测"按钮
2. 系统自动检查数据
3. 数据不足时自动获取
4. 执行回测计算
5. 显示结果

### 步骤3：查看结果

**图表区域**：
- 价格走势图（蜡烛图）
- 网格买入/卖出线
- 止损线（红色虚线）
- 买入信号（绿色标记）
- 卖出信号（红色标记）
- 权益曲线图

**统计面板**：
- 总收益率
- 夏普比率
- 最大回撤
- 胜率
- 交易次数统计

**交易日志**：
- 每笔交易详情
- 进场/出场时间
- 进场/出场价格
- 盈亏金额
- 收益率

### 步骤4：回放分析

1. 使用播放按钮查看策略执行过程
2. 调整速度（0.5x-5x）
3. 拖动时间轴到任意时刻
4. 逐帧分析关键决策点

## 🎯 测试结果示例

基于ETHUSDT 4h 180天数据的测试：

```
✅ 回测成功！

📊 回测结果:
  总收益率: 23.97%
  夏普比率: 2.44
  最大回撤: 0.11%
  胜率: 100.00%
  总交易次数: 4
  盈利交易: 4
  亏损交易: 0

📈 数据信息:
  价格数据点: 1080
  买入信号: 4
  卖出信号: 4
  权益曲线点数: 1080
```

## 🔧 技术架构

**后端技术栈**：
- Django 4.2.8
- vectorbt 0.26.2（回测引擎）
- SQLite（数据存储）
- Binance API v3（数据源）

**前端技术栈**：
- Chart.js 4.4.0（图表库）
- Vanilla JavaScript（无框架）
- CSS Grid/Flexbox（响应式布局）

**API设计**：
- RESTful JSON接口
- CSRF保护
- 错误处理
- 日志记录

## 📂 项目结构

```
backtest/
├── views.py              # Django视图和API
├── urls.py               # URL路由配置
├── models.py             # 数据模型（KLine, BacktestResult）
├── templates/
│   └── backtest/
│       └── index.html    # Web界面
└── services/
    ├── data_fetcher.py   # 数据获取服务
    ├── backtest_engine.py # 回测引擎
    ├── grid_strategy_vbt.py # 网格策略
    └── buy_hold_strategy.py # 买入持有策略

test_backtest_api.py      # API测试脚本
start_web_backtest.sh     # 启动脚本
```

## 🐛 常见问题

### Q: 端口8001被占用？
A: 修改启动命令使用其他端口：
```bash
python manage.py runserver 8002
```

### Q: 数据获取失败？
A: 检查网络连接和Binance API访问，或使用已有数据库数据。

### Q: 回测很慢？
A:
- 减少回测天数
- 使用更大的时间周期（如1d替代1h）
- 确保数据已在数据库中

### Q: 图表不显示？
A:
- 检查浏览器控制台错误
- 确认Chart.js CDN加载成功
- 刷新页面重试

## 🚀 后续优化方向

1. **性能优化**
   - 数据缓存机制
   - 异步任务队列
   - 结果预计算

2. **功能增强**
   - 多策略对比
   - 参数优化工具
   - 风险分析报告
   - 导出功能（PDF/Excel）

3. **用户体验**
   - 保存配置
   - 历史记录
   - 分享链接
   - 移动端适配

## 📞 支持

遇到问题？
1. 查看Django日志：控制台输出
2. 查看浏览器控制台
3. 检查数据库状态
4. 查看API响应错误信息

---

**最后更新**: 2025-11-28
**版本**: v1.0.0
