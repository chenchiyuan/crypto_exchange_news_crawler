# 价格监控系统架构

**版本**: v3.0.1
**状态**: ✅ 生产就绪
**最后更新**: 2025-12-09

---

## 系统架构图

```mermaid
graph TB
    subgraph "数据层"
        A1[币安API] --> A2[BinanceFuturesClient]
        A2 --> A3[KlineCache<br/>K线缓存]

        B1[ScreeningRecord] --> B2[ScreeningResultModel<br/>波动率缓存]
    end

    subgraph "业务层"
        C1[check_price_alerts<br/>检测命令] --> C2[PriceRuleEngine<br/>规则引擎]
        C2 --> C3{规则检测}
        C3 -->|规则1| D1[7天价格新高]
        C3 -->|规则2| D2[7天价格新低]
        C3 -->|规则3| D3[触及MA20]
        C3 -->|规则4| D4[触及MA99]
        C3 -->|规则5| D5[分布区间极值]

        D1 & D2 & D3 & D4 & D5 --> E1[批量收集触发]
        E1 --> E2[波动率计算]
        E2 --> E3[防重复过滤]
        E3 --> E4[上涨/下跌分类]
    end

    subgraph "推送层"
        F1[PriceAlertNotifier] --> F2{消息格式化}
        F2 --> F3[快速判断生成]
        F3 --> F4[速览提示]
        F4 --> F5[汇成推送API]
    end

    subgraph "数据持久化"
        G1[AlertTriggerLog<br/>触发日志]
        G2[MonitoredContract<br/>监控合约]
        G3[PriceAlertRule<br/>规则配置]
        G4[SystemConfig<br/>系统配置]
    end

    A3 --> C1
    B2 --> E2
    E4 --> F1
    F5 --> G1
    G2 --> C1
    G3 --> C2
    G4 --> E3

    style C1 fill:#e1f5ff
    style C2 fill:#e1f5ff
    style F1 fill:#fff4e6
    style F5 fill:#ffe6e6
    style G1 fill:#e8f5e9
```

## 数据流转

```mermaid
sequenceDiagram
    participant Cron as Crontab定时任务
    participant Cmd as check_price_alerts
    participant Engine as PriceRuleEngine
    participant Cache as KlineCache
    participant DB as Database
    participant Notifier as PriceAlertNotifier
    participant API as 汇成推送API

    Cron->>Cmd: 每5分钟触发
    Cmd->>DB: 查询启用的监控合约

    loop 遍历每个合约
        Cmd->>Cache: 获取K线数据
        Cache-->>Cmd: 返回4h K线(42根)

        Cmd->>Engine: 检测所有规则
        Engine->>Engine: 规则1-5检测
        Engine-->>Cmd: 返回触发结果

        alt 有触发
            Cmd->>DB: 查询波动率缓存
            DB-->>Cmd: 返回15m振幅累计
            Cmd->>Cmd: 收集到batch_alerts
        end
    end

    alt batch_alerts不为空
        Cmd->>Cmd: 防重复过滤
        Cmd->>DB: 查询最近60分钟推送
        DB-->>Cmd: 返回推送记录
        Cmd->>Cmd: 过滤重复触发

        Cmd->>Notifier: 批量推送(filtered_alerts)
        Notifier->>Notifier: 上涨/下跌分类
        Notifier->>Notifier: 生成快速判断
        Notifier->>Notifier: 格式化消息
        Notifier->>API: POST推送请求
        API-->>Notifier: 返回成功/失败

        Notifier-->>Cmd: 返回推送结果
        Cmd->>DB: 记录触发日志
    end
```

## 核心组件职责

### 1. 检测命令 (`check_price_alerts.py`)

**职责**:
- 主流程编排
- 合约遍历
- K线数据获取
- 波动率计算
- 批量触发收集
- 防重复过滤

**关键代码位置**:
- 行241-246: 调用规则引擎检测
- 行250-256: 计算并添加波动率
- 行291-360: 防重复过滤逻辑
- 行373-384: 格式化数据

### 2. 规则引擎 (`rule_engine.py`)

**职责**:
- 规则检测逻辑
- K线数据分析
- MA计算
- 价格分布计算

**规则检测流程**:
```mermaid
graph LR
    A[获取K线] --> B{数据充足?}
    B -->|否| C[返回空]
    B -->|是| D[规则1-5检测]
    D --> E{规则触发?}
    E -->|是| F[返回触发详情]
    E -->|否| C
```

### 3. 推送服务 (`alert_notifier.py`)

**职责**:
- 消息格式化
- 上涨/下跌分类
- 快速判断生成
- 速览提示
- HTTP推送

**分类逻辑**:
```python
优先级1: 明确方向
  规则1(新高) + 非规则2 → 上涨
  规则2(新低) → 下跌

优先级2: 规则5极值
  当前价 >= 90分位上限 → 上涨(极高)
  当前价 <= 90分位下限 → 下跌(极低)
```

### 4. K线缓存 (`kline_cache.py`)

**职责**:
- K线数据缓存
- 减少API调用
- 提升性能

**缓存策略**:
- 内存缓存：5分钟有效期
- 降低API调用频率：从N次/分钟降低到1次/5分钟

## 数据模型关系

```mermaid
erDiagram
    MonitoredContract ||--o{ AlertTriggerLog : "触发"
    PriceAlertRule ||--o{ AlertTriggerLog : "匹配"
    ScreeningResultModel ||--o| MonitoredContract : "提供波动率"
    SystemConfig ||--|| PriceAlertRule : "配置参数"

    MonitoredContract {
        string symbol PK
        string source
        string status
        datetime created_at
    }

    PriceAlertRule {
        int rule_id PK
        string name
        boolean enabled
        json parameters
    }

    AlertTriggerLog {
        int id PK
        string symbol FK
        int rule_id FK
        decimal current_price
        boolean pushed
        datetime pushed_at
        string skip_reason
        json extra_info
        datetime triggered_at
    }

    ScreeningResultModel {
        int id PK
        string symbol FK
        float amplitude_sum_15m
        datetime created_at
    }

    SystemConfig {
        string key PK
        string value
        string description
    }
```

## 关键配置

| 配置项 | 默认值 | 说明 |
|-------|--------|------|
| `duplicate_suppress_minutes` | 60 | 防重复推送间隔（分钟） |
| `huicheng_push_token` | 6020867bc6334c609d4f348c22f90f14 | 汇成推送Token |
| `huicheng_push_channel` | price_monitor | 推送渠道名称 |

## 定时任务流程

```mermaid
graph TB
    A[Crontab] -->|每天02:00| B[screen_simple<br/>更新波动率缓存]
    A -->|每5分钟| C[check_price_alerts<br/>检测价格触发]
    A -->|每小时| D[sync_monitored_contracts<br/>同步合约列表]
    A -->|每天03:00| E[update_price_monitor_data<br/>更新K线数据]

    B --> F[ScreeningResultModel]
    C --> G[AlertTriggerLog]
    D --> H[MonitoredContract]
    E --> I[KlineData]

    F -.提供波动率.-> C
    H -.提供合约列表.-> C
    I -.提供K线数据.-> C

    style B fill:#e8f5e9
    style C fill:#e1f5ff
    style D fill:#fff4e6
    style E fill:#fce4ec
```

## 性能优化

### 1. 数据库缓存优先

```mermaid
graph LR
    A[需要波动率] --> B{数据库有缓存?}
    B -->|是,80%| C[直接返回<br/>~5ms]
    B -->|否,20%| D[实时计算]
    D --> E[获取15m K线<br/>~100ms]
    E --> F[计算振幅累计<br/>~50ms]
    F --> G[返回结果<br/>~200ms]

    style C fill:#e8f5e9
    style G fill:#fff4e6
```

### 2. 批量推送优化

| 场景 | v1.0单次推送 | v2.0批量推送 | 优化效果 |
|------|-------------|-------------|---------|
| 5合约9触发 | 9条消息 | 1条消息 | -89% |
| 10合约20触发 | 20条消息 | 1条消息 | -95% |
| 50合约100触发 | 100条消息 | 1条消息 | -99% |

### 3. K线缓存机制

- **缓存有效期**: 5分钟
- **缓存命中率**: >80%
- **API调用减少**: -95%

## 扩展性设计

### 1. 新增规则

```python
# 在rule_engine.py中添加新规则
def check_rule_6(self, symbol: str, current_price: Decimal, klines: list) -> Optional[Dict]:
    """
    规则6: 自定义规则
    """
    # 实现规则逻辑
    if condition:
        return {
            'rule_id': 6,
            'rule_name': '自定义规则',
            'current_price': current_price,
            'extra_info': {...}
        }
    return None
```

### 2. 新增推送渠道

```python
# 在alert_notifier.py中添加新推送方法
def send_to_custom_service(self, alerts: Dict) -> bool:
    """发送到自定义推送服务"""
    # 实现推送逻辑
    pass
```

### 3. 新增监控指标

```python
# 在check_price_alerts.py中添加新指标计算
def _calculate_custom_metric(self, symbol: str, cache) -> float:
    """计算自定义指标"""
    # 实现计算逻辑
    return metric_value
```

## 监控与告警

### 1. 系统健康指标

```sql
-- 推送成功率（应 ≥ 90%）
SELECT
    COUNT(*) FILTER (WHERE pushed = true) * 100.0 / COUNT(*) as success_rate
FROM alert_trigger_log
WHERE triggered_at >= NOW() - INTERVAL '24 hours';

-- 数据库命中率（应 ≥ 80%）
SELECT
    COUNT(*) FILTER (WHERE volatility > 0) * 100.0 / COUNT(*) as cache_hit_rate
FROM alert_trigger_log
WHERE triggered_at >= NOW() - INTERVAL '24 hours';

-- 触发频率（每小时）
SELECT
    symbol,
    COUNT(*) as trigger_count
FROM alert_trigger_log
WHERE triggered_at >= NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY trigger_count DESC;
```

### 2. 告警阈值

| 指标 | 告警阈值 | 处理建议 |
|-----|---------|---------|
| 推送成功率 | < 90% | 检查汇成API token和网络 |
| 数据库命中率 | < 80% | 检查screen_simple任务 |
| 单次检测耗时 | > 30秒 | 优化K线缓存或减少合约 |
| 触发失败次数 | > 10/小时 | 检查币安API连接 |

## 故障排查流程

```mermaid
graph TB
    A[发现问题] --> B{问题类型?}

    B -->|推送失败| C1[检查汇成API配置]
    C1 --> C2[检查网络连接]
    C2 --> C3[查看错误日志]

    B -->|重复推送| D1[检查防重复配置]
    D1 --> D2[查询AlertTriggerLog]
    D2 --> D3[确认时间窗口设置]

    B -->|波动率为0| E1[检查ScreeningResult]
    E1 --> E2[确认screen_simple运行]
    E2 --> E3[手动运行screen_simple]

    B -->|K线数据不足| F1[检查KlineData表]
    F1 --> F2[运行update_price_monitor_data]

    C3 --> G[问题解决]
    D3 --> G
    E3 --> G
    F2 --> G
```

---

**相关文档**:
- [功能总结](./README.md)
- [运行指南](./RUN_GUIDE.md)
- [管理员指南](./ADMIN_GUIDE.md)
