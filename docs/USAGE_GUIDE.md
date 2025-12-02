# 系统使用完整指南

**更新时间**: 2025-12-02
**版本**: v3.0.0

---

## 🎯 功能概述

本系统提供完整的加密货币交易辅助功能，包括：

### 💹 网格交易系统
- ✅ **Grid V1**: 经典固定网格交易
- ✅ **Grid V2**: 动态4层网格，支持分级止盈
- ✅ **Grid V3**: 挂单系统，资金锁定管理

### 📊 回测验证系统
- ✅ **历史数据回测**: 基于vectorbt专业回测框架
- ✅ **Web可视化**: 交互式图表和实时回放
- ✅ **参数优化**: 网格搜索和热力图分析

### 🐦 Twitter舆情分析
- ✅ **推文收集**: 从 Twitter List 自动收集推文
- ✅ **AI 分析**: 使用 DeepSeek AI 分析市场情绪
- ✅ **通知推送**: 分析完成/失败/成本告警

### 📈 VP Squeeze分析
- ✅ **成交量分析**: 识别关键支撑阻力位
- ✅ **四峰分析**: 自动计算价格层级
- ✅ **动态网格**: 为Grid策略提供价格参考

---

## 1️⃣ 快速开始

### 1.1 环境准备

```bash
# 1. 激活虚拟环境
conda activate crypto

# 2. 安装依赖
pip install -r requirements.txt

# 3. 数据库迁移
python manage.py migrate

# 4. 创建超级用户
python manage.py createsuperuser
```

### 1.2 验证配置

```bash
# 验证Twitter API
python test_api_config.py

# 验证回测系统
python manage.py run_backtest --strategy buy_hold --symbol ETHUSDT --interval 4h --days 30

# 运行测试
python manage.py test
```

**预期输出**:
```
✅ Twitter API 配置已加载
✅ DeepSeek API 配置已加载
✅ 回测系统正常
✅ 所有测试通过！
```

### 1.3 启动服务

```bash
# 启动Web回测界面 (端口8001)
./start_web_backtest.sh
# 访问 http://127.0.0.1:8001/backtest/

# 启动Django Admin (端口8000)
python manage.py runserver 0.0.0.0:8000
# 访问 http://localhost:8000/admin/
```

---

## 2️⃣ 数据统计

```bash
# 查看当前数据统计
python verify_data.py
```

**输出示例**:
```
============================================================
数据统计
============================================================
Twitter Lists: 1
Tweets: 19
Analysis Results: 6

============================================================
最近的分析结果
============================================================
任务 ID: 580cdccf-ba45-4e60-a318-60e5f3534f30
  状态: 已完成
  推文数: 8
  成本: $0.0004
  时长: 29.47s
  情绪: 多头 2 | 空头 0 | 中性 6
============================================================
```

---

## 3️⃣ 网格交易系统

### 3.1 策略选择

#### Grid V1 - 经典网格
适合新手和小资金交易者，采用固定价格网格。

```bash
# 运行Grid V1回测
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid \
  --days 180 \
  --initial-cash 10000
```

#### Grid V2 - 动态4层网格
支持动态网格计算、分级止盈（R1/R2）和重复激活。

```bash
# 运行Grid V2回测
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v2 \
  --days 180 \
  --initial-cash 10000 \
  --grid-step-pct 0.015 \
  --grid-levels 10
```

#### Grid V3 - 挂单系统
高级功能，支持资金锁定、三重约束和挂单管理。

```bash
# 运行Grid V3回测
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v3 \
  --days 90 \
  --initial-cash 10000 \
  --order-validity-days 7
```

### 3.2 Web界面使用

```bash
# 启动Web回测界面
./start_web_backtest.sh

# 访问 http://127.0.0.1:8001/backtest/
```

**操作流程**:
1. 选择交易对 (ETHUSDT)
2. 选择时间周期 (4h)
3. 选择策略类型 (Grid V2)
4. 配置参数
   - 初始资金: 10000
   - 网格步长: 1.5%
   - 网格层数: 10
   - 止损比例: 10%
5. 点击"运行回测"
6. 查看结果和动态回放

### 3.3 参数对比

| 版本 | 推荐参数 | 适用场景 |
|------|----------|----------|
| **Grid V1** | 步长1%，层数2 | 简单网格，小资金 |
| **Grid V2** | 步长1.5%，层数10 | 动态网格，频繁交易 |
| **Grid V3** | 步长1.5%，层数10，挂单7天 | 大资金，严格风控 |

### 3.4 结果分析

```bash
# 对比不同策略
python manage.py compare_results \
  --strategy1 grid_v2 \
  --strategy2 grid_v3

# 生成详细报告
python manage.py generate_report --backtest-id 123
```

**示例输出**:
```
============================================================
Grid V2 回测结果
============================================================
策略名称: Grid V2 (动态4层)
交易对: ETHUSDT
时间周期: 4h
初始资金: $10,000.00
最终价值: $12,397.00
总收益率: +23.97%
夏普比率: 2.44
最大回撤: 0.11%
总交易次数: 4
胜率: 100.00%
============================================================
```

### 3.5 策略优化

```bash
# 参数网格搜索
python manage.py optimize_params \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v2 \
  --grid-step-pcts 0.5,1.0,1.5,2.0 \
  --grid-levels 5,10,15,20

# 生成热力图
python manage.py plot_heatmap --backtest-ids 123,124,125,126
```

---

## 4️⃣ 回测验证系统

### 4.1 历史数据管理

```bash
# 获取ETH 4h数据（6个月）
python manage.py fetch_klines \
  --symbol ETHUSDT \
  --interval 4h \
  --days 180 \
  --validate

# 查看数据统计
python manage.py shell
>>> from backtest.models import KLine
>>> KLine.objects.filter(symbol='ETHUSDT', interval='4h').count()
1080

# 增量更新最新数据
python manage.py update_klines \
  --symbol ETHUSDT \
  --interval 4h \
  --limit 100
```

### 4.2 策略回测

#### 命令行回测

```bash
# 买入持有基准
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy buy_hold \
  --days 180

# 网格交易策略
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v2 \
  --days 180

# 自定义参数
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v3 \
  --days 90 \
  --initial-cash 10000 \
  --grid-step-pct 0.015 \
  --grid-levels 10 \
  --order-validity-days 7
```

#### Web界面回测

1. 访问 http://127.0.0.1:8001/backtest/
2. 配置参数
   - 交易对: ETHUSDT
   - 时间周期: 4h
   - 回测天数: 180
   - 策略类型: Grid V2 (动态4层)
   - 初始资金: 10000
3. 点击"运行回测"
4. 查看结果
   - 价格图表（网格线+买卖信号）
   - 权益曲线
   - 统计数据（收益率、夏普比率、回撤）
   - 交易明细

### 4.3 可视化分析

```bash
# 生成权益曲线图
python manage.py visualize_results --backtest-id 123

# 生成参数热力图
python manage.py plot_heatmap --backtest-ids 123,124,125

# 综合分析报告
python manage.py generate_comprehensive_report \
  --strategy grid_v2 \
  --days 180
```

**报告内容**:
- 最优参数推荐
- 收益率分布
- 回撤分析
- 交易频率统计
- 参数敏感性分析

### 4.4 实时回放

Web界面支持回测过程的动态回放：

```javascript
// 回放控制功能
- 播放/暂停按钮
- 时间轴滑块
- 速度调节（0.5x - 5x）
- 逐帧显示

// 可视化内容
- 实时价格更新
- 网格线动态计算
- 买卖信号实时标记
- 权益曲线动态绘制
```

### 4.5 回测结果评估

#### 优秀策略标准

| 指标 | 优秀 | 良好 | 一般 | 需优化 |
|------|------|------|------|--------|
| **收益率** | > 15% | 10-15% | 5-10% | < 5% |
| **夏普比率** | > 1.5 | 1.0-1.5 | 0.5-1.0 | < 0.5 |
| **最大回撤** | < 5% | 5-10% | 10-20% | > 20% |
| **胜率** | > 60% | 50-60% | 40-50% | < 40% |

#### 风险控制建议

1. **设置止损**: 建议最大回撤不超过5%
2. **分散投资**: 不要将所有资金投入单一策略
3. **定期复盘**: 至少每月评估一次策略表现
4. **参数更新**: 根据市场环境调整参数

---

## 5️⃣ Twitter舆情分析

### 5.1 推文收集

#### 基本用法

```bash
# 收集最近 24 小时的推文
python manage.py collect_twitter_list 1988517245048455250 --hours 24

# 收集最近 1 小时的推文
python manage.py collect_twitter_list 1988517245048455250 --hours 1
```

#### 高级参数

```bash
# 指定时间范围
python manage.py collect_twitter_list 1988517245048455250 \
  --start-time "2025-01-01T00:00:00+00:00" \
  --end-time "2025-01-02T00:00:00+00:00"

# 调整批次大小（默认 500）
python manage.py collect_twitter_list 1988517245048455250 \
  --hours 24 --batch-size 1000

# 试运行模式（不保存数据库）
python manage.py collect_twitter_list 1988517245048455250 \
  --hours 1 --dry-run
```

#### 常用 List ID

```
1988517245048455250  # 可用于测试（已有数据）
```

#### 输出示例

```
============================================================
Twitter List 推文收集
============================================================
List ID: 1988517245048455250
时间范围: 2025-11-12 13:10:32 ~ 2025-11-13 13:10:32
处理批次数: 1
总获取推文数: 19
新保存推文数: 19
重复推文数: 0

============================================================
✓ 成功保存 19 条推文！
```

---

### 3.2 AI 分析

#### 基本用法

```bash
# 分析最近 24 小时的推文
python manage.py analyze_twitter_list 1988517245048455250 --hours 24

# 分析最近 1 小时的推文
python manage.py analyze_twitter_list 1988517245048455250 --hours 1
```

#### 成本控制

```bash
# 设置最大成本（默认 $10）
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 --max-cost 5.0

# 试运行模式（仅估算成本，不执行分析）
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 --dry-run
```

#### 自定义 Prompt

```bash
# 使用自定义分析模板
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 --prompt /path/to/custom_prompt.txt

# 使用自定义模板并限制成本
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 \
  --prompt /path/to/custom_prompt.txt \
  --max-cost 2.0
```

#### 分析模式

```bash
# 强制使用批次模式（≥100 条推文）
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 \
  --batch-mode \
  --batch-size 50

# 强制使用一次性模式（<100 条推文）
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 --batch-size 20
```

#### 输出格式

```bash
# 文本格式输出（默认，彩色摘要）
python manage.py analyze_twitter_list 1988517245048455250 --hours 1

# JSON 格式输出（适合 API 集成）
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 1 --format json
```

#### 文本格式输出示例

```
============================================================
Twitter List AI 分析
============================================================
任务 ID: 580cdccf-ba45-4e60-a318-60e5f3534f30
推文数量: 8
实际成本: $0.0004
处理时长: 29.47 秒

【市场情绪】
  多头: 2 条 (25.0%)
  空头: 0 条 (0.0%)
  中性: 6 条 (75.0%)

【关键话题】
  1. Binance (4 次) ➖
  2. KaitoAI (4 次) ➖
  3. LorenzoProtocol (1 次) 📈
  4. MeteoraAG (1 次) 📈
  5. AnichessGame (1 次) ➖

【重要推文】
  1. @binance (互动: 1675)
     Wake me up when it's Friday! https://t.co/tYlOUm51GT...
     原因: 高互动

【市场总结】
  当前市场主要关注Binance的新币上市和自动化交易工具，
  以及KaitoAI相关的项目公告和互动活动。
============================================================
```

---

## 4️⃣ 完整工作流示例

### 场景 1: 快速测试（5 分钟）

```bash
# 1. 收集最近 1 小时的推文
python manage.py collect_twitter_list 1988517245048455250 --hours 1

# 2. 试运行分析（查看成本估算）
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 1 --dry-run

# 3. 执行分析
python manage.py analyze_twitter_list 1988517245048455250 --hours 1

# 4. 查看结果
python verify_data.py
```

### 场景 2: 日常使用（每天分析）

```bash
# 1. 收集过去 24 小时的推文
python manage.py collect_twitter_list <list_id> --hours 24

# 2. 分析过去 24 小时的推文
python manage.py analyze_twitter_list <list_id> --hours 24
```

### 场景 3: 生产使用（定时任务）

创建 cron 任务（每天凌晨 2 点执行）:

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天 2:00 AM 执行）
0 2 * * * cd /path/to/your/project && python manage.py collect_twitter_list <list_id> --hours 24 >> /var/log/twitter_collect.log 2>&1
5 2 * * * cd /path/to/your/project && python manage.py analyze_twitter_list <list_id> --hours 24 --max-cost 10 >> /var/log/twitter_analyze.log 2>&1
```

---

## 5️⃣ Django Admin 使用

### 5.1 启动 Admin

```bash
# 开发服务器已启动
python manage.py runserver 0.0.0.0:8000

# 访问 Admin 界面
# http://localhost:8000/admin/

# 登录凭据
# 用户名: admin
# 密码: admin123
```

### 5.2 模型管理

#### Twitter Lists
- 查看所有监控的 Twitter List
- 添加新的 List（输入 list_id）
- 查看推文数量统计
- 设置状态（active/inactive/archived）
- 管理标签分类

#### Tweets（只读）
- 查看收集的推文
- 按 List、时间筛选
- 查看互动分数（彩色）
  - 红色: ≥1000（超高互动）
  - 橙色: ≥100（高互动）
  - 绿色: ≥10（中等互动）
  - 灰色: <10（低互动）
- 点击用户名跳转到 Twitter

#### Analysis Results（只读）
- 查看所有分析任务
- 按状态筛选
  - 灰色: pending（待处理）
  - 蓝色: running（运行中）
  - 绿色: completed（已完成）
  - 红色: failed（失败）
  - 橙色: cancelled（已取消）
- 查看成本（彩色）
  - 绿色: ≤$1（低成本）
  - 橙色: $1-$5（中等成本）
  - 红色: >$5（高成本）
- 查看分析结果详情
  - 市场情绪统计
  - 关键话题列表
  - 市场总结文本
  - 完整 JSON（可折叠展开）

#### Tags
- 管理标签分类

### 5.3 Admin 界面截图说明

**列表页面**:
- ✅ 绿色徽章：已完成
- 🔵 蓝色徽章：运行中
- ❌ 红色徽章：失败
- 🟡 橙色徽章：已取消/成本告警

**成本显示**:
- 🟢 绿色成本：低成本 (<$1)
- 🟠 橙色成本：中等成本 ($1-$5)
- 🔴 红色成本：高成本 (>$5)

---

## 6️⃣ 通知推送配置（可选）

### 6.1 配置通知服务

在 `.env` 文件中添加：

```bash
# 通知推送配置（可选）
ALERT_PUSH_TOKEN=你的推送token
ALERT_PUSH_CHANNEL=twitter_analysis
COST_ALERT_THRESHOLD=5.00
```

### 6.2 通知类型

系统会在以下情况自动发送通知：

1. **分析完成通知**: 包含情绪统计、关键话题、成本信息
2. **分析失败通知**: 包含错误详情和任务 ID
3. **成本告警**: 成本超过阈值时（默认 $5）

### 6.3 测试通知

```bash
# 执行分析时会自动发送通知（如果配置了 ALERT_PUSH_TOKEN）
python manage.py analyze_twitter_list 1988517245048455250 --hours 1
```

---

## 7️⃣ 自定义分析模板

### 7.1 创建自定义模板

```bash
cat > /tmp/custom_analysis.txt << 'EOF'
你是一位专业的区块链分析师。请分析以下推文，重点关注：

1. 新项目发布（IDO, IEO, 空投等）
2. 技术突破和创新
3. 重要合作伙伴关系
4. 监管政策变化

请按照以下 JSON 格式输出：
{
  "market_mood": "整体市场情绪（看涨/看跌/中性）",
  "breaking_news": [
    {"project": "项目名", "type": "类型", "impact": "影响力评估"}
  ],
  "technical_analysis": "技术面分析",
  "regulatory_updates": "监管更新",
  "sentiment": {
    "bullish": 数量,
    "bearish": 数量,
    "neutral": 数量
  }
}

请开始分析以下推文：
EOF
```

### 7.2 使用自定义模板

```bash
# 使用自定义模板分析
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 \
  --prompt /tmp/custom_analysis.txt \
  --max-cost 5.0 \
  --format json
```

---

## 8️⃣ 故障排查

### 8.1 常见问题

#### Q: 推文收集失败

```bash
# 检查 API 配置
python test_api_config.py

# 查看详细日志
python manage.py collect_twitter_list <list_id> --hours 1 -v 3
```

#### Q: AI 分析失败

```bash
# 检查是否有推文数据
python verify_data.py

# 试运行查看成本估算
python manage.py analyze_twitter_list <list_id> --hours 24 --dry-run

# 检查 DeepSeek API 配置
python test_api_config.py
```

#### Q: 成本过高

```bash
# 使用 dry-run 查看成本估算
python manage.py analyze_twitter_list <list_id> --dry-run

# 减少时间范围
python manage.py analyze_twitter_list <list_id> --hours 6 --max-cost 2.0

# 使用批次模式（更高效）
python manage.py analyze_twitter_list <list_id> \
  --hours 24 --batch-mode --batch-size 50
```

#### Q: 通知未收到

```bash
# 检查是否配置了 ALERT_PUSH_TOKEN
echo $ALERT_PUSH_TOKEN

# 检查阈值设置
python manage.py shell -c "
from django.conf import settings
print(getattr(settings, 'COST_ALERT_THRESHOLD', 5.00))
"
```

### 8.2 日志查看

```bash
# 查看 Django 服务器日志
tail -f /tmp/django.log

# 查看实时日志（如果配置了日志文件）
tail -f /var/log/django.log

# 搜索错误
grep -i error /var/log/django.log | tail -20
```

---

## 9️⃣ 环境变量配置

### .env 文件示例

```bash
# Twitter API 配置
TWITTER_API_KEY=jv58xo5oyj6h4bvtw02gsqav40brrd
TWITTER_API_BASE_URL=https://api.apidance.pro

# DeepSeek AI 配置
DEEPSEEK_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
DEEPSEEK_BASE_URL=https://deepseek.wanjiedata.com/v1
DEEPSEEK_MODEL=deepseek-v3

# 可选：通知推送配置
ALERT_PUSH_TOKEN=你的推送token
ALERT_PUSH_CHANNEL=twitter_analysis
COST_ALERT_THRESHOLD=5.00

# 可选：其他配置
MAX_COST_PER_ANALYSIS=10.00
```

---

## 🔟 更多资源

- **完整设计文档**: `docs/twitter-integration-solution.md`
- **任务计划**: `specs/001-twitter-app-integration/tasks.md`
- **快速开始**: `specs/001-twitter-app-integration/quickstart.md`
- **API 契约**: `specs/001-twitter-app-integration/contracts/management-commands.md`

---

## ✨ 完整测试示例

```bash
# 1. 检查配置
python test_api_config.py

# 2. 运行测试
python manage.py test twitter.tests -v 2

# 3. 查看数据统计
python verify_data.py

# 4. 收集推文
python manage.py collect_twitter_list 1988517245048455250 --hours 24

# 5. 试运行分析
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 --dry-run

# 6. 执行分析
python manage.py analyze_twitter_list 1988517245048455250 --hours 24

# 7. 查看结果
python verify_data.py

# 8. 启动 Admin 服务器
python manage.py runserver 0.0.0.0:8000

# 9. 访问 Admin
# http://localhost:8000/admin/
# 用户名: admin
# 密码: admin123
```

---

## 📊 系统架构

```
twitter/
├── sdk/                          # 外部 API SDK
│   ├── rate_limiter.py          # 限流器
│   ├── retry_manager.py         # 重试管理
│   ├── twitter_sdk.py           # Twitter API
│   └── deepseek_sdk.py          # DeepSeek AI
│
├── models/                       # 数据模型
│   ├── soft_delete.py           # 软删除基类
│   ├── tag.py                   # 标签模型
│   ├── twitter_list.py          # List 模型
│   ├── tweet.py                 # Tweet 模型
│   └── twitter_analysis_result.py  # 分析结果
│
├── services/                     # 业务逻辑
│   ├── twitter_list_service.py  # 推文收集
│   ├── ai_analysis_service.py   # AI 分析
│   ├── orchestrator.py          # 流程编排
│   └── notifier.py              # 通知服务
│
├── management/commands/          # 管理命令
│   ├── collect_twitter_list.py  # 推文收集
│   └── analyze_twitter_list.py  # AI 分析
│
├── templates/prompts/            # AI Prompt
│   └── crypto_analysis.txt      # 加密货币分析
│
├── tests/                        # 单元测试
│   └── test_models.py           # 模型测试
│
├── admin.py                      # Admin 配置
└── migrations/                   # 数据库迁移
```

---

## 💡 最佳实践

1. **成本控制**:
   - 始终使用 `--dry-run` 先查看成本估算
   - 设置合理的 `--max-cost` 上限
   - 对于大量数据，使用批次模式（`--batch-mode`）

2. **性能优化**:
   - 使用较小的批次大小（50-100）减少内存占用
   - 定期清理旧数据（软删除的记录）
   - 使用索引优化查询

3. **生产部署**:
   - 配置日志记录
   - 设置定时任务
   - 监控成本和使用情况
   - 配置告警通知

4. **数据管理**:
   - 定期备份数据库
   - 导出重要分析结果
   - 使用软删除保留历史记录

---

**系统状态**: ✅ 所有功能正常，可投入使用！

---

---

## 🔟 完整工作流示例

### 场景1: 策略研究与回测 (30分钟)

```bash
# 1. 获取历史数据
python manage.py fetch_klines --symbol ETHUSDT --interval 4h --days 180 --validate

# 2. 运行Grid V2回测
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v2 \
  --days 180

# 3. 参数优化
python manage.py optimize_params \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v2 \
  --grid-step-pcts 0.5,1.0,1.5,2.0 \
  --grid-levels 5,10,15,20

# 4. 生成报告
python manage.py generate_comprehensive_report \
  --strategy grid_v2 \
  --days 180
```

### 场景2: 实时策略监控 (每天5分钟)

```bash
# 1. 更新数据
python manage.py update_klines --symbol ETHUSDT --interval 4h --limit 100

# 2. 运行回测
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v3 \
  --days 30

# 3. 查看结果
python manage.py shell
>>> from backtest.models import BacktestResult
>>> result = BacktestResult.objects.latest('created_at')
>>> print(f"收益率: {result.total_return:.2%}")
```

### 场景3: Twitter舆情分析 (10分钟)

```bash
# 1. 收集推文
python manage.py collect_twitter_list 1988517245048455250 --hours 24

# 2. 试运行分析
python manage.py analyze_twitter_list 1988517245048455250 \
  --hours 24 --dry-run

# 3. 执行分析
python manage.py analyze_twitter_list 1988517245048455250 --hours 24

# 4. 查看结果
python verify_data.py
```

---

## 📋 快速参考

### 网格交易命令

```bash
# Grid V1回测
python manage.py run_backtest \
  --symbol ETHUSDT --interval 4h --strategy grid --days 180

# Grid V2回测
python manage.py run_backtest \
  --symbol ETHUSDT --interval 4h --strategy grid_v2 \
  --days 180 --grid-step-pct 0.015 --grid-levels 10

# Grid V3回测
python manage.py run_backtest \
  --symbol ETHUSDT --interval 4h --strategy grid_v3 \
  --days 90 --order-validity-days 7

# 参数优化
python manage.py optimize_params \
  --symbol ETHUSDT --interval 4h --strategy grid_v2

# 策略对比
python manage.py compare_results --strategy1 grid_v2 --strategy2 grid_v3
```

### 回测系统命令

```bash
# 获取历史数据
python manage.py fetch_klines --symbol ETHUSDT --interval 4h --days 180

# 增量更新
python manage.py update_klines --symbol ETHUSDT --interval 4h --limit 100

# 数据验证
python manage.py validate_data --symbol ETHUSDT --interval 4h

# 生成图表
python manage.py visualize_results --backtest-id 123

# 参数热力图
python manage.py plot_heatmap --backtest-ids 123,124,125,126
```

### Twitter分析命令

```bash
# 收集推文
python manage.py collect_twitter_list <list_id> --hours 24

# 分析推文
python manage.py analyze_twitter_list <list_id> --hours 24

# 试运行分析（估算成本）
python manage.py analyze_twitter_list <list_id> --hours 24 --dry-run

# JSON 输出
python manage.py analyze_twitter_list <list_id> --hours 24 --format json

# 自定义成本上限
python manage.py analyze_twitter_list <list_id> --hours 24 --max-cost 5.0

# 自定义 Prompt
python manage.py analyze_twitter_list <list_id> \
  --hours 24 --prompt /path/to/custom.txt
```

### Web界面命令

```bash
# 启动Web回测界面
./start_web_backtest.sh
# 访问 http://127.0.0.1:8001/backtest/

# 启动Django Admin
python manage.py runserver 0.0.0.0:8000
# 访问 http://localhost:8000/admin/
```

### 工具脚本

```bash
# 验证配置
python test_api_config.py

# 查看数据统计
python verify_data.py

# 创建超级用户
python create_admin.py

# 运行测试
python manage.py test

# 查看日志
tail -f /tmp/django.log
```

---

**祝您使用愉快！** 🎉
