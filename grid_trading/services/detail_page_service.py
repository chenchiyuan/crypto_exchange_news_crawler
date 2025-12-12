"""
合约详情页数据聚合服务
Contract Detail Page Data Aggregation Service

提供详情页所需的所有数据聚合功能:
1. 合约基本信息
2. 技术指标和评分
3. 网格参数推荐
4. 挂单建议
"""

import logging
from typing import Dict, Optional
from datetime import datetime

from grid_trading.django_models import ScreeningResultModel, ScreeningRecord

logger = logging.getLogger("grid_trading")


class DetailPageService:
    """
    详情页数据服务

    聚合ScreeningResultModel的所有数据，为详情页提供完整的数据结构
    """

    @staticmethod
    def prepare_detail_data(
        screening_date: str,
        symbol: str
    ) -> Optional[Dict]:
        """
        准备详情页所需的所有数据

        Args:
            screening_date: 筛选日期 (YYYY-MM-DD格式字符串)
            symbol: 合约代码 (如BTCUSDT)

        Returns:
            Dict: 详情页数据，包含:
                - basic_info: 基本信息（symbol, price, rank, GSS, date）
                - volatility_indicators: 波动率指标（VDR, KER, 振幅累计）
                - trend_indicators: 趋势指标（EMA斜率, 高点回落, 价格分位）
                - market_data: 市场数据（持仓量, 交易量, Vol/OI, 资金费率）
                - money_flow: 资金流指标（大单净流入, 流强度, 大单主导度）
                - grid_params: 网格参数推荐
                - entry_suggestion: 挂单建议
            None: 如果未找到对应记录
        """
        try:
            # 1. 查询筛选记录
            screening_record = ScreeningRecord.objects.filter(
                screening_date=screening_date
            ).first()

            if not screening_record:
                logger.warning(f"未找到筛选记录: date={screening_date}")
                return None

            # 2. 查询合约结果
            result = ScreeningResultModel.objects.filter(
                record=screening_record,
                symbol=symbol
            ).first()

            if not result:
                logger.warning(f"未找到合约结果: date={screening_date}, symbol={symbol}")
                return None

            # 3. 使用to_dict()获取所有原始数据
            raw_data = result.to_dict()

            # 4. 组织数据结构
            detail_data = {
                # 基本信息
                'basic_info': {
                    'symbol': raw_data['symbol'],
                    'current_price': raw_data['price'],
                    'rank': raw_data['rank'],
                    'composite_index': raw_data['composite_index'],
                    'screening_date': screening_date,
                    'has_spot': raw_data['has_spot'],
                },

                # 波动率维度指标
                'volatility_indicators': {
                    'vdr': {
                        'value': raw_data['vdr'],
                        'score': raw_data['vdr_score'],
                        'label': 'VDR(波动率-位移比)',
                        'description': '衡量价格波动效率，值越高表示真实波动越大'
                    },
                    'ker': {
                        'value': raw_data['ker'],
                        'score': raw_data['ker_score'],
                        'label': 'KER(考夫曼效率比)',
                        'description': '趋势性指标，值越高表示趋势越强'
                    },
                    'amplitude_sum_15m': {
                        'value': raw_data['amplitude_sum_15m'],
                        'label': '15分钟振幅累计(%)',
                        'description': '最近100根15分钟K线的振幅百分比累加'
                    },
                },

                # 趋势维度指标
                'trend_indicators': {
                    'ma99_slope': {
                        'value': raw_data['ma99_slope'],
                        'label': 'EMA99斜率',
                        'description': 'EMA(99)均线斜率，正值=上升趋势，负值=下降趋势'
                    },
                    'ma20_slope': {
                        'value': raw_data['ma20_slope'],
                        'label': 'EMA20斜率',
                        'description': 'EMA(20)均线斜率，正值=上升趋势，负值=下降趋势'
                    },
                    'highest_price_300': {
                        'value': raw_data['highest_price_300'],
                        'label': '300根4h高点',
                        'description': '300根4h K线内的最高价'
                    },
                    'drawdown_from_high_pct': {
                        'value': raw_data['drawdown_from_high_pct'],
                        'label': '高点回落(%)',
                        'description': '当前价格相对300根4h高点的回落比例，正值=已回落'
                    },
                    'price_percentile_100': {
                        'value': raw_data['price_percentile_100'],
                        'label': '价格分位(100根4h)',
                        'description': '基于100根4h K线的价格分位，0%=最低点，100%=最高点'
                    },
                },

                # 市场数据维度
                'market_data': {
                    'open_interest': {
                        'value': raw_data['open_interest'],
                        'label': '持仓量(USDT)',
                        'description': '合约未平仓总量（美元价值）'
                    },
                    'volume_24h': {
                        'value': raw_data['volume_24h_calculated'],
                        'label': '24h交易量(USDT)',
                        'description': '从1440根1m K线计算的24小时交易量'
                    },
                    'vol_oi_ratio': {
                        'value': raw_data['vol_oi_ratio'],
                        'score': raw_data['ovr_score'],
                        'label': 'Vol/OI比率',
                        'description': '24h交易量/持仓量比率'
                    },
                    'annual_funding_rate': {
                        'value': raw_data['annual_funding_rate'],
                        'label': '年化资金费率(%)',
                        'description': '基于过去24小时平均资金费率年化，正值表示做空有利'
                    },
                    'fdv': {
                        'value': raw_data['fdv'],
                        'label': '完全稀释市值(USD)',
                        'description': 'Fully Diluted Valuation'
                    },
                    'oi_fdv_ratio': {
                        'value': raw_data['oi_fdv_ratio'],
                        'label': 'OI/FDV比率(%)',
                        'description': '持仓量占完全稀释市值的百分比'
                    },
                },

                # 资金流维度指标
                'money_flow': {
                    'large_net': {
                        'value': raw_data['money_flow_large_net'],
                        'label': '大单净流入(USDT)',
                        'description': '24小时大单净流入金额，正值=流入，负值=流出'
                    },
                    'strength': {
                        'value': raw_data['money_flow_strength'],
                        'label': '资金流强度',
                        'description': '主动买入占比(0-1)，>0.55=买盘强，<0.45=卖盘强'
                    },
                    'large_dominance': {
                        'value': raw_data['money_flow_large_dominance'],
                        'label': '大单主导度',
                        'description': '大单对资金流的影响程度(0-1)，越高表示机构影响越大'
                    },
                },

                # CVD背离
                'cvd_divergence': {
                    'value': raw_data['cvd'],
                    'score': raw_data['cvd_score'],
                    'label': 'CVD背离',
                },

                # 网格参数推荐
                'grid_params': {
                    'upper_limit': raw_data['grid_upper'],
                    'lower_limit': raw_data['grid_lower'],
                    'grid_count': raw_data['grid_count'],
                    'grid_step': raw_data['grid_step'],
                    'take_profit_price': raw_data['take_profit_price'],
                    'stop_loss_price': raw_data['stop_loss_price'],
                    'take_profit_pct': raw_data['take_profit_pct'],
                    'stop_loss_pct': raw_data['stop_loss_pct'],
                },

                # 挂单建议
                'entry_suggestion': {
                    'rsi_15m': raw_data['rsi_15m'],
                    'recommended_price': raw_data['recommended_entry_price'],
                    'trigger_prob_24h': raw_data['entry_trigger_prob_24h'],
                    'trigger_prob_72h': raw_data['entry_trigger_prob_72h'],
                    'strategy_label': raw_data['entry_strategy_label'],
                    'rebound_pct': raw_data['entry_rebound_pct'],
                    'avg_trigger_time': raw_data['entry_avg_trigger_time'],
                    'expected_return_24h': raw_data['entry_expected_return_24h'],
                    'candidates': raw_data['entry_candidates'],
                },
            }

            logger.info(f"✓ 详情页数据准备完成: {symbol} @ {screening_date}")
            return detail_data

        except Exception as e:
            logger.error(f"准备详情页数据失败: {screening_date}/{symbol} - {e}", exc_info=True)
            return None

    @staticmethod
    def get_available_dates(limit: int = 30) -> list:
        """
        获取最近的可用筛选日期列表

        Args:
            limit: 返回的日期数量

        Returns:
            list: 日期列表，格式为['YYYY-MM-DD', ...]，按时间倒序
        """
        try:
            dates = ScreeningRecord.objects.values_list(
                'screening_date', flat=True
            ).order_by('-screening_date')[:limit]

            return [date.strftime('%Y-%m-%d') if isinstance(date, datetime) else str(date)
                    for date in dates]
        except Exception as e:
            logger.error(f"获取可用日期列表失败: {e}")
            return []

    @staticmethod
    def get_contracts_by_date(screening_date: str) -> list:
        """
        获取指定日期的所有合约列表

        Args:
            screening_date: 筛选日期 (YYYY-MM-DD格式字符串)

        Returns:
            list: 合约列表，每项包含 {symbol, price, rank, composite_index}
        """
        try:
            screening_record = ScreeningRecord.objects.filter(
                screening_date=screening_date
            ).first()

            if not screening_record:
                return []

            results = ScreeningResultModel.objects.filter(
                record=screening_record
            ).order_by('rank')

            contracts = [
                {
                    'symbol': r.symbol,
                    'price': float(r.current_price),
                    'rank': r.rank,
                    'composite_index': round(r.composite_index, 4),
                }
                for r in results
            ]

            logger.info(f"✓ 获取到{len(contracts)}个合约: {screening_date}")
            return contracts

        except Exception as e:
            logger.error(f"获取合约列表失败: {screening_date} - {e}")
            return []
