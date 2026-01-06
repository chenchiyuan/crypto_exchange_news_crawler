"""
Volume Trap API视图集合

包含以下API端点：
1. KLineDataAPIView - K线数据查询接口
2. ChartDataAPIView - 图表数据查询接口

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F2.1, F2.2)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (5.3, 5.4)
    - Task: TASK-006-004, TASK-006-005
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from volume_trap.exceptions import DataFormatError, DateRangeInvalidError, SymbolNotFoundError
from volume_trap.models import VolumeTrapMonitor
from volume_trap.services.chart_data_formatter import ChartDataFormatter
from volume_trap.services.kline_data_service import KLineDataService

logger = logging.getLogger(__name__)


class KLineDataAPIView(APIView):
    """K线数据API视图。

    提供GET /api/volume-trap/kline/{symbol}/端点，支持查询指定交易对的K线数据。
    集成KLineDataService进行数据查询和格式化，返回标准化的OHLCV格式。

    路径参数:
        symbol (str): 交易对符号，如 'BTCUSDT'、'ETHUSDT'

    查询参数:
        interval (str, 必填): K线周期，支持 '1h'、'4h'、'1d'
        market_type (str, 必填): 市场类型，'spot' 或 'futures'
        start_time (datetime, 必填): 开始时间，ISO 8601格式
        end_time (datetime, 必填): 结束时间，ISO 8601格式
        limit (int, 可选): 返回数据条数限制，默认1000，最大5000

    响应格式:
        {
            "data": [  // K线数据数组
                {
                    "time": 1704067200.0,  // 时间戳（秒）
                    "open": 50000.0,       // 开盘价
                    "high": 50100.0,       // 最高价
                    "low": 49900.0,        // 最低价
                    "close": 50050.0,      // 收盘价
                    "volume": 1000.0,      // 成交量
                    "market_type": "futures"  // 市场类型
                },
                ...
            ],
            "total_count": 30  // 符合条件的数据总条数
        }

    错误响应:
        - 400 Bad Request: 参数验证失败（缺少必填参数、无效参数值、日期格式错误等）
        - 404 Not Found: 交易对不存在
        - 500 Internal Server Error: 服务器内部错误

    Examples:
        获取BTCUSDT合约4小时K线数据：
        GET /api/volume-trap/kline/BTCUSDT/?interval=4h&market_type=futures&start_time=2025-12-01T00:00:00&end_time=2025-12-25T23:59:59&limit=100

        获取ETHUSDT现货日K线数据：
        GET /api/volume-trap/kline/ETHUSDT/?interval=1d&market_type=spot&start_time=2025-12-01T00:00:00&end_time=2025-12-25T23:59:59

    性能特性:
        - 响应时间目标：<1秒（1000条记录以内）
        - 数据库查询优化：使用索引和分页
        - 内存使用：限制单次返回数据量

    异常处理:
        - 参数验证：自动验证必填参数和参数格式
        - 业务异常：symbol不存在、日期范围无效等
        - 系统异常：数据库连接错误等

    Related:
        - Task: TASK-006-004
        - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (5.3)
    """

    def __init__(self, **kwargs):
        """初始化K线数据API视图。

        Args:
            **kwargs: 父类初始化参数
        """
        super().__init__(**kwargs)
        self.kline_service = KLineDataService()

    def get(self, request, symbol: str, format: Optional[str] = None) -> Response:
        """处理GET请求，返回K线数据。

        Args:
            request: HTTP请求对象
            symbol (str): 交易对符号（路径参数）
            format (str, optional): 响应格式（保留参数）

        Returns:
            Response: DRF响应对象，包含K线数据或错误信息

        Raises:
            无（所有异常被捕获并转换为适当的HTTP响应）

        Examples:
            基础查询：
            >>> request = self.request
            >>> request.query_params = {
            ...     'interval': '4h',
            ...     'market_type': 'futures',
            ...     'start_time': '2025-12-01T00:00:00',
            ...     'end_time': '2025-12-25T23:59:59',
            ...     'limit': '100'
            ... }
            >>> response = self.get(request, 'BTCUSDT')
            >>> print(response.status_code)
            200
            >>> print(len(response.data['data']))
            100

        Side Effects:
            - 查询数据库：执行KLine表查询
            - 调用服务：使用KLineDataService进行数据查询
            - 记录日志：记录API调用和执行时间
        """
        try:
            # === 参数解析 ===
            interval = request.query_params.get("interval")
            market_type = request.query_params.get("market_type")
            start_time_str = request.query_params.get("start_time")
            end_time_str = request.query_params.get("end_time")
            limit_str = request.query_params.get("limit")

            # === 参数验证 ===
            self._validate_required_parameters(interval, market_type, start_time_str, end_time_str)
            self._validate_parameter_values(interval, market_type)

            # === 解析日期时间 ===
            start_time = self._parse_datetime(start_time_str, "start_time")
            end_time = self._parse_datetime(end_time_str, "end_time")

            # === 解析limit参数 ===
            limit = None
            if limit_str:
                try:
                    limit = int(limit_str)
                    if limit <= 0 or limit > 5000:
                        return self._error_response(
                            "limit参数必须在1-5000范围内", status_code=status.HTTP_400_BAD_REQUEST
                        )
                except ValueError:
                    return self._error_response(
                        "limit必须是整数", status_code=status.HTTP_400_BAD_REQUEST
                    )

            # === 调用服务查询数据 ===
            result = self.kline_service.get_kline_data(
                symbol=symbol,
                interval=interval,
                market_type=market_type,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )

            # === 记录成功日志 ===
            logger.info(
                f"K线数据API调用成功: symbol={symbol}, interval={interval}, "
                f"market_type={market_type}, count={len(result['data'])}, "
                f"total={result['total_count']}"
            )

            # === 返回成功响应 ===
            return Response(result, status=status.HTTP_200_OK)

        except SymbolNotFoundError as e:
            logger.warning(f"K线数据API - 交易对不存在: {symbol}")
            return self._error_response(
                f"交易对 '{symbol}' 不存在或已下架", status_code=status.HTTP_404_NOT_FOUND
            )

        except DateRangeInvalidError as e:
            logger.warning(f"K线数据API - 日期范围无效: {e}")
            return self._error_response(
                "结束时间必须大于开始时间", status_code=status.HTTP_400_BAD_REQUEST
            )

        except ValueError as e:
            logger.warning(f"K线数据API - 参数错误: {e}")
            return self._error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"K线数据API - 内部错误: {e}", exc_info=True)
            return self._error_response(
                "服务器内部错误", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _validate_required_parameters(
        self,
        interval: Optional[str],
        market_type: Optional[str],
        start_time_str: Optional[str],
        end_time_str: Optional[str],
    ) -> None:
        """验证必填参数。

        Args:
            interval: K线周期
            market_type: 市场类型
            start_time_str: 开始时间字符串
            end_time_str: 结束时间字符串

        Raises:
            ValueError: 当必填参数缺失时抛出
        """
        if not interval:
            raise ValueError("缺少必填参数: interval")

        if not market_type:
            raise ValueError("缺少必填参数: market_type")

        if not start_time_str:
            raise ValueError("缺少必填参数: start_time")

        if not end_time_str:
            raise ValueError("缺少必填参数: end_time")

    def _validate_parameter_values(self, interval: str, market_type: str) -> None:
        """验证参数值。

        Args:
            interval: K线周期
            market_type: 市场类型

        Raises:
            ValueError: 当参数值无效时抛出
        """
        valid_intervals = ["1h", "4h", "1d"]
        if interval not in valid_intervals:
            raise ValueError(f"interval必须是以下值之一: {valid_intervals}")

        valid_market_types = ["spot", "futures"]
        if market_type not in valid_market_types:
            raise ValueError(f"market_type必须是以下值之一: {valid_market_types}")

    def _parse_datetime(self, datetime_str: str, param_name: str) -> datetime:
        """解析日期时间字符串。

        Args:
            datetime_str: 日期时间字符串
            param_name: 参数名称（用于错误信息）

        Returns:
            datetime: 解析后的datetime对象

        Raises:
            ValueError: 当日期时间格式错误时抛出
        """
        try:
            # 支持多种日期时间格式
            formats = [
                "%Y-%m-%dT%H:%M:%S",  # 2025-12-25T10:30:00
                "%Y-%m-%dT%H:%M:%S.%f",  # 2025-12-25T10:30:00.123456
                "%Y-%m-%dT%H:%M:%S%z",  # 2025-12-25T10:30:00+00:00
                "%Y-%m-%dT%H:%M:%S.%f%z",  # 2025-12-25T10:30:00.123456+00:00
                "%Y-%m-%d %H:%M:%S",  # 2025-12-25 10:30:00
                "%Y-%m-%d",  # 2025-12-25
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue

            raise ValueError(f"{param_name}日期时间格式错误，应为ISO 8601格式")

        except Exception as e:
            raise ValueError(f"{param_name}解析失败: {str(e)}")

    def _error_response(self, message: str, status_code: int) -> Response:
        """返回错误响应。

        Args:
            message: 错误信息
            status_code: HTTP状态码

        Returns:
            Response: 错误响应
        """
        return Response({"error": message, "code": status_code}, status=status_code)


class ChartDataAPIView(APIView):
    """图表数据API视图。

    提供GET /api/volume-trap/chart-data/{monitor_id}/端点，支持查询指定监控记录的图表数据。
    集成ChartDataFormatter进行数据格式化，返回Chart.js兼容的格式。

    路径参数:
        monitor_id (int): 监控记录ID

    响应格式:
        {
            "data": {  // Chart.js格式数据
                "labels": ["2025-12-25 10:00", ...],  // 时间标签
                "datasets": [  // 数据集数组
                    {
                        "label": "Open Price",
                        "data": [[timestamp, price], ...]
                    },
                    ...
                ]
            },
            "trigger_marker": {  // 触发点标记
                "time": 1703500800.0,  // 触发时间戳（秒）
                "price": 50000.0  // 触发价格
            }
        }

    错误响应:
        - 400 Bad Request: monitor_id格式错误
        - 404 Not Found: 监控记录不存在
        - 500 Internal Server Error: 服务器内部错误

    Examples:
        获取BTCUSDT监控记录的图表数据：
        GET /api/volume-trap/chart-data/123/

    性能特性:
        - 响应时间目标：<1秒（1000条K线记录以内）
        - 数据库查询优化：使用select_related和prefetch_related
        - 批量数据处理：避免N+1查询问题

    异常处理:
        - 参数验证：验证monitor_id格式和存在性
        - 业务异常：监控记录不存在、K线数据查询失败等
        - 系统异常：数据库连接错误等

    Related:
        - Task: TASK-006-005
        - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (5.4)
    """

    def __init__(self, **kwargs):
        """初始化图表数据API视图。

        Args:
            **kwargs: 父类初始化参数
        """
        super().__init__(**kwargs)
        self.kline_service = KLineDataService()
        self.chart_formatter = ChartDataFormatter()

    def get(self, request, monitor_id: int, format: Optional[str] = None) -> Response:
        """处理GET请求，返回图表数据。

        Args:
            request: HTTP请求对象
            monitor_id (int): 监控记录ID（路径参数）
            format (str, optional): 响应格式（保留参数）

        Returns:
            Response: DRF响应对象，包含图表数据或错误信息

        Raises:
            无（所有异常被捕获并转换为适当的HTTP响应）

        Examples:
            基础查询：
            >>> response = self.get(request, 123)
            >>> print(response.status_code)
            200
            >>> print(response.data['trigger_marker']['price'])
            50000.0

        Side Effects:
            - 查询数据库：执行VolumeTrapMonitor和KLine表查询
            - 调用服务：使用KLineDataService和ChartDataFormatter
            - 记录日志：记录API调用和执行时间
        """
        try:
            # === 参数验证 ===
            if not isinstance(monitor_id, int) or monitor_id <= 0:
                return self._error_response(
                    "monitor_id必须是正整数", status_code=status.HTTP_400_BAD_REQUEST
                )

            # === 查询监控记录 ===
            try:
                monitor = VolumeTrapMonitor.objects.get(id=monitor_id)
            except VolumeTrapMonitor.DoesNotExist:
                logger.warning(f"图表数据API - 监控记录不存在: monitor_id={monitor_id}")
                return self._error_response(
                    f"监控记录 {monitor_id} 不存在", status_code=status.HTTP_404_NOT_FOUND
                )

            # === 获取交易对符号 ===
            # 根据market_type获取对应的交易对符号
            if monitor.market_type == "futures":
                if not monitor.futures_contract:
                    return self._error_response(
                        "监控记录缺少合约信息", status_code=status.HTTP_404_NOT_FOUND
                    )
                symbol = monitor.futures_contract.symbol
            else:  # spot
                if not monitor.spot_contract:
                    return self._error_response(
                        "监控记录缺少合约信息", status_code=status.HTTP_404_NOT_FOUND
                    )
                symbol = monitor.spot_contract.symbol

            # === 获取K线数据 ===
            # 计算时间范围：监控记录前后的K线数据
            # 获取前后各30根K线，总共60根
            end_time = monitor.trigger_time + timedelta(hours=120)  # 触发后5天
            start_time = monitor.trigger_time - timedelta(hours=120)  # 触发前5天

            kline_result = self.kline_service.get_kline_data(
                symbol=symbol,
                interval=monitor.interval,
                market_type=monitor.market_type,
                start_time=start_time,
                end_time=end_time,
                limit=100,  # 限制返回数据量
            )

            # === 检查是否有K线数据 ===
            if not kline_result["data"]:
                logger.warning(
                    f"图表数据API - 没有K线数据: monitor_id={monitor_id}, "
                    f"symbol={symbol}, interval={monitor.interval}"
                )
                return self._error_response(
                    f"交易对 {symbol} 在时间范围内没有K线数据",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            # === 格式化图表数据 ===
            chart_data = self.chart_formatter.format_chart_data(
                kline_data=kline_result["data"],
                trigger_time=monitor.trigger_time.timestamp(),
                trigger_price=float(monitor.trigger_price),
            )

            # === 记录成功日志 ===
            logger.info(
                f"图表数据API调用成功: monitor_id={monitor_id}, "
                f"symbol={symbol}, kline_count={len(kline_result['data'])}"
            )

            # === 返回成功响应 ===
            return Response(
                {
                    "data": chart_data,
                    "trigger_marker": {
                        "time": monitor.trigger_time.timestamp(),
                        "price": float(monitor.trigger_price),
                    },
                },
                status=status.HTTP_200_OK,
            )

        except SymbolNotFoundError as e:
            logger.warning(f"图表数据API - 交易对不存在: {e}")
            # 重新获取symbol用于错误信息
            if monitor.market_type == "futures" and monitor.futures_contract:
                symbol = monitor.futures_contract.symbol
            elif monitor.market_type == "spot" and monitor.spot_contract:
                symbol = monitor.spot_contract.symbol
            else:
                symbol = "unknown"
            return self._error_response(
                f"交易对 '{symbol}' 不存在或已下架", status_code=status.HTTP_404_NOT_FOUND
            )

        except DataFormatError as e:
            logger.warning(f"图表数据API - 数据格式化失败: {e}")
            return self._error_response(
                "数据格式化失败", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except Exception as e:
            logger.error(f"图表数据API - 内部错误: {e}", exc_info=True)
            return self._error_response(
                "服务器内部错误", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _error_response(self, message: str, status_code: int) -> Response:
        """返回错误响应。

        Args:
            message: 错误信息
            status_code: HTTP状态码

        Returns:
            Response: 错误响应
        """
        return Response({"error": message, "code": status_code}, status=status_code)


# === 回测相关API视图 ===

from volume_trap.services.backtest_result_service import BacktestResultService
from volume_trap.services.chart_data_service import ChartDataService
from volume_trap.services.statistics_service import StatisticsCalculator


class BacktestDetailView(APIView):
    """回测详情API。

    GET /api/volume-trap/backtest/{id}/
    获取单个回测结果的详细信息。
    """

    def get(self, request, backtest_id):
        """获取回测详情。

        Args:
            request: HTTP请求对象
            backtest_id: 回测结果ID

        Returns:
            Response: 包含回测详情和图表数据的响应
        """
        try:
            # 获取回测结果
            service = BacktestResultService()
            backtest_result = service.get_backtest_by_id(backtest_id)

            if not backtest_result:
                return Response(
                    {"error": "回测结果不存在"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 格式化回测结果
            result_data = service._format_backtest_result(backtest_result)

            # 获取图表数据
            chart_service = ChartDataService()
            chart_data = chart_service.get_kline_chart_data(backtest_result)

            # 合并数据
            response_data = {
                "backtest": result_data,
                "chart": chart_data,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"获取回测详情失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BacktestListView(APIView):
    """回测列表API。

    GET /api/volume-trap/backtest/
    批量查询回测结果，支持分页、筛选、排序。
    """

    def get(self, request):
        """获取回测列表。

        Query Parameters:
            page: 页码（默认1）
            page_size: 每页数量（默认20，最大100）
            status: 状态筛选
            symbol: 交易对符号筛选
            interval: K线周期筛选
            market_type: 市场类型筛选
            is_profitable: 是否盈利筛选
            order_by: 排序字段（默认-entry_time）

        Returns:
            Response: 包含回测列表和分页信息的响应
        """
        try:
            # 解析查询参数
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
            status_filter = request.query_params.get("status")
            symbol = request.query_params.get("symbol")
            interval = request.query_params.get("interval")
            market_type = request.query_params.get("market_type")
            is_profitable_param = request.query_params.get("is_profitable")
            order_by = request.query_params.get("order_by", "-entry_time")

            # 限制page_size
            page_size = min(page_size, 100)

            # 转换is_profitable参数
            is_profitable = None
            if is_profitable_param is not None:
                is_profitable = is_profitable_param.lower() in ("true", "1", "yes")

            # 获取回测列表
            service = BacktestResultService()
            result = service.get_backtest_list(
                page=page,
                page_size=page_size,
                status=status_filter,
                symbol=symbol,
                interval=interval,
                market_type=market_type,
                is_profitable=is_profitable,
                order_by=order_by,
            )

            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"error": f"参数错误: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"获取回测列表失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StatisticsView(APIView):
    """统计API。

    GET /api/volume-trap/statistics/
    获取整体策略统计数据。
    """

    def get(self, request):
        """获取整体统计。

        Query Parameters:
            market_type: 市场类型筛选
            interval: K线周期筛选
            status_filter: 状态筛选
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）

        Returns:
            Response: 包含统计数据的响应
        """
        try:
            # 解析查询参数
            market_type = request.query_params.get("market_type")
            interval = request.query_params.get("interval")
            status_filter = request.query_params.get("status_filter")
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            # 计算统计
            calculator = StatisticsCalculator()
            stats = calculator.calculate_overall_stats(
                market_type=market_type,
                interval=interval,
                status_filter=status_filter,
                start_date=start_date,
                end_date=end_date,
            )

            # 格式化统计数据
            response_data = {
                "id": stats.id,
                "name": stats.name,
                "market_type": stats.market_type,
                "interval": stats.interval,
                "total_trades": stats.total_trades,
                "profitable_trades": stats.profitable_trades,
                "losing_trades": stats.losing_trades,
                "win_rate": float(stats.win_rate) if stats.win_rate else 0,
                "avg_profit_percent": float(stats.avg_profit_percent) if stats.avg_profit_percent else 0,
                "max_profit_percent": float(stats.max_profit_percent) if stats.max_profit_percent else 0,
                "min_profit_percent": float(stats.min_profit_percent) if stats.min_profit_percent else 0,
                "total_profit_percent": float(stats.total_profit_percent) if stats.total_profit_percent else 0,
                "avg_max_drawdown": float(stats.avg_max_drawdown) if stats.avg_max_drawdown else 0,
                "worst_drawdown": float(stats.worst_drawdown) if stats.worst_drawdown else 0,
                "avg_bars_to_lowest": float(stats.avg_bars_to_lowest) if stats.avg_bars_to_lowest else 0,
                "profit_factor": float(stats.profit_factor) if stats.profit_factor else 0,
                "created_at": stats.created_at.isoformat(),
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"获取统计数据失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StatisticsSummaryView(APIView):
    """统计摘要API。

    GET /api/volume-trap/statistics/summary/
    获取回测结果的统计摘要。
    """

    def get(self, request):
        """获取统计摘要。

        Returns:
            Response: 包含统计摘要的响应
        """
        try:
            service = BacktestResultService()
            summary = service.get_statistics_summary()

            return Response(summary, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"获取统计摘要失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BacktestSearchView(APIView):
    """回测搜索API。

    GET /api/volume-trap/backtest/search/
    搜索回测结果（按交易对符号）。
    """

    def get(self, request):
        """搜索回测结果。

        Query Parameters:
            q: 搜索关键词（交易对符号）
            page: 页码（默认1）
            page_size: 每页数量（默认20）

        Returns:
            Response: 包含搜索结果的响应
        """
        try:
            query = request.query_params.get("q", "").strip()
            if not query:
                return Response(
                    {"error": "请提供搜索关键词"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))

            # 限制page_size
            page_size = min(page_size, 100)

            # 搜索回测结果
            service = BacktestResultService()
            result = service.search_backtest_results(
                query=query,
                page=page,
                page_size=page_size,
            )

            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"error": f"参数错误: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"搜索失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChartDataView(APIView):
    """图表数据API。

    GET /api/volume-trap/chart/{backtest_id}/
    获取特定回测的图表数据。
    """

    def get(self, request, backtest_id):
        """获取图表数据。

        Args:
            request: HTTP请求对象
            backtest_id: 回测结果ID

        Query Parameters:
            format: 图表类型（kline/price，默认kline）

        Returns:
            Response: 包含图表数据的响应
        """
        try:
            # 获取图表类型
            chart_format = request.query_params.get("format", "kline")

            # 获取回测结果
            service = BacktestResultService()
            backtest_result = service.get_backtest_by_id(backtest_id)

            if not backtest_result:
                return Response(
                    {"error": "回测结果不存在"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 获取图表数据
            chart_service = ChartDataService()

            if chart_format == "price":
                chart_data = chart_service.get_price_series(backtest_result)
            else:
                chart_data = chart_service.get_kline_chart_data(backtest_result)

            return Response(chart_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"获取图表数据失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
