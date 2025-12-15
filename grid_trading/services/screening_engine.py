"""
筛选引擎

用途: Pipeline主流程，整合数据获取、指标计算、评分排序
关联FR: 完整Pipeline流程
"""

import logging
import time
from typing import List, Any
from decimal import Decimal

from grid_trading.services.binance_futures_client import BinanceFuturesClient
from grid_trading.services.indicator_calculator import (
    calculate_all_indicators,
    calculate_percentile_rank,
)
from grid_trading.services.scoring_model import ScoringModel
from grid_trading.services.simple_scoring import SimpleScoring, SimpleScore
from grid_trading.services.kline_cache import KlineCache
from grid_trading.models import ScreeningResult, SymbolInfo
import numpy as np

logger = logging.getLogger("grid_trading")


class ScreeningEngine:
    """
    筛选引擎

    整合完整的Pipeline流程:
    1. 数据获取与初筛
    2. 三维指标计算
    3. 加权评分与排序
    4. 返回Top N结果
    """

    def __init__(
        self,
        top_n: int,
        weights: List[float],
        min_volume: Decimal,
        min_days: int,
        interval: str = "4h",
        use_cache: bool = True,
    ):
        """
        初始化筛选引擎 (T042)

        Args:
            top_n: 输出Top N标的
            weights: 权重列表 [w1, w2, w3, w4]
            min_volume: 最小流动性阈值 (USDT)
            min_days: 最小上市天数
            interval: K线周期 (默认4h)
            use_cache: 是否使用K线数据缓存 (默认True，推荐开启以提升性能)
        """
        self.top_n = top_n
        self.weights = weights
        self.min_volume = min_volume
        self.min_days = min_days
        self.interval = interval
        self.use_cache = use_cache

        self.client = BinanceFuturesClient()
        self.kline_cache = KlineCache(api_client=self.client) if use_cache else None
        self.scoring_model = ScoringModel(
            w1=weights[0], w2=weights[1], w3=weights[2], w4=weights[3]
        )

    def run_screening(self) -> List[ScreeningResult]:
        """
        执行筛选 (T043)

        Returns:
            List[ScreeningResult] (Top N标的)
        """
        start_time = time.time()

        try:
            # ========== 步骤1: 全市场扫描与初筛 (使用本地SymbolInfo) ==========
            logger.info("=" * 70)
            logger.info("📥 步骤1: 全市场扫描与初筛")
            logger.info("-" * 70)

            # 从本地SymbolInfo表查询(优先使用缓存)
            logger.info(f"  从本地SymbolInfo表查询...")
            symbol_infos = SymbolInfo.objects.filter(is_active=True)

            logger.info(f"  活跃合约总数: {symbol_infos.count()}")

            # 不进行初筛过滤,直接分析所有合约(过滤在展示层进行)
            market_symbols = [info.to_market_symbol() for info in symbol_infos]

            logger.info(f"  ✓ 将分析全部 {len(market_symbols)} 个合约")

            if not market_symbols:
                logger.warning("  ⚠️ 无可用合约，直接返回")
                return []

            # ========== 步骤2: 三维指标计算 ==========
            logger.info("=" * 70)
            logger.info(f"📊 步骤2: 三维指标计算 ({len(market_symbols)}个标的)")
            logger.info("-" * 70)

            # 获取K线数据 (优先使用缓存)
            symbol_list = [s.symbol for s in market_symbols]

            from django.utils import timezone
            current_time_utc8 = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"  当前时间(UTC+8): {current_time_utc8}")
            logger.info(f"  需要获取的周期: 4h(300), 1m(1440), 1d(30), 1h(30), 15m(100)")

            if self.use_cache and self.kline_cache:
                logger.info(f"  🔄 使用K线缓存 (本地+增量更新)...")
                # 使用缓存服务（自动增量更新）
                klines_4h_dict = {}
                klines_1m_dict = {}
                klines_1d_dict = {}
                klines_1h_dict = {}
                klines_15m_dict = {}

                for symbol in symbol_list:
                    klines_4h_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="4h", limit=300
                    )
                    klines_1m_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="1m", limit=1440
                    )
                    klines_1d_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="1d", limit=30
                    )
                    klines_1h_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="1h", limit=30
                    )
                    klines_15m_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="15m", limit=100
                    )
            else:
                logger.info(f"  📡 直接从API获取K线 (无缓存)...")
                # 直接从API获取
                klines_4h_dict = self.client.fetch_klines(
                    symbol_list, interval="4h", limit=300
                )
                klines_1m_dict = self.client.fetch_klines(
                    symbol_list, interval="1m", limit=1440
                )
                klines_1d_dict = self.client.fetch_klines(
                    symbol_list, interval="1d", limit=30
                )
                klines_1h_dict = self.client.fetch_klines(
                    symbol_list, interval="1h", limit=30
                )
                klines_15m_dict = self.client.fetch_klines(
                    symbol_list, interval="15m", limit=100
                )

            logger.info(f"  ✓ K线数据获取完成 - 所有周期数据已就绪")

            # 获取历史资金费率数据（含结算周期，支持缓存）
            logger.info(f"  获取历史资金费率数据（自动检测结算周期）...")
            funding_info_dict = self.client.fetch_funding_rate_history(
                symbol_list,
                limit=50,  # 获取足够多的记录来计算结算周期
                use_cache=use_funding_cache,
                force_refresh=force_refresh_funding,
            )
            logger.info(f"  ✓ 成功获取 {len(funding_info_dict)}/{len(symbol_list)} 个标的的资金费率历史")

            # 串行计算指标
            logger.info(f"  串行计算三维指标...")
            indicators_data = []

            for market_symbol in market_symbols:
                symbol = market_symbol.symbol

                # 确保K线数据存在
                if symbol not in klines_4h_dict:
                    logger.warning(f"  ⚠️ {symbol} K线数据缺失，跳过")
                    continue

                # 获取资金费率信息
                funding_info = funding_info_dict.get(symbol, {})
                funding_history = funding_info.get("history", [])
                funding_interval = funding_info.get("funding_interval_hours", 8)

                try:
                    vol, trend, micro, atr_daily, atr_hourly, rsi_15m, highest_price_300, drawdown_pct, price_percentile_100, money_flow_metrics = calculate_all_indicators(
                        market_symbol,
                        klines_4h_dict[symbol],
                        klines_1m_dict.get(symbol, []),
                        klines_1d_dict.get(symbol, []),
                        klines_1h_dict.get(symbol, []),
                        klines_15m_dict.get(symbol, []),
                        funding_history,  # 传递历史资金费率
                        funding_interval,  # 传递结算周期
                    )
                    indicators_data.append(
                        (market_symbol, vol, trend, micro, atr_daily, atr_hourly, rsi_15m, highest_price_300, drawdown_pct, price_percentile_100, money_flow_metrics)
                    )
                except Exception as e:
                    logger.warning(f"  ⚠️ {market_symbol.symbol} 指标计算失败: {str(e)}")

            logger.info(
                f"  ✓ 完成 {len(indicators_data)} 个标的的指标计算 (用时: {time.time() - start_time:.1f}秒)"
            )

            if not indicators_data:
                logger.warning("  ⚠️ 无标的完成指标计算，直接返回")
                return []

            # 计算百分位排名 (FR-010)
            all_natr = np.array([data[1].natr for data in indicators_data])
            all_ker = np.array([data[1].ker for data in indicators_data])

            natr_percentiles = calculate_percentile_rank(all_natr)
            inv_ker_percentiles = calculate_percentile_rank(1 - all_ker)

            # 填充百分位排名
            for i, (_, vol, _, _, _, _, _, _, _) in enumerate(indicators_data):
                vol.natr_percentile = float(natr_percentiles[i])
                vol.inv_ker_percentile = float(inv_ker_percentiles[i])

            # ========== 步骤3: 加权评分与排序 ==========
            results = self.scoring_model.score_and_rank(indicators_data, self.top_n)

            # ========== 步骤4: 输出推荐清单 ==========
            logger.info("=" * 70)
            logger.info("📢 步骤4: 输出推荐清单")
            logger.info("-" * 70)
            logger.info(f"  ✓ 筛选完成，返回Top {len(results)} 标的")

            return results

        except Exception as e:
            logger.error(f"筛选引擎执行失败: {str(e)}", exc_info=True)
            raise

        finally:
            elapsed = time.time() - start_time
            logger.info(f"  总执行时长: {elapsed:.1f}秒")

    def run_simple_screening(
        self,
        vdr_weight: float = 0.40,
        ker_weight: float = 0.30,
        ovr_weight: float = 0.20,
        cvd_weight: float = 0.10,
        min_vdr: float = None,
        min_ker: float = None,
        min_amplitude: float = None,
        min_funding_rate: float = None,
        max_ma99_slope: float = None,
        end_time: Any = None,
        use_funding_cache: bool = True,
        force_refresh_funding: bool = False,
    ) -> List[SimpleScore]:
        """
        执行简化筛选 (只基于VDR/KER/OVR/CVD四个指标)

        Args:
            vdr_weight: VDR权重 (默认40%)
            ker_weight: KER权重 (默认30%)
            ovr_weight: OVR权重 (默认20%)
            cvd_weight: CVD权重 (默认10%)
            use_funding_cache: 是否使用资金费率缓存 (默认True)
            force_refresh_funding: 强制刷新资金费率缓存 (默认False)

        Returns:
            List[SimpleScore] (按综合指数降序排列的所有结果)
        """
        start_time = time.time()

        try:
            # ========== 步骤1: 全市场扫描与初筛 ==========
            logger.info("=" * 70)
            logger.info("📥 步骤1: 全市场扫描与初筛 (简化模式)")
            logger.info("-" * 70)

            # 从本地SymbolInfo表查询
            logger.info(f"  从本地SymbolInfo表查询...")
            symbol_infos = SymbolInfo.objects.filter(is_active=True)
            logger.info(f"  活跃合约总数: {symbol_infos.count()}")

            # 不进行初筛过滤,直接分析所有合约(过滤在展示层进行)
            market_symbols = [info.to_market_symbol() for info in symbol_infos]

            logger.info(f"  ✓ 将分析全部 {len(market_symbols)} 个合约")

            if not market_symbols:
                logger.warning("  ⚠️ 无可用合约，直接返回")
                return []

            # 获取现货交易对列表
            logger.info("  获取现货交易对列表...")
            spot_symbols = self.client.fetch_spot_symbols()
            logger.info(f"  ✓ 获取到 {len(spot_symbols)} 个现货交易对")

            # ========== 步骤2: 指标计算 ==========
            logger.info("=" * 70)
            logger.info(f"📊 步骤2: 指标计算 ({len(market_symbols)}个标的)")
            logger.info("-" * 70)

            # 获取K线数据
            symbol_list = [s.symbol for s in market_symbols]

            from django.utils import timezone
            if end_time:
                current_time_utc8 = end_time.strftime('%Y-%m-%d %H:%M:%S')
                mode_label = "历史模式"
            else:
                current_time_utc8 = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                mode_label = "实时模式"
            logger.info(f"  {mode_label} | 当前时间(UTC+8): {current_time_utc8}")
            logger.info(f"  需要获取的周期: 4h(300), 1m(1440), 1d(30), 1h(30), 15m(672)")

            if self.use_cache and self.kline_cache:
                logger.info(f"  🔄 使用K线缓存...")
                klines_4h_dict = {}
                klines_1m_dict = {}
                klines_1d_dict = {}
                klines_1h_dict = {}
                klines_15m_dict = {}

                for symbol in symbol_list:
                    klines_4h_dict[symbol] = self.kline_cache.get_klines(symbol, interval="4h", limit=300, end_time=end_time)
                    klines_1m_dict[symbol] = self.kline_cache.get_klines(symbol, interval="1m", limit=1440, end_time=end_time)
                    klines_1d_dict[symbol] = self.kline_cache.get_klines(symbol, interval="1d", limit=30, end_time=end_time)
                    klines_1h_dict[symbol] = self.kline_cache.get_klines(symbol, interval="1h", limit=30, end_time=end_time)
                    klines_15m_dict[symbol] = self.kline_cache.get_klines(symbol, interval="15m", limit=672, end_time=end_time)  # 7天数据用于挂单概率统计
            else:
                if end_time:
                    logger.info(f"  📡 直接从API获取K线 (截止时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')})...")
                else:
                    logger.info(f"  📡 直接从API获取K线 (最新数据)...")
                klines_4h_dict = self.client.fetch_klines(symbol_list, interval="4h", limit=300, end_time=end_time)
                klines_1m_dict = self.client.fetch_klines(symbol_list, interval="1m", limit=1440, end_time=end_time)
                klines_1d_dict = self.client.fetch_klines(symbol_list, interval="1d", limit=30, end_time=end_time)
                klines_1h_dict = self.client.fetch_klines(symbol_list, interval="1h", limit=30, end_time=end_time)
                klines_15m_dict = self.client.fetch_klines(symbol_list, interval="15m", limit=672, end_time=end_time)  # 7天数据用于挂单概率统计

            logger.info(f"  ✓ K线数据获取完成 - 所有周期数据已就绪")

            # 获取历史资金费率数据（含结算周期，支持缓存）
            logger.info(f"  获取历史资金费率数据（自动检测结算周期）...")
            funding_info_dict = self.client.fetch_funding_rate_history(
                symbol_list,
                limit=50,  # 获取足够多的记录来计算结算周期
                use_cache=use_funding_cache,
                force_refresh=force_refresh_funding,
            )
            logger.info(f"  ✓ 成功获取 {len(funding_info_dict)}/{len(symbol_list)} 个标的的资金费率历史")

            # 串行计算指标
            logger.info(f"  串行计算指标...")
            indicators_data = []

            for market_symbol in market_symbols:
                symbol = market_symbol.symbol

                # 检查K线数据是否存在且非空
                if symbol not in klines_4h_dict or not klines_4h_dict.get(symbol):
                    logger.warning(f"  ⚠️ {symbol} K线数据缺失或为空，跳过")
                    continue

                # 获取资金费率信息
                funding_info = funding_info_dict.get(symbol, {})
                funding_history = funding_info.get("history", [])
                funding_interval = funding_info.get("funding_interval_hours", 8)

                try:
                    vol, trend, micro, atr_daily, atr_hourly, rsi_15m, highest_price_300, drawdown_pct, price_percentile_100, money_flow_metrics = calculate_all_indicators(
                        market_symbol,
                        klines_4h_dict[symbol],
                        klines_1m_dict.get(symbol, []),
                        klines_1d_dict.get(symbol, []),
                        klines_1h_dict.get(symbol, []),
                        klines_15m_dict.get(symbol, []),
                        funding_history,  # 传递历史资金费率
                        funding_interval,  # 传递结算周期
                    )

                    # 🔧 修复历史价格问题：使用K线最后一根的收盘价作为当时的价格
                    # 优先使用4h K线（更稳定），如果没有则使用1m K线
                    if symbol in klines_4h_dict and klines_4h_dict[symbol]:
                        historical_price = Decimal(str(klines_4h_dict[symbol][-1]["close"]))
                        market_symbol.current_price = historical_price
                    elif symbol in klines_1m_dict and klines_1m_dict[symbol]:
                        historical_price = Decimal(str(klines_1m_dict[symbol][-1]["close"]))
                        market_symbol.current_price = historical_price

                    indicators_data.append((market_symbol, vol, trend, micro, atr_daily, atr_hourly, rsi_15m, highest_price_300, drawdown_pct, price_percentile_100, money_flow_metrics))
                except Exception as e:
                    logger.warning(f"  ⚠️ {market_symbol.symbol} 指标计算失败: {str(e)}")

            logger.info(f"  ✓ 完成 {len(indicators_data)} 个标的的指标计算")

            if not indicators_data:
                logger.warning("  ⚠️ 无标的完成指标计算，直接返回")
                return []

            # ========== 步骤3: 简化评分与排序 ==========
            logger.info("=" * 70)
            logger.info("🎯 步骤3: 简化评分 (VDR/KER/OVR/CVD)")
            logger.info("-" * 70)

            simple_scoring = SimpleScoring(
                vdr_weight=vdr_weight,
                ker_weight=ker_weight,
                ovr_weight=ovr_weight,
                cvd_weight=cvd_weight,
            )

            results = simple_scoring.score_and_rank(
                indicators_data,
                klines_1m_dict=klines_1m_dict,
                klines_15m_dict=klines_15m_dict,
                spot_symbols=spot_symbols
            )

            logger.info(f"  ✓ 评分完成，返回 {len(results)} 个标的")
            logger.info(f"  权重配置: VDR={vdr_weight:.0%} KER={ker_weight:.0%} OVR={ovr_weight:.0%} CVD={cvd_weight:.0%}")

            # ========== 应用过滤条件 ==========
            if any([min_vdr, min_ker, min_amplitude, min_funding_rate, max_ma99_slope is not None]):
                logger.info("==" * 35)
                logger.info("🔍 应用过滤条件")
                logger.info("--" * 35)

                initial_count = len(results)
                filtered_results = []

                for score in results:
                    # VDR过滤
                    if min_vdr is not None and score.vdr < min_vdr:
                        continue

                    # KER过滤
                    if min_ker is not None and score.ker < min_ker:
                        continue

                    # 15m振幅过滤
                    if min_amplitude is not None and score.amplitude_sum_15m < min_amplitude:
                        continue

                    # 年化资金费率过滤
                    if min_funding_rate is not None and score.annual_funding_rate < min_funding_rate:
                        continue

                    # EMA99斜率过滤（小于等于指定值）
                    if max_ma99_slope is not None and score.ma99_slope > max_ma99_slope:
                        continue

                    filtered_results.append(score)

                results = filtered_results
                logger.info(f"  初始数量: {initial_count} 个")
                logger.info(f"  过滤后数量: {len(results)} 个")
                logger.info(f"  过滤条件:")
                if min_vdr is not None:
                    logger.info(f"    VDR >= {min_vdr}")
                if min_ker is not None:
                    logger.info(f"    KER >= {min_ker}")
                if min_amplitude is not None:
                    logger.info(f"    15m振幅 >= {min_amplitude}%")
                if min_funding_rate is not None:
                    logger.info(f"    年化资金费率 >= {min_funding_rate}%")
                if max_ma99_slope is not None:
                    logger.info(f"    EMA99斜率 <= {max_ma99_slope}")

            return results

        except Exception as e:
            logger.error(f"简化筛选执行失败: {str(e)}", exc_info=True)
            raise

        finally:
            elapsed = time.time() - start_time
            logger.info(f"  总执行时长: {elapsed:.1f}秒")
