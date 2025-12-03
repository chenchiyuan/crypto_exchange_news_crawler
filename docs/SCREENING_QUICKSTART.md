# 做空网格标的筛选系统 - 快速开始

**最后更新**: 2025-12-03

## 🎯 系统简介

基于币安永续合约市场的量化筛选系统，通过多维度指标分析，自动识别最适合做空网格策略的交易标的。

### 核心能力

- ✅ **四维指标体系** - VDR/KER/OVR/CVD综合评分
- ✅ **智能缓存** - K线数据本地缓存，避免重复API调用
- ✅ **多种输出** - HTML报告 + 数据库存储 + Web动态查询
- ✅ **历史追溯** - 支持查询历史筛选结果对比

## ⚡ 快速开始

### 1. 准备工作

确保已安装依赖并配置好环境：

```bash
# 激活conda环境
conda activate crypto_env

# 检查数据库迁移
python manage.py migrate
```

### 2. 更新市场数据（首次运行必须）

```bash
# 更新所有合约基本信息和K线缓存
python manage.py update_market_data --warmup-klines --interval 4h --limit 300

# 查看缓存统计
python manage.py cache_stats
```

**输出示例**:
```
======================================================================
K线缓存统计
======================================================================
已缓存标的数: 534 个
各周期缓存情况:
  4h:  534 个标的, 总计 160,200 根K线
  1m:  534 个标的, 总计 128,160 根K线
  1d:  534 个标的, 总计 16,020 根K线
  1h:  534 个标的, 总计 16,020 根K线
  15m: 534 个标的, 总计 53,400 根K线
```

### 3. 执行筛选

#### 方式A: 简化筛选（推荐）

使用VDR/KER/OVR/CVD四维指标快速筛选：

```bash
# 基础筛选（最小成交量5000万）
python manage.py screen_simple

# 自定义最小成交量
python manage.py screen_simple --min-volume 100000000

# 自定义权重
python manage.py screen_simple --vdr-weight 0.5 --ker-weight 0.3 --ovr-weight 0.15 --cvd-weight 0.05

# 应用过滤条件
python manage.py screen_simple \
    --min-vdr 10 \
    --min-ker 0.3 \
    --min-amplitude 300 \
    --min-funding-rate 50
```

**输出示例**:
```
======================================================================
🎯 简化筛选模式 (VDR/KER/OVR/CVD)
======================================================================

初筛条件:
  最小流动性: $50,000,000 USDT
  最小上市天数: 30 天

权重配置:
  VDR权重: 40% (震荡性)
  KER权重: 30% (低效率)
  OVR权重: 20% (低拥挤)
  CVD权重: 10% (背离信号)

✓ 初筛完成: 108 个合格标的
✓ 获取到 440 个现货交易对
✓ 完成 108 个标的的指标计算

Top 3 标的:
  1. ICPUSDT         综合指数=0.8234 VDR=12.5 KER=0.245 OVR=1.12 CVD=✓
  2. ZENUSDT         综合指数=0.8156 VDR=11.8 KER=0.267 OVR=0.98 CVD=✓
  3. QNTUSDT         综合指数=0.7891 VDR=10.3 KER=0.289 OVR=1.34 CVD=✗

✅ HTML报告已生成: screening_reports/simple_screening_report.html
👉 静态HTML报告: file:///path/to/screening_reports/simple_screening_report.html
👉 动态查询页面: http://127.0.0.1:8000/screening/

💡 提示: 动态页面支持按日期查询历史筛选结果
```

#### 方式B: 完整筛选

使用三维指标体系（波动率/趋势/资金持仓）进行深度分析：

```bash
# 默认筛选Top 5
python manage.py screen_short_grid

# 自定义Top N
python manage.py screen_short_grid --top-n 10

# 自定义权重
python manage.py screen_short_grid --weights="0.3,0.3,0.2,0.2"
```

### 4. 查看结果

#### 方式1: HTML报告（静态）

打开生成的HTML报告文件，支持：
- 📊 表格排序（点击表头）
- 🔍 实时筛选（VDR/KER/振幅/资金费率）
- 📈 可视化指标对比

#### 方式2: Web动态查询

启动Django开发服务器：

```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/screening/

功能：
- 📅 按日期选择历史筛选记录
- 🔄 刷新数据
- 📊 动态排序和筛选
- 📝 查看详细指标和网格参数

### 5. 定时任务（可选）

使用cron定时执行筛选：

```bash
# 编辑crontab
crontab -e

# 添加定时任务（每天上午10点执行）
0 10 * * * cd /path/to/project && conda run -n crypto_env python manage.py screen_simple >> /tmp/screening.log 2>&1
```

## 📊 指标说明

### VDR (波动率-位移比)

**计算方式**: 累积日内波动率 / 净位移

**意义**: 衡量价格震荡的"纯净度"
- VDR > 10: 完美震荡，价格在区间内反复波动
- 5 < VDR < 10: 良好震荡
- VDR < 5: 趋势性较强

**筛选标准**: VDR越高越好

### KER (考夫曼效率比)

**计算方式**: Direction / Volatility

**意义**: 衡量价格运动的效率
- KER < 0.3: 低效率波动，适合网格
- 0.3 < KER < 0.5: 中等效率
- KER > 0.5: 高效率，趋势性强

**筛选标准**: KER越低越好

### OVR (持仓/成交比)

**计算方式**: Open Interest / 24H Volume

**意义**: 衡量杠杆拥挤度
- OVR 0.5-1.5: 健康范围
- OVR > 2.0: 高杠杆拥挤，爆仓风险大
- OVR < 0.5: 流动性可能不足

**筛选标准**: OVR在0.5-1.5之间最优

### CVD (累计成交量差)

**计算方式**: 检测买卖压力背离

**意义**: 识别熊市背离信号
- ✓ 有背离: 价格上涨但买盘减弱，做空优势
- ✗ 无背离: 市场平衡

**筛选标准**: 有背离更优

## 🎨 评分逻辑

综合指数计算：

```
Composite Index =
    VDR_weight × VDR_score +
    KER_weight × KER_score +
    OVR_weight × OVR_score +
    CVD_weight × CVD_score
```

**默认权重**:
- VDR: 40%
- KER: 30%
- OVR: 20%
- CVD: 10%

**单项得分计算**:
```python
# VDR得分
if VDR >= 10: score = 1.0
elif VDR >= 5: score = 0.5 + (VDR - 5) / 10
else: score = VDR / 10

# KER得分（反向）
if KER <= 0.1: score = 1.0
elif KER < 0.3: score = 1.0 - (KER - 0.1) * 2.5
else: score = max(0, 0.5 - (KER - 0.3) * 0.714)

# OVR得分
if 0.5 <= OVR <= 1.5: score = 1.0
elif OVR < 0.5: score = 0.5 + OVR
elif OVR < 2.0: score = 1.0 - (OVR - 1.5)
else: score = max(0, 0.5 - (OVR - 2.0) / 6)

# CVD得分
score = 1.0 if has_divergence else 0.5
```

## 📈 网格参数推荐

系统自动计算并推荐：

- **网格上限** = Current Price + 2×ATR(日线)
- **网格下限** = Current Price - 2×ATR(日线)
- **网格数量** = 根据振幅动态计算
- **止损价** = 网格上限（价格突破即退出）
- **止盈价** = 网格下限（目标获利位）

## ⚠️ 注意事项

1. **首次运行必须预热缓存**
   ```bash
   python manage.py update_market_data --warmup-klines
   ```

2. **定期更新缓存（推荐每天）**
   ```bash
   python manage.py update_market_data
   ```

3. **筛选结果仅供参考**
   - 实际交易前需人工复核
   - 结合市场环境综合判断
   - 注意风险控制

4. **API限流**
   - 币安API有请求频率限制
   - 使用缓存可显著减少API调用
   - 避免短时间内重复筛选

## 🔗 相关文档

- [完整规格文档](../specs/001-short-grid-screening/spec.md)
- [数据模型](../specs/001-short-grid-screening/data-model.md)
- [命令接口](../specs/001-short-grid-screening/contracts/command-interface.md)
- [项目架构](./PROJECT_ARCHITECTURE.md)
