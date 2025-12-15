# 资金费率缓存优化方案

## 📋 问题分析

### 当前问题
1. **API错误频繁**: 获取531个标的的历史资金费率时，经常遇到403 Forbidden错误
2. **重复请求**: 每次筛选都重新请求历史资金费率，浪费API配额
3. **效率低下**: 历史资金费率是不变数据，不应该重复获取

### 核心观察
- **历史资金费率是不可变数据**: 已经发生的资金费率不会改变
- **只需获取一次**: 相同时间段的历史数据，获取一次后可永久缓存
- **新数据增量获取**: 只需要获取缓存之后的新数据

---

## 🎯 解决方案

### 方案A: 数据库缓存（推荐）✅

#### 1. 创建数据库模型

```python
class FundingRateHistory(models.Model):
    """历史资金费率缓存表"""

    symbol = models.CharField('交易对', max_length=20, db_index=True)
    funding_rate = models.DecimalField('资金费率', max_digits=20, decimal_places=8)
    funding_time = models.BigIntegerField('结算时间戳(毫秒)', db_index=True)
    funding_interval_hours = models.IntegerField('结算周期(小时)', default=8)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'grid_funding_rate_history'
        verbose_name = '历史资金费率'
        verbose_name_plural = verbose_name
        unique_together = [['symbol', 'funding_time']]  # 防止重复
        indexes = [
            models.Index(fields=['symbol', 'funding_time']),
        ]
```

#### 2. 缓存管理器

```python
class FundingRateCache:
    """资金费率缓存管理器"""

    @staticmethod
    def get_cached_history(
        symbol: str,
        start_time: int,
        end_time: int = None
    ) -> List[Dict]:
        """
        从数据库获取缓存的历史资金费率

        Args:
            symbol: 交易对
            start_time: 开始时间戳(毫秒)
            end_time: 结束时间戳(毫秒)，None表示当前时间

        Returns:
            历史资金费率列表
        """
        from grid_trading.django_models import FundingRateHistory
        from datetime import datetime

        if end_time is None:
            end_time = int(datetime.now().timestamp() * 1000)

        records = FundingRateHistory.objects.filter(
            symbol=symbol,
            funding_time__gte=start_time,
            funding_time__lte=end_time
        ).order_by('funding_time')

        return [{
            'fundingRate': record.funding_rate,
            'fundingTime': record.funding_time,
        } for record in records]

    @staticmethod
    def save_funding_history(
        symbol: str,
        history: List[Dict],
        funding_interval_hours: int = 8
    ) -> int:
        """
        保存历史资金费率到数据库

        Args:
            symbol: 交易对
            history: 资金费率列表
            funding_interval_hours: 结算周期

        Returns:
            新增记录数
        """
        from grid_trading.django_models import FundingRateHistory

        records_to_create = []
        for item in history:
            records_to_create.append(
                FundingRateHistory(
                    symbol=symbol,
                    funding_rate=item['fundingRate'],
                    funding_time=item['fundingTime'],
                    funding_interval_hours=funding_interval_hours
                )
            )

        # 使用ignore_conflicts避免重复插入错误
        created = FundingRateHistory.objects.bulk_create(
            records_to_create,
            ignore_conflicts=True
        )

        return len(created)

    @staticmethod
    def get_funding_interval(symbol: str) -> int:
        """
        从缓存中获取资金费率结算周期

        Args:
            symbol: 交易对

        Returns:
            结算周期(小时)，默认8
        """
        from grid_trading.django_models import FundingRateHistory

        record = FundingRateHistory.objects.filter(
            symbol=symbol
        ).first()

        return record.funding_interval_hours if record else 8

    @staticmethod
    def get_latest_funding_time(symbol: str) -> Optional[int]:
        """
        获取缓存中最新的资金费率时间戳

        Args:
            symbol: 交易对

        Returns:
            最新时间戳(毫秒)，无缓存返回None
        """
        from grid_trading.django_models import FundingRateHistory

        record = FundingRateHistory.objects.filter(
            symbol=symbol
        ).order_by('-funding_time').first()

        return record.funding_time if record else None
```

#### 3. 修改 BinanceFuturesClient

```python
def fetch_funding_rate_history(
    self,
    symbols: List[str],
    start_time: int = None,
    limit: int = 100,
    use_cache: bool = True,  # 新增参数
    force_refresh: bool = False,  # 新增参数
) -> Dict[str, Dict]:
    """
    批量获取历史资金费率（支持缓存）

    Args:
        symbols: 标的代码列表
        start_time: 开始时间戳(毫秒)，默认为48小时前
        limit: 返回记录数量
        use_cache: 是否使用缓存（默认True）
        force_refresh: 强制刷新（默认False，忽略缓存直接调用API）

    Returns:
        Dict[symbol, info]
    """
    from datetime import datetime, timedelta
    from grid_trading.services.funding_rate_cache import FundingRateCache

    if start_time is None:
        start_time = int((datetime.now() - timedelta(hours=48)).timestamp() * 1000)

    end_time = int(datetime.now().timestamp() * 1000)

    logger.info(f"获取 {len(symbols)} 个标的的历史资金费率...")
    if use_cache and not force_refresh:
        logger.info(f"  ✓ 缓存模式: 优先使用本地缓存")
    elif force_refresh:
        logger.info(f"  ⚠️ 强制刷新模式: 忽略缓存，直接调用API")
    else:
        logger.info(f"  📡 API模式: 直接调用API")

    funding_info_dict = {}
    symbols_need_fetch = []

    # ========== 第一步: 检查缓存 ==========
    if use_cache and not force_refresh:
        cache_hit = 0
        for symbol in symbols:
            # 从缓存获取数据
            cached_history = FundingRateCache.get_cached_history(
                symbol, start_time, end_time
            )

            # 检查缓存是否完整（至少需要2条记录来计算周期）
            if len(cached_history) >= 2:
                # 缓存命中
                funding_interval = FundingRateCache.get_funding_interval(symbol)
                funding_info_dict[symbol] = {
                    'history': cached_history,
                    'funding_interval_hours': funding_interval
                }
                cache_hit += 1
            else:
                # 缓存未命中或不完整，需要从API获取
                symbols_need_fetch.append(symbol)

        logger.info(f"  ✓ 缓存命中: {cache_hit}/{len(symbols)} 个标的")
        logger.info(f"  📡 需要从API获取: {len(symbols_need_fetch)} 个标的")
    else:
        symbols_need_fetch = symbols

    # ========== 第二步: 从API获取未缓存的数据 ==========
    if symbols_need_fetch:
        max_workers = 3

        def fetch_single_history(symbol: str) -> tuple:
            """获取单个标的的历史资金费率并保存到缓存"""
            try:
                params = {
                    "symbol": symbol,
                    "startTime": start_time,
                    "limit": limit,
                }
                data = self._make_request("/fapi/v1/fundingRate", params)

                if not data or len(data) < 2:
                    return (symbol, {"history": [], "funding_interval_hours": 8})

                # 解析历史数据
                history = []
                for item in data:
                    history.append({
                        "fundingRate": Decimal(str(item.get("fundingRate", "0"))),
                        "fundingTime": int(item.get("fundingTime", 0)),
                    })

                # 计算结算周期
                intervals = []
                for i in range(min(10, len(data) - 1)):
                    interval_ms = data[i + 1]['fundingTime'] - data[i]['fundingTime']
                    interval_hours = interval_ms / (1000 * 3600)
                    intervals.append(interval_hours)

                avg_interval = sum(intervals) / len(intervals) if intervals else 8.0
                funding_interval_hours = round(avg_interval)

                # 保存到缓存
                if use_cache:
                    saved_count = FundingRateCache.save_funding_history(
                        symbol, history, funding_interval_hours
                    )
                    logger.debug(f"  ✓ {symbol}: 保存 {saved_count} 条新记录到缓存")

                return (symbol, {
                    "history": history,
                    "funding_interval_hours": funding_interval_hours
                })
            except Exception as e:
                logger.warning(f"  ⚠️ {symbol} 获取失败: {str(e)}")
                return (symbol, {"history": [], "funding_interval_hours": 8})

        # 分批并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_single_history, symbol)
                      for symbol in symbols_need_fetch]

            for future in as_completed(futures):
                symbol, info = future.result()
                funding_info_dict[symbol] = info

    logger.info(f"  ✓ 完成: 获取 {len(funding_info_dict)} 个标的的历史资金费率")
    return funding_info_dict
```

#### 4. 修改 screen_contracts 命令参数

```python
parser.add_argument(
    "--no-funding-cache",
    action="store_true",
    help="禁用资金费率缓存（直接从API获取）",
)

parser.add_argument(
    "--force-refresh-funding",
    action="store_true",
    help="强制刷新资金费率（忽略缓存，重新从API获取并更新缓存）",
)
```

---

## 📊 优化效果

### 对比分析

| 指标 | 当前实现 | 缓存优化后 |
|------|---------|-----------|
| API请求次数 | 531次/次筛选 | 首次531次，后续0-5次 |
| 执行时间 | ~30-60秒 | ~1-3秒 |
| 403错误风险 | 高 | 极低 |
| API配额消耗 | 531权重/次 | 首次531，后续0-5 |

### 使用场景

```bash
# 场景1: 日常筛选（使用缓存，默认）
python manage.py screen_contracts

# 场景2: 完全不使用缓存（直接调API）
python manage.py screen_contracts --no-funding-cache

# 场景3: 强制刷新（重新获取并更新缓存）
python manage.py screen_contracts --force-refresh-funding

# 场景4: 历史回测（使用缓存）
python manage.py screen_contracts --date 2024-12-10
```

---

## 🔧 实施步骤

### 步骤1: 创建数据库模型
- [ ] 在 `django_models.py` 添加 `FundingRateHistory` 模型
- [ ] 执行 `python manage.py makemigrations`
- [ ] 执行 `python manage.py migrate`

### 步骤2: 创建缓存管理器
- [ ] 创建 `grid_trading/services/funding_rate_cache.py`
- [ ] 实现 `FundingRateCache` 类

### 步骤3: 修改API客户端
- [ ] 修改 `binance_futures_client.py` 的 `fetch_funding_rate_history` 方法
- [ ] 添加缓存逻辑和参数

### 步骤4: 更新命令参数
- [ ] 在 `screen_contracts.py` 添加缓存控制参数
- [ ] 传递参数到筛选引擎

### 步骤5: 测试验证
- [ ] 测试首次获取（全部API）
- [ ] 测试二次获取（全部缓存）
- [ ] 测试强制刷新
- [ ] 测试禁用缓存

---

## ⚠️ 注意事项

1. **数据一致性**: 缓存的历史数据永不过期（历史是不变的）
2. **增量更新**: 未来可扩展增量获取新数据功能
3. **API限流**: 仍需注意API限流，建议分批并发不超过3
4. **缓存清理**: 可定期清理超过N天的旧数据（可选）

---

## 📝 总结

**核心优势**:
- ✅ 大幅减少API请求（95%+）
- ✅ 避免403错误
- ✅ 显著提升执行速度
- ✅ 节省API配额
- ✅ 支持灵活的缓存控制

**实施优先级**: 🔥 高优先级（解决当前痛点）
