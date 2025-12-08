# Quick Start Guide: 自动化网格交易系统

本指南帮助你快速上手自动化网格交易系统,从安装配置到启动第一个网格策略。

---

## 前置条件

### 系统要求
- ✅ Python 3.8+
- ✅ PostgreSQL 12+ 或 SQLite 3.31+
- ✅ 稳定的网络连接(访问币安API)
- ✅ 至少 512MB 可用内存
- ✅ 建议24/7运行的服务器环境

### 交易所账户
- ✅ 币安(Binance)账户并完成KYC
- ✅ 开通永续合约交易权限
- ✅ 创建API Key并设置IP白名单
- ✅ 账户余额充足(建议至少100 USDT)

### API权限要求
- ✅ 读取账户信息 (Read)
- ✅ 现货与合约交易 (Enable Futures)
- ⚠️ **不要**勾选"提币"权限(安全考虑)

---

## 安装步骤

### 1. 克隆项目(如果尚未完成)

```bash
git checkout 002-auto-grid-trading
cd /path/to/crypto_exchange_news_crawler
```

### 2. 安装依赖

```bash
# 创建虚拟环境(推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装Python依赖
pip install -r requirements.txt

# 如果requirements.txt未包含网格交易依赖,手动安装:
pip install python-binance websockets pandas numpy
```

### 3. 配置数据库

#### 选项A: 使用SQLite (开发环境)

```bash
# settings.py 中已配置SQLite,无需额外操作
python manage.py migrate
```

#### 选项B: 使用PostgreSQL (生产环境)

```bash
# 创建数据库
createdb grid_trading_db

# 配置 settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'grid_trading_db',
        'USER': 'your_username',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# 执行迁移
python manage.py migrate
```

### 4. 配置交易所API Key

#### 方式A: 环境变量(推荐)

```bash
# 创建 .env 文件
cat > .env << EOF
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
EOF

# 确保 .env 在 .gitignore 中
echo ".env" >> .gitignore
```

#### 方式B: Django Settings

```python
# crypto_exchange_news_crawler/settings.py
BINANCE_API_KEY = 'your_api_key_here'
BINANCE_API_SECRET = 'your_api_secret_here'
```

⚠️ **安全警告**: 切勿将API密钥提交到Git仓库!

### 5. 验证安装

```bash
# 检查Django项目
python manage.py check

# 检查币安API连接
python manage.py test_binance_connection

# 预期输出:
# ✅ Binance API连接成功
# 账户类型: Futures
# 可用余额: 1,250.50 USDT
```

---

## 快速开始: 第一个网格策略

### 场景: 创建BTC做空网格

假设你认为BTC价格在60,000 ~ 65,000 USDT区间震荡,希望通过做空网格获利。

### Step 1: 创建网格配置

```bash
python manage.py create_grid_config \
  --name btc_short_demo \
  --exchange binance \
  --symbol BTCUSDT \
  --mode short \
  --upper 65000 \
  --lower 60000 \
  --levels 20 \
  --amount 0.01 \
  --max-position 0.2 \
  --stop-loss-buffer 0.005
```

**输出**:
```
✅ 网格配置创建成功
配置名称: btc_short_demo
交易所: binance
交易对: BTCUSDT
网格模式: SHORT (做空网格)
价格区间: 60000 ~ 65000
网格数量: 20层
网格间距: 250 USDT (0.42%)
```

### Step 2: 查看配置详情

```bash
python manage.py show_grid_config --name btc_short_demo
```

### Step 3: 启动网格策略

```bash
python manage.py start_grid --config btc_short_demo
```

**输出**:
```
🚀 正在启动网格策略: btc_short_demo

[1/6] 加载配置...                    ✅ 完成
[2/6] 连接币安WebSocket...           ✅ 完成
[3/6] 同步账户状态...                 ✅ 完成
[4/6] 计算网格层级...                 ✅ 完成
[5/6] 挂初始订单...                   ✅ 完成 (8/8)
[6/6] 启动主循环...                   ✅ 完成

✅ 网格策略已启动
进程PID: 12345
```

### Step 4: 实时监控

```bash
# 查看实时状态
python manage.py grid_status --config btc_short_demo --watch

# 或打开另一个终端查看日志
tail -f /var/log/grid/btc_short_demo.log
```

### Step 5: 查看统计数据

```bash
# 等待策略运行一段时间后(如1小时),查看统计
python manage.py grid_stats --config btc_short_demo

# 生成详细报告
python manage.py grid_report --config btc_short_demo
```

### Step 6: 停止策略

```bash
# 停止策略并平仓
python manage.py stop_grid --config btc_short_demo

# 或仅暂停(保留持仓)
python manage.py pause_grid --config btc_short_demo
```

---

## 常见场景

### 场景1: 修改网格参数

```bash
# 先停止策略
python manage.py stop_grid --config btc_short_demo

# 修改配置
python manage.py update_grid_config \
  --name btc_short_demo \
  --stop-loss-buffer 0.01  # 调整止损缓冲区为1%

# 重新启动
python manage.py start_grid --config btc_short_demo
```

### 场景2: 同时运行多个网格

```bash
# 创建第二个配置(ETH中性网格)
python manage.py create_grid_config \
  --name eth_neutral_demo \
  --exchange binance \
  --symbol ETHUSDT \
  --mode neutral \
  --upper 3500 \
  --lower 3000 \
  --levels 20 \
  --amount 0.1 \
  --max-position 2.0

# 启动两个策略
python manage.py start_grid --config btc_short_demo
python manage.py start_grid --config eth_neutral_demo

# 监控所有策略
python manage.py grid_monitor --all
```

### 场景3: 使用Django Admin管理

```bash
# 启动Django开发服务器
python manage.py runserver

# 访问 http://localhost:8000/admin
# 登录后导航到 Grid Trading > Grid Configs
```

---

## 故障排除

### 问题1: WebSocket连接失败

**错误信息**:
```
❌ 错误: WebSocket连接失败
Connection refused
```

**解决方法**:
1. 检查网络连接: `ping api.binance.com`
2. 检查API Key配置是否正确
3. 确认币安服务是否正常(访问 https://www.binance.com/en/futures/BTCUSDT)
4. 检查防火墙设置

### 问题2: 订单创建失败

**错误信息**:
```
BinanceAPIException: Order would immediately match and take
```

**解决方法**:
- 这是正常的,说明价格已经穿过网格层级,订单会被跳过
- 系统会自动继续运行,无需干预

### 问题3: 余额不足

**错误信息**:
```
❌ 错误: 余额不足
Available: 10 USDT, Required: 50 USDT
```

**解决方法**:
1. 充值账户余额
2. 或减少`--amount`参数(单笔金额)
3. 或减少`--levels`参数(网格数量)

### 问题4: 策略频繁止损

**现象**: 策略启动后不久就触发止损

**解决方法**:
1. 检查市场行情,是否出现单边突破
2. 调整价格区间(`--upper`, `--lower`)更贴近当前价格
3. 增加止损缓冲区(`--stop-loss-buffer`)
4. 考虑使用中性网格(双向交易)而非做空/做多

### 问题5: 成交率低

**现象**: `grid_stats`显示成交率 < 50%

**解决方法**:
1. 减少网格数量(`--levels`),增大网格间距
2. 确认价格区间是否覆盖当前市场波动范围
3. 检查市场流动性是否充足

---

## 生产环境部署

### 1. 使用Supervisor管理进程

```bash
# 安装Supervisor
sudo apt-get install supervisor  # Ubuntu/Debian
# 或 brew install supervisor  # macOS

# 创建配置文件
sudo nano /etc/supervisor/conf.d/grid_btc_short.conf
```

**配置内容**:
```ini
[program:grid_btc_short]
command=/path/to/venv/bin/python /path/to/project/manage.py start_grid --config btc_short_demo
directory=/path/to/project
autostart=true
autorestart=true
stderr_logfile=/var/log/grid/btc_short.err.log
stdout_logfile=/var/log/grid/btc_short.out.log
user=your_username
environment=PYTHONUNBUFFERED=1
```

```bash
# 重新加载Supervisor
sudo supervisorctl reread
sudo supervisorctl update

# 查看状态
sudo supervisorctl status

# 手动启动/停止
sudo supervisorctl start grid_btc_short
sudo supervisorctl stop grid_btc_short
```

### 2. 配置日志轮转

```bash
# 创建logrotate配置
sudo nano /etc/logrotate.d/grid-trading
```

**配置内容**:
```
/var/log/grid/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0640 your_username your_username
}
```

### 3. 设置监控告警

```bash
# 创建监控脚本
cat > /path/to/monitor_grid.sh << 'EOF'
#!/bin/bash
STATUS=$(python manage.py grid_status --config btc_short_demo | grep "状态")

if [[ $STATUS == *"已停止"* ]]; then
    echo "警告: 网格策略已停止!" | mail -s "Grid Alert" admin@example.com
fi
EOF

# 添加到crontab (每5分钟检查)
crontab -e
# 添加: */5 * * * * /path/to/monitor_grid.sh
```

---

## 下一步

### 深入学习
1. 📖 阅读 [spec.md](./spec.md) 了解完整功能需求
2. 📖 阅读 [research.md](./research.md) 了解技术选型
3. 📖 阅读 [data-model.md](./data-model.md) 了解数据模型

### 高级功能(后续实现)
- 🚀 回测引擎: 基于历史数据验证策略
- 🚀 参数优化: 自动寻找最佳网格参数
- 🚀 多交易所支持: OKX, Bybit等
- 🚀 告警通知: 邮件/钉钉/Telegram通知

### 参与开发
- 📝 查看 [tasks.md](./tasks.md) 了解待实现任务(使用`/speckit.tasks`生成)
- 🐛 提交Issue: 报告Bug或提出建议
- 🔧 提交PR: 贡献代码(遵循项目宪法原则)

---

## 安全提示

⚠️ **重要安全建议**:

1. **API密钥安全**:
   - 使用环境变量或加密存储API密钥
   - 定期轮换API密钥
   - 设置IP白名单
   - 永不提交密钥到Git仓库

2. **仓位管理**:
   - 初期使用小仓位测试(如0.01 BTC)
   - 单个策略资金占比 ≤ 10%
   - 设置合理的止损缓冲区

3. **风险控制**:
   - 避免在单边行情中使用做空/做多网格
   - 定期检查策略表现,及时调整
   - 不要让策略无人看管运行数天

4. **备份恢复**:
   - 定期备份数据库
   - 记录所有策略配置参数
   - 准备应急止损方案

---

## 支持与帮助

- 📧 技术支持: [提交Issue](https://github.com/your-repo/issues)
- 📖 完整文档: 参见 `specs/002-auto-grid-trading/` 目录
- 💬 社区讨论: [加入讨论群](链接待补充)

---

**祝你网格交易愉快! 🚀**
