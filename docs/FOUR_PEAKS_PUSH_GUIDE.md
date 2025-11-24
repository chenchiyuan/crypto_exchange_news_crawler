# 四峰分析推送通知使用指南

## 概述

`push_four_peaks_notification.py` 是一个独立的推送通知脚本，基于成交量聚类算法识别4个关键价位（2个支撑位、2个压力位），并通过慧诚推送平台发送通知。

## 快速开始

### 基本用法

```bash
# ETH 4小时周期分析（默认）
python push_four_peaks_notification.py --symbol eth --interval 4h

# BTC 1小时周期，使用10%价格范围过滤
python push_four_peaks_notification.py --symbol btc --interval 1h --price-range 0.10

# 自定义推送渠道
python push_four_peaks_notification.py --symbol eth --interval 4h --token YOUR_TOKEN --channel YOUR_CHANNEL
```

## 命令行参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--symbol` | string | 是 | - | 交易对符号，如 eth, btc, bnb |
| `--interval` | string | 否 | 4h | 时间周期：15m, 1h, 4h, 1d |
| `--price-range` | float | 否 | 0.15 | 价格范围过滤百分比（±15%） |
| `--limit` | int | 否 | 100 | K线数量 |
| `--token` | string | 否 | (默认) | 推送服务token |
| `--channel` | string | 否 | symbal_rate | 推送渠道 |

## 推送格式

### 标题格式
```
📊 {SYMBOL} ${当前价格} - 压力 ${R1价格}({距离%}) - 支撑 ${S1价格}({距离%}) (YYYY-MM-DD HH:MM)
```

示例:
```
📊 ETH $2824.73 - 压力 $2838.85(+0.5%) - 支撑 $2793.66(-1.1%) (2025-11-24 21:41)
📊 BTC $86525.85 - 压力 $87650.69(+1.3%) - 支撑 $85747.12(-0.9%) (2025-11-24 21:42)
```

**距离百分比说明**:
- 压力位距离: 正数，表示在当前价格上方
- 支撑位距离: 负数，表示在当前价格下方
- 计算公式: `(价格 - 当前价格) / 当前价格 × 100%`

### 内容格式

推送内容包含以下部分：

1. **基本信息**
   - 交易对
   - 时间周期
   - 价格范围过滤
   - 当前价格

2. **关键价位分析**
   - 压力位（R1, R2）：包含价格、偏离百分比、来源区间、成交量
   - 支撑位（S1, S2）：包含价格、偏离百分比、来源区间、成交量

3. **区间分布详情**
   - 每个成交密集区间的价格范围
   - 成交量及占比
   - 价格宽度
   - 相对当前价格的位置

4. **简洁摘要**
   - 一行展示：当前价格 | 支撑位 | 压力位

### 示例内容

```
【基本信息】
交易对: ETH
周期: 4h
价格范围: ±15%
当前价格: $2815.43

【关键价位分析】

📈 压力位:
  R2: $2992.80 (+6.30%)
      来源: 区间2 的 low 边界
      成交量: 1,045,867 (9.8%)
  R1: $2840.77 (+0.90%)
      来源: 区间3 的 high 边界
      成交量: 819,448 (7.7%)

💰 当前价格: $2815.43

📉 支撑位:
  S1: $2792.91 (-0.80%)
      来源: 区间3 的 low 边界
      成交量: 819,448 (7.7%)
  S2: $2752.56 (-2.23%)
      来源: 区间4 的 high 边界
      成交量: 754,234 (7.1%)

【区间分布详情】
共识别出 4 个成交密集区间:

区间1: [$2992.80, $3054.74]
  成交量: 1,045,867 (9.8%)
  宽度: $61.94 (2.20%)
  位置: 上方 (偏离 6.99%)

区间2: [$2792.91, $2840.77]
  成交量: 819,448 (7.7%)
  宽度: $47.86 (1.70%)
  位置: 下方 (偏离 0.04%)

...

【摘要】
当前: $2815.43 | 支撑: $2792.91, $2752.56 | 压力: $2840.77, $2992.80
```

## 核心算法说明

### 1. 成交量聚类

使用连续性算法识别成交密集区间：

- **成交量阈值**: 平均成交量 × 1.3
- **最小桶数**: 3个
- **最大间隔**: 允许2个低量桶
- **最小宽度**: 0.3% 价格宽度
- **价格范围**: ±15%（可配置）

### 2. 关键价位提取

从4个区间的8个边界价格中，选出距离当前价格最近的4个：

1. 收集所有边界价格（每个区间的low和high）
2. 按与当前价格的距离排序
3. 选出下方最近的2个 → 支撑位（S1, S2）
4. 选出上方最近的2个 → 压力位（R1, R2）

**关键特性**: 同一个区间的两个边界可能同时被选为关键价位（当价格在区间内时）

### 3. 距离计算

- **支撑位距离**: 负数表示在当前价格下方
- **压力位距离**: 正数表示在当前价格上方
- **距离百分比**: `(价格 - 当前价格) / 当前价格 × 100%`

## 推送服务配置

### 默认配置

脚本使用项目默认的慧诚推送配置：
- Token: `6020867bc6334c609d4f348c22f90f14`
- Channel: `symbal_rate`

### 自定义配置

如需使用自己的推送服务：

```bash
python push_four_peaks_notification.py \
  --symbol eth \
  --interval 4h \
  --token YOUR_CUSTOM_TOKEN \
  --channel YOUR_CUSTOM_CHANNEL
```

## 实战案例

### 案例1: 监控ETH多周期价位

```bash
# 4小时周期 - 中期趋势
python push_four_peaks_notification.py --symbol eth --interval 4h

# 1小时周期 - 短期波动
python push_four_peaks_notification.py --symbol eth --interval 1h
```

### 案例2: BTC保守策略（缩小范围）

```bash
# 使用10%范围，只关注近距离支撑/压力
python push_four_peaks_notification.py --symbol btc --interval 4h --price-range 0.10
```

### 案例3: 定时任务集成

添加到 crontab 实现自动推送：

```bash
# 每4小时执行一次ETH分析
0 */4 * * * cd /path/to/project && python push_four_peaks_notification.py --symbol eth --interval 4h

# 每小时执行一次BTC分析
0 * * * * cd /path/to/project && python push_four_peaks_notification.py --symbol btc --interval 1h
```

## 错误处理

### 常见错误及解决方案

1. **未识别出足够的关键价位**
   ```
   ❌ 未识别出足够的关键价位，无法发送推送
   ```
   解决：
   - 增大 `--price-range` 参数（如改为 0.20）
   - 更换时间周期（如从15m改为4h）
   - 增加 `--limit` 参数（如改为200）

2. **推送失败**
   ```
   ❌ 推送失败: 找不到数据
   ```
   解决：
   - 检查 token 和 channel 是否正确
   - 访问 https://huicheng.powerby.com.cn/api/simple/alert/ 配置接收渠道

3. **网络超时**
   ```
   ❌ 推送超时
   ```
   解决：
   - 检查网络连接
   - 重试执行命令

## 相关文件

- `example_four_peaks.py` - 四峰分析核心算法（无推送）
- `demo_volume_clustering.py` - 成交量聚类算法演示
- `SUPPORT_RESISTANCE_EXTRACTION_SCHEME.md` - 关键价位提取算法文档

## 开发调试

### 查看详细日志

```bash
# 先运行 example_four_peaks.py 查看完整分析过程
python example_four_peaks.py --symbol eth --interval 4h

# 再运行推送脚本
python push_four_peaks_notification.py --symbol eth --interval 4h
```

### 测试推送服务

```python
from monitor.services.notifier import AlertPushService

push_service = AlertPushService()
success = push_service.test_push()
print(f"推送服务测试: {'成功' if success else '失败'}")
```

## 技术架构

```
push_four_peaks_notification.py
├── analyze_four_peaks()          # 从 example_four_peaks.py 导入
│   ├── fetch_klines()            # 获取K线数据
│   ├── calculate_volume_profile() # 计算成交量分布
│   ├── find_volume_clusters()    # 聚类识别区间
│   └── extract_key_levels()      # 提取关键价位
├── format_title()                # 格式化推送标题
├── format_content()              # 格式化推送内容
└── AlertPushService              # 从 monitor.services.notifier 导入
    └── POST /api/simple/alert/   # 慧诚推送API
```

## 注意事项

1. **时间周期选择**
   - 15m: 适合日内交易，但区间可能较少
   - 1h: 平衡短期和中期
   - **4h: 推荐，能识别多个独立区间**
   - 1d: 长期趋势，区间更稳定但更新慢

2. **价格范围设置**
   - 过小（如5%）: 可能识别不到足够区间
   - **适中（15%）: 推荐，覆盖大部分日常波动**
   - 过大（如30%）: 区间过多，关键价位可能失去参考意义

3. **推送频率控制**
   - 避免过于频繁推送（建议≥1小时间隔）
   - 价格波动较小时可能产生相同结果
   - 建议根据时间周期设置合理的cron任务间隔

## 许可与支持

本脚本为内部项目工具，复用了项目中的以下服务：
- `vp_squeeze` 应用的成交量分析算法
- `monitor` 应用的推送通知服务

如有问题，请查阅相关文档或联系开发团队。
