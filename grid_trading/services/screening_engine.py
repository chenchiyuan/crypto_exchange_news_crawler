"""
筛选引擎

用途: Pipeline主流程，整合数据获取、指标计算、评分排序
关联FR: 完整Pipeline流程
"""

import logging
import time
from typing import List
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

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

            # 应用初筛条件
            market_symbols = []
            for info in symbol_infos:
                if info.passes_initial_filter(self.min_volume, self.min_days):
                    market_symbols.append(info.to_market_symbol())

            logger.info(f"  ✓ 初筛完成: {len(market_symbols)} 个合格标的")

            if not market_symbols:
                logger.warning("  ⚠️ 初筛后无合格标的，直接返回")
                return []

            # ========== 步骤2: 三维指标计算 ==========
            logger.info("=" * 70)
            logger.info(f"📊 步骤2: 三维指标计算 ({len(market_symbols)}个标的)")
            logger.info("-" * 70)

            # 获取K线数据 (优先使用缓存)
            symbol_list = [s.symbol for s in market_symbols]

            if self.use_cache and self.kline_cache:
                logger.info(f"  使用K线缓存 (本地+增量更新)...")
                # 使用缓存服务（自动增量更新）
                klines_4h_dict = {}
                klines_1m_dict = {}
                klines_1d_dict = {}
                klines_1h_dict = {}

                for symbol in symbol_list:
                    klines_4h_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="4h", limit=300
                    )
                    klines_1m_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="1m", limit=240
                    )
                    klines_1d_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="1d", limit=30
                    )
                    klines_1h_dict[symbol] = self.kline_cache.get_klines(
                        symbol, interval="1h", limit=30
                    )
            else:
                logger.info(f"  直接从API获取K线 (无缓存)...")
                # 直接从API获取
                klines_4h_dict = self.client.fetch_klines(
                    symbol_list, interval="4h", limit=300
                )
                klines_1m_dict = self.client.fetch_klines(
                    symbol_list, interval="1m", limit=240
                )
                klines_1d_dict = self.client.fetch_klines(
                    symbol_list, interval="1d", limit=30
                )
                klines_1h_dict = self.client.fetch_klines(
                    symbol_list, interval="1h", limit=30
                )

            logger.info(f"  ✓ K线数据获取完成")

            # 并行计算指标
            logger.info(f"  并行计算三维指标...")
            indicators_data = []

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                for market_symbol in market_symbols:
                    symbol = market_symbol.symbol

                    # 确保K线数据存在
                    if symbol not in klines_4h_dict:
                        logger.warning(f"  ⚠️ {symbol} K线数据缺失，跳过")
                        continue

                    future = executor.submit(
                        calculate_all_indicators,
                        market_symbol,
                        klines_4h_dict[symbol],
                        klines_1m_dict.get(symbol, []),
                        klines_1d_dict.get(symbol, []),
                        klines_1h_dict.get(symbol, []),
                    )
                    futures[future] = market_symbol

                for future in as_completed(futures):
                    market_symbol = futures[future]
                    try:
                        vol, trend, micro, atr_daily, atr_hourly = future.result()
                        indicators_data.append(
                            (market_symbol, vol, trend, micro, atr_daily, atr_hourly)
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
            for i, (_, vol, _, _, _, _) in enumerate(indicators_data):
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
    ) -> List[SimpleScore]:
        """
        执行简化筛选 (只基于VDR/KER/OVR/CVD四个指标)

        Args:
            vdr_weight: VDR权重 (默认40%)
            ker_weight: KER权重 (默认30%)
            ovr_weight: OVR权重 (默认20%)
            cvd_weight: CVD权重 (默认10%)

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

            # 应用初筛条件
            market_symbols = []
            for info in symbol_infos:
                if info.passes_initial_filter(self.min_volume, self.min_days):
                    market_symbols.append(info.to_market_symbol())

            logger.info(f"  ✓ 初筛完成: {len(market_symbols)} 个合格标的")

            if not market_symbols:
                logger.warning("  ⚠️ 初筛后无合格标的，直接返回")
                return []

            # ========== 步骤2: 指标计算 ==========
            logger.info("=" * 70)
            logger.info(f"📊 步骤2: 指标计算 ({len(market_symbols)}个标的)")
            logger.info("-" * 70)

            # 获取K线数据
            symbol_list = [s.symbol for s in market_symbols]

            if self.use_cache and self.kline_cache:
                logger.info(f"  使用K线缓存...")
                klines_4h_dict = {}
                klines_1m_dict = {}
                klines_1d_dict = {}
                klines_1h_dict = {}

                for symbol in symbol_list:
                    klines_4h_dict[symbol] = self.kline_cache.get_klines(symbol, interval="4h", limit=300)
                    klines_1m_dict[symbol] = self.kline_cache.get_klines(symbol, interval="1m", limit=240)
                    klines_1d_dict[symbol] = self.kline_cache.get_klines(symbol, interval="1d", limit=30)
                    klines_1h_dict[symbol] = self.kline_cache.get_klines(symbol, interval="1h", limit=30)
            else:
                logger.info(f"  直接从API获取K线...")
                klines_4h_dict = self.client.fetch_klines(symbol_list, interval="4h", limit=300)
                klines_1m_dict = self.client.fetch_klines(symbol_list, interval="1m", limit=240)
                klines_1d_dict = self.client.fetch_klines(symbol_list, interval="1d", limit=30)
                klines_1h_dict = self.client.fetch_klines(symbol_list, interval="1h", limit=30)

            logger.info(f"  ✓ K线数据获取完成")

            # 并行计算指标
            logger.info(f"  并行计算指标...")
            indicators_data = []

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                for market_symbol in market_symbols:
                    symbol = market_symbol.symbol

                    if symbol not in klines_4h_dict:
                        logger.warning(f"  ⚠️ {symbol} K线数据缺失，跳过")
                        continue

                    future = executor.submit(
                        calculate_all_indicators,
                        market_symbol,
                        klines_4h_dict[symbol],
                        klines_1m_dict.get(symbol, []),
                        klines_1d_dict.get(symbol, []),
                        klines_1h_dict.get(symbol, []),
                    )
                    futures[future] = market_symbol

                for future in as_completed(futures):
                    market_symbol = futures[future]
                    try:
                        vol, trend, micro, atr_daily, atr_hourly = future.result()
                        indicators_data.append((market_symbol, vol, trend, micro, atr_daily, atr_hourly))
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

            results = simple_scoring.score_and_rank(indicators_data)

            logger.info(f"  ✓ 评分完成，返回 {len(results)} 个标的")
            logger.info(f"  权重配置: VDR={vdr_weight:.0%} KER={ker_weight:.0%} OVR={ovr_weight:.0%} CVD={cvd_weight:.0%}")

            return results

        except Exception as e:
            logger.error(f"简化筛选执行失败: {str(e)}", exc_info=True)
            raise

        finally:
            elapsed = time.time() - start_time
            logger.info(f"  总执行时长: {elapsed:.1f}秒")
