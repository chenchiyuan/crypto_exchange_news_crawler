# GRVT网格交易使用指南

## 概述

本指南介绍如何使用GRVT交易所进行ETH网格交易。系统已集成GRVT官方Python SDK (`grvt-pysdk`)，支持实盘交易。

## 环境要求

### 1. Python依赖

```bash
pip install grvt-pysdk
```

已安装的关键依赖：
- `grvt-pysdk==0.2.1` - GRVT官方SDK
- `eth-account==0.13.7` - 以太坊账户管理
- `websockets==13.1` - WebSocket支持
- `aiohttp==3.13.2` - 异步HTTP客户端

### 2. 环境变量配置

创建 `.env` 文件或设置以下环境变量：

```bash
# GRVT API凭据
export GRVT_API_KEY="your_api_key"
export GRVT_PRIVATE_KEY="0x..."  # 用于订单签名
export GRVT_TRADING_ACCOUNT_ID="your_account_id"
export GRVT_ENV="testnet"  # testnet 或 prod
```

**重要说明：**
- `GRVT_API_KEY`: 从GRVT平台获取的API密钥
- `GRVT_PRIVATE_KEY`: 用于签名交易的私钥（必须以0x开头）
- `GRVT_TRADING_ACCOUNT_ID`: 您的交易账户ID
- `GRVT_ENV`: 建议先使用 `testnet` 测试

## 快速开始

### 第一步：创建ETH网格配置

运行配置脚本创建ETH网格交易配置：

```bash
python scripts/setup_eth_grid.py
```

**默认配置：**
- 交易对: ETHUSDT
- 价格范围: 3000 - 3300 USDT
- 网格层数: 20层
- 单笔开仓: 0.01 ETH
- 最大持仓: 0.2 ETH
- 网格模式: 做空网格(SHORT)

脚本输出示例：

```
============================================================
创建ETH网格交易配置
============================================================

✓ 配置创建成功!
  ID: 1
  名称: ETH_SHORT_GRID_TEST
  交易对: ETHUSDT
  网格模式: SHORT
  价格区间: 3000 - 3300
  网格层数: 20
  网格间距: 1.5789%
  单笔数量: 0.01 ETH
  最大持仓: 0.2 ETH
  状态: 激活
```

### 第二步：设置环境变量

```bash
export GRVT_API_KEY=your_api_key
export GRVT_PRIVATE_KEY=0x...
export GRVT_TRADING_ACCOUNT_ID=your_account_id
export GRVT_ENV=testnet
```

### 第三步：启动网格交易

**方式1：使用启动脚本（推荐）**

```bash
python scripts/start_eth_grid.py
```

启动脚本会：
1. ✓ 检查环境变量
2. ✓ 测试GRVT适配器连接
3. ✓ 加载网格配置
4. ✓ 请求确认后启动
5. ✓ 开始运行网格策略

**方式2：使用Django管理命令**

```bash
# 使用配置ID
python manage.py start_grid --config-id 1

# 使用配置名称
python manage.py start_grid --config-name ETH_SHORT_GRID_TEST

# 指定交易所
python manage.py start_grid --config-id 1 --exchange grvt

# 模拟模式（不连接交易所）
python manage.py start_grid --config-id 1 --dry-run
```

### 第四步：监控网格状态

**命令行查看：**

```bash
python manage.py grid_status --config-id 1
```

**Web后台查看：**

1. 启动Django服务器：
```bash
python manage.py runserver
```

2. 访问：
```
http://localhost:8000/grid-trading/grids/
```

可以看到：
- 网格列表
- 网格详情
- 层级状态
- 运行历史
- 事件日志

## 系统架构

### 1. 适配器层

```
grid_trading/services/exchange/
├── adapter.py           # 抽象基类
├── types.py             # 类型定义
├── grvt_adapter.py      # GRVT实现（基于grvt-pysdk）
└── factory.py           # 工厂模式
```

**GRVT适配器特性：**
- ✅ 基于官方SDK `grvt-pysdk`
- ✅ 支持异步订单操作
- ✅ 自动市场信息加载
- ✅ 订单签名自动处理
- ✅ 批量订单撤销
- ✅ 精度信息查询

### 2. 网格引擎

```python
from grid_trading.services.grid.engine import GridEngine
from grid_trading.services.exchange.factory import create_adapter

# 创建适配器
adapter = create_adapter("grvt")

# 创建引擎
engine = GridEngine(config, exchange_adapter=adapter)

# 启动
engine.start()

# 执行tick
result = engine.tick()

# 停止
engine.stop()
```

### 3. 运行模式

系统支持三种运行模式：

| 模式 | 适配器 | 用途 |
|------|--------|------|
| **回测** | None | 使用历史数据模拟 |
| **模拟** | None + `--dry-run` | 测试逻辑，不下单 |
| **实盘** | GRVTAdapter | 真实交易 |

## API使用示例

### 创建订单

```python
from grid_trading.services.exchange.factory import create_adapter

adapter = create_adapter("grvt")

order = await adapter.create_order({
    "symbol": "ETHUSDT",
    "side": "SELL",
    "type": "LIMIT",
    "quantity": 0.01,
    "price": 3200,
    "client_order_id": "my_order_1"
})

print(f"订单ID: {order['order_id']}")
```

### 撤销订单

```python
# 撤销单个订单
await adapter.cancel_order("ETHUSDT", order_id)

# 撤销所有订单
await adapter.cancel_all_orders("ETHUSDT")
```

### 获取精度信息

```python
precision = await adapter.get_precision("ETHUSDT")
print(f"价格精度: {precision['price_tick']}")
print(f"数量精度: {precision['qty_step']}")
```

### 获取账户余额

```python
balance = await adapter.get_balance()
print(balance)
```

## 网格策略说明

### 做空网格(SHORT)策略

ETH做空网格的工作原理：

1. **网格层级分布**
   - 价格范围: 3000 - 3300 USDT
   - 20层网格，间距约1.58%
   - 中心价: 3150 USDT

2. **订单放置**
   - **上方层级(价格 >= 3150)**: 放置卖单（开仓）
   - **下方层级(价格 < 3150)**: 放置买单（平仓）

3. **交易流程**
   - 价格上涨触发卖单 → 开空仓
   - 价格下跌触发买单 → 平空仓，获利

4. **盈利来源**
   - 每完成一个完整轮次（开仓→平仓）赚取网格间距差价
   - 适合震荡下跌行情

### 风险控制

- **持仓限制**: 最大0.2 ETH
- **止损缓冲**: 0.5%
- **订单同步**: 每秒刷新
- **异常保护**: 自动降级到模拟模式

## 故障排除

### 1. 环境变量未设置

```
❌ 缺少必需的环境变量:
   - GRVT_API_KEY
```

**解决方案**：设置所有必需的环境变量

### 2. 适配器连接失败

```
❌ 适配器连接失败: Missing GRVT_PRIVATE_KEY
```

**解决方案**：
- 检查私钥格式（必须以0x开头）
- 确认API密钥有效
- 验证账户ID正确

### 3. 市场信息加载失败

```
⚠ 已连接但未加载市场信息
```

**解决方案**：
- 检查网络连接
- 确认GRVT服务可访问
- 查看日志获取详细错误

### 4. 订单创建失败

**可能原因**：
- 账户余额不足
- 订单参数不符合交易所规则
- 网络问题

**解决方案**：查看详细日志

## 日志配置

在 `settings.py` 中配置日志级别：

```python
LOGGING = {
    'loggers': {
        'grid_trading': {
            'level': 'INFO',  # 改为 'DEBUG' 查看详细日志
        },
    },
}
```

## 测试清单

在实盘前，建议完成以下测试：

- [ ] ✓ 环境变量配置正确
- [ ] ✓ 适配器连接成功
- [ ] ✓ 市场信息加载正常
- [ ] ✓ 网格配置符合预期
- [ ] ✓ 账户余额充足
- [ ] ✓ 使用testnet环境测试
- [ ] ✓ 小金额测试订单创建
- [ ] ✓ 测试订单撤销
- [ ] ✓ 监控系统运行稳定

## 参考文档

### 官方文档

- **GRVT API文档**: https://api-docs.grvt.io/
- **GRVT Python SDK**: https://github.com/gravity-technologies/grvt-pysdk
- **GRVT Help Center**: https://help.grvt.io/

### 项目文档

- `docs/EXCHANGE_ADAPTER_IMPLEMENTATION.md` - 适配器实现文档
- `docs/ADAPTER_INTEGRATION_COMPLETE.md` - 集成完成报告
- `docs/GRID_DASHBOARD_GUIDE.md` - Web后台使用指南

## 注意事项

1. **安全性**
   - 不要将私钥提交到版本控制
   - 使用环境变量管理敏感信息
   - 定期轮换API密钥

2. **资金管理**
   - 建议使用testnet先测试
   - 实盘从小金额开始
   - 设置合理的持仓限制

3. **监控**
   - 定期检查网格状态
   - 关注事件日志
   - 监控账户余额

4. **性能**
   - tick间隔建议5秒以上
   - 避免频繁重启
   - 监控系统资源

## 支持

如有问题，请：
1. 查看日志文件
2. 检查环境配置
3. 参考官方文档
4. 提交Issue: https://github.com/anthropics/claude-code/issues

---

**最后更新**: 2025-12-05
**版本**: 1.0.0
