"""
回测Web视图
Backtest Web Views
"""
import json
import logging
from datetime import timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from backtest.models import KLine, BacktestResult, BacktestSnapshot
from backtest.services.data_fetcher import DataFetcher
from backtest.services.backtest_engine import BacktestEngine
from backtest.services.grid_strategy_vbt import GridStrategyVBT
from backtest.services.buy_hold_strategy import BuyHoldStrategy

logger = logging.getLogger(__name__)


def index(request):
    """回测首页"""
    return render(request, 'backtest/index.html')


def player_view(request):
    """回测播放器页面"""
    return render(request, 'backtest/player.html')


@csrf_exempt
def run_backtest_view(request):
    """运行回测并返回结果"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    try:
        # 获取参数
        data = json.loads(request.body)
        symbol = data.get('symbol', 'ETHUSDT').upper()
        interval = data.get('interval', '4h')
        days = int(data.get('days', 180))
        initial_cash = float(data.get('initial_cash', 10000))
        strategy_type = data.get('strategy', 'grid')

        # 网格策略参数
        grid_step = float(data.get('grid_step', 1.5)) / 100
        grid_levels = int(data.get('grid_levels', 10))
        stop_loss = data.get('stop_loss')
        if stop_loss:
            stop_loss = float(stop_loss) / 100

        # 1. 确保数据可用
        data_status = _ensure_data(symbol, interval, days)
        if not data_status['success']:
            return JsonResponse(data_status, status=400)

        # 2. 计算时间范围
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # 3. 创建回测引擎
        engine = BacktestEngine(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash
        )

        # 4. 运行策略
        if strategy_type == 'buy_hold':
            strategy = BuyHoldStrategy(engine)
            entries, exits = strategy.generate_signals()
            result = strategy.run()
            grid_info = None
        else:
            strategy = GridStrategyVBT(
                engine=engine,
                grid_step_pct=grid_step,
                grid_levels=grid_levels,
                stop_loss_pct=stop_loss
            )
            entries, exits = strategy.generate_signals()
            result = strategy.run()

            # 获取网格信息
            base_price = engine.df['Close'].iloc[0]
            grid_levels_list = []
            for i in range(1, grid_levels + 1):
                buy_price = base_price * (1 - grid_step * i)
                sell_price = base_price * (1 + grid_step * i)
                grid_levels_list.append({
                    'buy': float(buy_price),
                    'sell': float(sell_price)
                })

            grid_info = {
                'base_price': float(base_price),
                'levels': grid_levels_list,
                'stop_loss_price': float(base_price * (1 - stop_loss)) if stop_loss else None
            }

        # 5. 准备返回数据
        response_data = _prepare_response_data(
            result, engine, entries, exits, grid_info
        )

        return JsonResponse(response_data)

    except Exception as e:
        logger.exception("回测执行失败")
        return JsonResponse({'error': str(e)}, status=500)


def _ensure_data(symbol: str, interval: str, days: int) -> dict:
    """确保数据可用"""
    interval_map = {'1h': 24, '4h': 6, '1d': 1}
    bars_per_day = interval_map.get(interval, 6)
    needed_bars = days * bars_per_day

    existing_count = KLine.objects.filter(
        symbol=symbol,
        interval=interval
    ).count()

    if existing_count >= needed_bars:
        return {
            'success': True,
            'message': f'数据充足: {existing_count} 根K线',
            'existing': existing_count,
            'needed': needed_bars
        }

    # 数据不足，尝试获取
    try:
        fetcher = DataFetcher(symbol, interval)
        saved_count = fetcher.fetch_historical_data(days=days)

        return {
            'success': True,
            'message': f'成功获取 {saved_count} 根新K线',
            'existing': existing_count,
            'needed': needed_bars,
            'fetched': saved_count
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'数据获取失败: {str(e)}'
        }


def _prepare_response_data(result, engine, entries, exits, grid_info):
    """准备响应数据"""
    df = engine.df

    # 价格数据
    price_data = []
    for idx, row in df.iterrows():
        price_data.append({
            'time': idx.isoformat(),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': float(row['Volume'])
        })

    # 买卖信号
    signals = []
    for i in range(len(df)):
        if entries.iloc[i]:
            signals.append({
                'time': df.index[i].isoformat(),
                'type': 'buy',
                'price': float(df['Close'].iloc[i])
            })
        if exits.iloc[i]:
            signals.append({
                'time': df.index[i].isoformat(),
                'type': 'sell',
                'price': float(df['Close'].iloc[i])
            })

    # 持仓状态
    position_data = []
    current_position = 0
    for i in range(len(df)):
        if entries.iloc[i]:
            current_position = 1
        elif exits.iloc[i]:
            current_position = 0
        position_data.append({
            'time': df.index[i].isoformat(),
            'position': current_position
        })

    # 权益曲线
    equity_data = []
    if result.equity_curve:
        for time_str, value in result.equity_curve.items():
            equity_data.append({
                'time': time_str,
                'value': float(value)
            })

    # 交易详情
    trades = []
    if result.trades_detail:
        for trade in result.trades_detail:
            trades.append({
                'entry_time': str(trade.get('Entry Timestamp', '')),
                'exit_time': str(trade.get('Exit Timestamp', '')),
                'entry_price': float(trade.get('Entry Price', 0)),
                'exit_price': float(trade.get('Exit Price', 0)),
                'pnl': float(trade.get('PnL', 0)),
                'return': float(trade.get('Return', 0)) * 100,
                'duration': str(trade.get('Duration', ''))
            })

    return {
        'success': True,
        'result': {
            'id': result.id,
            'name': result.name,
            'symbol': result.symbol,
            'interval': result.interval,
            'total_return': float(result.total_return) * 100,
            'sharpe_ratio': float(result.sharpe_ratio) if result.sharpe_ratio else None,
            'max_drawdown': float(result.max_drawdown),
            'win_rate': float(result.win_rate),
            'total_trades': result.total_trades,
            'profitable_trades': result.profitable_trades,
            'losing_trades': result.losing_trades,
            'initial_cash': float(result.initial_cash),
            'final_value': float(result.final_value)
        },
        'data': {
            'prices': price_data,
            'signals': signals,
            'positions': position_data,
            'equity': equity_data,
            'trades': trades
        },
        'grid_info': grid_info
    }


@require_http_methods(["GET"])
def get_symbols(request):
    """获取可用交易对列表"""
    symbols = KLine.objects.values_list('symbol', flat=True).distinct()
    return JsonResponse({'symbols': list(symbols)})


@require_http_methods(["GET"])
def get_intervals(request):
    """获取可用时间周期列表"""
    intervals = ['1h', '4h', '1d']
    return JsonResponse({'intervals': intervals})


@require_http_methods(["GET"])
def get_backtest_detail(request, backtest_id):
    """获取回测详细信息"""
    try:
        backtest = BacktestResult.objects.get(id=backtest_id)

        # 基础指标
        backtest_data = {
            'id': backtest.id,
            'name': backtest.name,
            'symbol': backtest.symbol,
            'interval': backtest.interval,
            'start_date': backtest.start_date.isoformat(),
            'end_date': backtest.end_date.isoformat(),
            'strategy_params': backtest.strategy_params,
            'initial_cash': float(backtest.initial_cash),
            'final_value': float(backtest.final_value),
            'total_return': float(backtest.total_return),
            'max_drawdown': float(backtest.max_drawdown),
            'win_rate': float(backtest.win_rate),
            'total_trades': backtest.total_trades,
            'profitable_trades': backtest.profitable_trades,
            'losing_trades': backtest.losing_trades,
            'created_at': backtest.created_at.isoformat(),
            # 增强指标 - 年化指标
            'annual_return': float(backtest.annual_return) if backtest.annual_return else None,
            'annual_volatility': float(backtest.annual_volatility) if backtest.annual_volatility else None,
            # 增强指标 - 风险调整收益
            'sharpe_ratio': float(backtest.sharpe_ratio) if backtest.sharpe_ratio else None,
            'sortino_ratio': float(backtest.sortino_ratio) if backtest.sortino_ratio else None,
            'calmar_ratio': float(backtest.calmar_ratio) if backtest.calmar_ratio else None,
            # 增强指标 - 回撤分析
            'max_drawdown_duration': backtest.max_drawdown_duration,
            # 增强指标 - 交易质量
            'profit_factor': float(backtest.profit_factor) if backtest.profit_factor else None,
            'avg_win': float(backtest.avg_win) if backtest.avg_win else None,
            'avg_loss': float(backtest.avg_loss) if backtest.avg_loss else None,
        }

        return JsonResponse({
            'success': True,
            'backtest': backtest_data
        })
    except BacktestResult.DoesNotExist:
        return JsonResponse({'error': '回测记录不存在'}, status=404)
    except Exception as e:
        logger.exception("获取回测详情失败")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_backtest_snapshots(request, backtest_id):
    """获取回测所有快照（用于渲染K线图和事件）"""
    try:
        backtest = BacktestResult.objects.get(id=backtest_id)
        snapshots = BacktestSnapshot.objects.filter(
            backtest_result_id=backtest_id
        ).order_by('kline_index')

        # K线数据
        klines = []
        # 事件标记
        events_all = []

        for snapshot in snapshots:
            # K线数据点
            klines.append({
                'time': snapshot.timestamp.isoformat(),
                'price': float(snapshot.current_price),
                'cash': float(snapshot.cash_balance),
                'value': float(snapshot.total_value),
                'index': snapshot.kline_index
            })

            # 如果有事件，添加到事件列表
            if snapshot.events:
                for event in snapshot.events:
                    event_data = {
                        'time': snapshot.timestamp.isoformat(),
                        'index': snapshot.kline_index,
                        **event
                    }
                    events_all.append(event_data)

        return JsonResponse({
            'success': True,
            'backtest_id': backtest_id,
            'klines': klines,
            'events': events_all,
            'total_snapshots': len(klines)
        })

    except BacktestResult.DoesNotExist:
        return JsonResponse({'error': '回测记录不存在'}, status=404)
    except Exception as e:
        logger.exception("获取快照列表失败")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_snapshot_detail(request, backtest_id, kline_index):
    """获取特定K线快照的详细信息"""
    try:
        snapshot = BacktestSnapshot.objects.get(
            backtest_result_id=backtest_id,
            kline_index=kline_index
        )

        return JsonResponse({
            'success': True,
            'snapshot': {
                'index': snapshot.kline_index,
                'timestamp': snapshot.timestamp.isoformat(),
                'current_price': float(snapshot.current_price),
                'cash_balance': float(snapshot.cash_balance),
                'total_value': float(snapshot.total_value),
                'grid_levels': snapshot.grid_levels,
                'positions': snapshot.positions,
                'events': snapshot.events
            }
        })

    except BacktestSnapshot.DoesNotExist:
        return JsonResponse({'error': '快照不存在'}, status=404)
    except Exception as e:
        logger.exception("获取快照详情失败")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_backtest_list(request):
    """获取所有回测记录列表（支持搜索）"""
    try:
        # 获取搜索参数
        search_query = request.GET.get('search', '').strip()
        symbol_filter = request.GET.get('symbol', '').strip().upper()
        limit = int(request.GET.get('limit', 50))

        # 构建查询
        queryset = BacktestResult.objects.all()

        # 应用搜索过滤
        if search_query:
            # 支持搜索：编号(ID)、名称、交易对
            from django.db.models import Q
            queryset = queryset.filter(
                Q(id__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(symbol__icontains=search_query)
            )

        # 应用交易对过滤
        if symbol_filter:
            queryset = queryset.filter(symbol=symbol_filter)

        # 按创建时间倒序排列
        queryset = queryset.order_by('-created_at')[:limit]

        backtest_list = []
        for bt in queryset:
            # 计算回测天数
            days = (bt.end_date - bt.start_date).days if bt.start_date and bt.end_date else 0

            # 获取策略类型
            strategy_type = bt.strategy_params.get('strategy_type', 'unknown') if bt.strategy_params else 'unknown'

            backtest_list.append({
                'id': bt.id,
                'name': bt.name,
                'symbol': bt.symbol,
                'interval': bt.interval,
                'strategy_type': strategy_type,
                'start_date': bt.start_date.isoformat() if bt.start_date else None,
                'end_date': bt.end_date.isoformat() if bt.end_date else None,
                'days': days,
                'total_return': float(bt.total_return),
                'total_trades': bt.total_trades,
                'win_rate': float(bt.win_rate),
                'initial_cash': float(bt.initial_cash),
                'final_value': float(bt.final_value),
                'created_at': bt.created_at.isoformat()
            })

        return JsonResponse({
            'success': True,
            'backtests': backtest_list,
            'total': len(backtest_list),
            'filters': {
                'search': search_query,
                'symbol': symbol_filter
            }
        })

    except Exception as e:
        logger.exception("获取回测列表失败")
        return JsonResponse({'error': str(e)}, status=500)
