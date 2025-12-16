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

    @staticmethod
    def get_top_frequent_contracts(days: int = 7, limit: int = 20) -> list:
        """
        获取最近N天的高频合约列表

        统计逻辑:
        1. 获取最近N天的筛选记录
        2. 统计每个合约出现的次数
        3. 对于每个合约，收集其所有出现日期的数据
        4. 排序规则:
           - 主排序: 出现次数（降序）
           - 次排序: 15分钟平均振幅（降序）= sum(15m振幅) / 出现天数

        Args:
            days: 统计最近N天（默认7天）
            limit: 返回前N个合约（默认20个）

        Returns:
            list: 合约列表，每项包含:
            {
                'symbol': 合约代码,
                'current_price': 最新价格,
                'fdv': 最新FDV,
                'appearance_count': 出现次数,
                'avg_amplitude_15m': 15分钟平均振幅,
                'latest_drawdown': 最新高点回落,
                'latest_strategy': 最新策略建议,
                'latest_grid_range': 最新网格区间,
                'latest_price_percentile': 最新价格分位
            }
        """
        from django.db.models import Count, Sum, Avg, Max
        from datetime import timedelta
        from django.utils import timezone
        from collections import defaultdict

        try:
            # 1. 获取最近N天的日期列表
            recent_dates = DetailPageService.get_available_dates(limit=days)

            if not recent_dates:
                logger.warning(f"未找到最近{days}天的筛选记录")
                return []

            logger.info(f"统计最近{days}天高频合约: {recent_dates[0]} 至 {recent_dates[-1]}")

            # 2. 获取这些日期对应的ScreeningRecord
            screening_records = ScreeningRecord.objects.filter(
                screening_date__in=recent_dates
            )

            if not screening_records.exists():
                return []

            # 3. 统计每个合约的出现情况
            # {symbol: {'dates': [date1, date2], 'data': [result1, result2]}}
            symbol_stats = defaultdict(lambda: {'dates': [], 'results': []})

            for record in screening_records:
                results = ScreeningResultModel.objects.filter(record=record)

                for result in results:
                    symbol_stats[result.symbol]['dates'].append(record.screening_date)
                    symbol_stats[result.symbol]['results'].append(result)

            # 4. 计算每个合约的聚合数据
            aggregated_contracts = []

            for symbol, data in symbol_stats.items():
                results = data['results']
                appearance_count = len(results)

                # 获取最新的一条记录（按日期）
                latest_result = max(results, key=lambda x: x.record.screening_date)
                latest_dict = latest_result.to_dict()

                # 计算15分钟平均振幅
                total_amplitude_15m = sum(r.amplitude_sum_15m for r in results)
                avg_amplitude_15m = total_amplitude_15m / appearance_count if appearance_count > 0 else 0

                # 构建网格区间字符串
                grid_range = f"{latest_dict['grid_lower']:.4f} - {latest_dict['grid_upper']:.4f}"

                aggregated_contracts.append({
                    'symbol': symbol,
                    'current_price': float(latest_dict['price']),
                    'fdv': float(latest_dict['fdv']) if latest_dict['fdv'] else None,
                    'appearance_count': appearance_count,
                    'avg_amplitude_15m': round(avg_amplitude_15m, 4),
                    'latest_drawdown': round(latest_dict['drawdown_from_high_pct'], 2),
                    'latest_strategy': latest_dict['entry_strategy_label'] or '-',
                    'latest_grid_range': grid_range,
                    'latest_price_percentile': round(latest_dict['price_percentile_100'], 2),
                })

            # 5. 排序: 先按出现次数降序，次按平均振幅降序
            aggregated_contracts.sort(
                key=lambda x: (-x['appearance_count'], -x['avg_amplitude_15m'])
            )

            # 6. 返回前N个
            top_contracts = aggregated_contracts[:limit]

            logger.info(
                f"✓ 统计完成: 共{len(symbol_stats)}个合约，返回Top {len(top_contracts)}"
            )

            return top_contracts

        except Exception as e:
            logger.error(f"获取高频合约列表失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
