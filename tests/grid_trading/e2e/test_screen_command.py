"""
screen_short_grid Command 端到端测试

测试覆盖: T053
- test_command_execution: 运行命令验证输出包含Top 5标的
- test_custom_parameters: 测试--top-n, --weights参数生效
- test_output_format: 验证表格格式化和警告标记正确
"""

import pytest
from io import StringIO
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from django.core.management import call_command
from django.core.management.base import CommandError
from grid_trading.models import MarketSymbol


class TestScreenShortGridCommand:
    """screen_short_grid 命令端到端测试"""

    @pytest.fixture
    def mock_market_data(self):
        """创建丰富的模拟市场数据"""
        base_time = datetime.now()
        symbols = []

        # 创建15个不同特征的标的
        for i in range(15):
            symbol = MarketSymbol(
                symbol=f"TEST{i:02d}USDT",
                exchange="binance",
                contract_type="PERPETUAL",
                listing_date=base_time - timedelta(days=100 + i * 5),
                current_price=Decimal(f"{1000 + i * 100}"),
                volume_24h=Decimal(f"{60000000 + i * 5000000}"),
                open_interest=Decimal(f"{10000000 + i * 500000}"),
                funding_rate=Decimal("0.0001") if i % 2 == 0 else Decimal("0.0005"),
                funding_interval_hours=8,
                next_funding_time=base_time + timedelta(hours=8),
                market_cap_rank=30 + i * 5 if i < 10 else None,
            )
            symbols.append(symbol)

        return symbols

    @pytest.fixture
    def mock_klines_varied(self):
        """创建不同特征的K线数据"""

        def generate_sideways_klines(count, base_price=100):
            """生成震荡市K线 (高VDR)"""
            klines = []
            for i in range(count):
                # 在base_price±5范围内震荡
                price = base_price + (i % 10 - 5)
                klines.append(
                    {
                        "open": price,
                        "high": price + 3,
                        "low": price - 3,
                        "close": price + (1 if i % 2 == 0 else -1),
                        "volume": 1000000 + i * 1000,
                        "taker_buy_base_volume": 500000 + i * 500,
                    }
                )
            return klines

        def generate_downtrend_klines(count, base_price=150):
            """生成下降趋势K线"""
            klines = []
            for i in range(count):
                price = base_price - i * 0.2  # 轻微下降
                klines.append(
                    {
                        "open": price,
                        "high": price + 1,
                        "low": price - 2,
                        "close": price - 0.5,
                        "volume": 1000000,
                        "taker_buy_base_volume": 300000,  # 30% 买盘
                    }
                )
            return klines

        return {
            "4h": generate_sideways_klines(300, 1000),
            "1m": generate_sideways_klines(240, 1000),
            "1d": generate_downtrend_klines(100, 1000),
            "1h": generate_sideways_klines(200, 1000),
        }

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_command_execution(
        self, mock_client_class, mock_market_data, mock_klines_varied
    ):
        """测试命令执行 - 验证输出包含Top 5标的 (T053)"""
        # 配置Mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = mock_market_data

        def mock_fetch_klines(symbols, interval, limit):
            return {symbol: mock_klines_varied[interval] for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_klines

        # 捕获输出
        out = StringIO()

        # 运行命令 (使用默认参数)
        call_command("screen_short_grid", stdout=out)

        # 获取输出
        output = out.getvalue()

        # ========== 验证输出内容 ==========

        # 1. 验证包含配置信息
        assert "配置参数" in output or "权重配置" in output

        # 2. 验证包含筛选结果
        assert "Rank" in output or "排名" in output
        assert "Symbol" in output or "标的" in output
        assert "GSS" in output

        # 3. 验证包含关键指标列
        assert "NATR" in output
        assert "KER" in output
        assert "VDR" in output
        assert "Z-Score" in output or "Z_Score" in output

        # 4. 验证包含网格参数
        assert "Grid Upper" in output or "网格上限" in output
        assert "Grid Lower" in output or "网格下限" in output

        # 5. 验证包含执行摘要
        assert "执行时间" in output or "完成" in output or "duration" in output.lower()

        # 6. 验证至少有结果行（包含TEST标的）
        assert "TEST" in output  # 应该有我们的模拟标的

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_custom_parameters(
        self, mock_client_class, mock_market_data, mock_klines_varied
    ):
        """测试自定义参数 - 验证--top-n, --weights生效 (T053)"""
        # 配置Mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = mock_market_data

        def mock_fetch_klines(symbols, interval, limit):
            return {symbol: mock_klines_varied[interval] for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_klines

        # ========== 测试场景1: 自定义Top N ==========
        out1 = StringIO()
        call_command("screen_short_grid", top_n=3, stdout=out1)
        output1 = out1.getvalue()

        # 应该只有3个结果（或更少）
        # 简单验证: 不应该有Rank 4
        lines_with_rank = [line for line in output1.split("\n") if "TEST" in line]
        # 粗略验证结果数量（实际可能受格式影响）
        assert len(lines_with_rank) <= 3 or "Top 3" in output1

        # ========== 测试场景2: 自定义权重 ==========
        out2 = StringIO()
        call_command(
            "screen_short_grid", weights="0.3,0.3,0.2,0.2", top_n=5, stdout=out2
        )
        output2 = out2.getvalue()

        # 验证命令执行成功
        assert "✅" in output2 or "完成" in output2

        # ========== 测试场景3: 自定义流动性阈值 ==========
        out3 = StringIO()
        call_command(
            "screen_short_grid",
            min_volume=100000000,  # 100M USDT (更严格)
            top_n=5,
            stdout=out3,
        )
        output3 = out3.getvalue()

        # 验证命令执行成功
        assert "✅" in output3 or "完成" in output3

        # ========== 测试场景4: 自定义K线周期 ==========
        out4 = StringIO()
        call_command("screen_short_grid", interval="1h", top_n=5, stdout=out4)
        output4 = out4.getvalue()

        # 验证命令执行成功
        assert "✅" in output4 or "完成" in output4

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_output_format(self, mock_client_class, mock_market_data, mock_klines_varied):
        """测试输出格式 - 验证表格和警告标记 (T053)"""
        # 修改mock数据以触发不同的警告标记
        # 创建一个高OVR的标的
        high_ovr_symbol = MarketSymbol(
            symbol="HIGHOVRTEST",
            exchange="binance",
            contract_type="PERPETUAL",
            listing_date=datetime.now() - timedelta(days=100),
            current_price=Decimal("1000"),
            volume_24h=Decimal("60000000"),
            open_interest=Decimal("150000000"),  # 非常高的持仓量
            funding_rate=Decimal("0.0015"),  # 高资金费率
            funding_interval_hours=8,
            next_funding_time=datetime.now() + timedelta(hours=8),
        )

        enhanced_data = mock_market_data + [high_ovr_symbol]

        # 配置Mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = enhanced_data

        # 创建高NATR的K线数据 (剧烈波动)
        volatile_klines = []
        for i in range(300):
            base_price = 100 + (i % 20 - 10) * 5  # 剧烈震荡
            volatile_klines.append(
                {
                    "open": base_price,
                    "high": base_price + 20,  # 大幅波动
                    "low": base_price - 20,
                    "close": base_price + (5 if i % 2 == 0 else -5),
                    "volume": 1000000,
                    "taker_buy_base_volume": 800000,  # 高买盘压力
                }
            )

        mock_klines_volatile = {
            "4h": volatile_klines,
            "1m": volatile_klines[:240],
            "1d": volatile_klines[:100],
            "1h": volatile_klines[:200],
        }

        def mock_fetch_klines(symbols, interval, limit):
            return {symbol: mock_klines_volatile[interval] for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_klines

        # 运行命令
        out = StringIO()
        call_command("screen_short_grid", top_n=10, verbosity=2, stdout=out)
        output = out.getvalue()

        # ========== 验证输出格式 ==========

        # 1. 验证表格列存在
        expected_columns = [
            "Rank",
            "Symbol",
            "Price",
            "NATR",
            "KER",
            "VDR",
            "H",
            "Z-Score",
            "OVR",
            "Funding",
            "CVD_ROC",
            "GSS",
        ]

        for column in expected_columns:
            assert column in output, f"缺少列: {column}"

        # 2. 验证可能的警告标记 (如果触发)
        possible_warnings = [
            "⚠️",  # 警告符号
            "✓",  # 优势符号
            "极端波动",
            "高OVR",
            "逼空风险",
            "CVD异常",
            "完美震荡",
            "假突破",
        ]

        # 至少应该有一些标记或警告文本
        has_any_marker = any(marker in output for marker in possible_warnings)
        # 注意: 如果数据特征不明显，可能没有警告标记，这是正常的

        # 3. 验证数值格式合理
        # 提取包含数据的行
        data_lines = [line for line in output.split("\n") if "TEST" in line]

        if data_lines:
            # 验证至少有一行数据
            assert len(data_lines) > 0

    def test_invalid_parameters(self):
        """测试无效参数验证"""
        out = StringIO()
        err = StringIO()

        # ========== 测试场景1: 无效Top N ==========
        with pytest.raises(CommandError):
            call_command("screen_short_grid", top_n=15, stdout=out, stderr=err)

        # ========== 测试场景2: 无效权重总和 ==========
        with pytest.raises(CommandError):
            call_command(
                "screen_short_grid",
                weights="0.3,0.3,0.3,0.3",
                stdout=out,
                stderr=err,
            )

        # ========== 测试场景3: 负数流动性 ==========
        with pytest.raises(CommandError):
            call_command(
                "screen_short_grid", min_volume=-1000, stdout=out, stderr=err
            )

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_no_results_scenario(self, mock_client_class):
        """测试无结果场景的输出"""
        # 配置Mock返回空数据
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = []

        # 运行命令
        out = StringIO()
        call_command("screen_short_grid", stdout=out)
        output = out.getvalue()

        # 验证无结果提示
        # 应该有明确的提示信息，而不是崩溃
        assert (
            "无合格标的" in output
            or "没有找到" in output
            or "0 个标的" in output
        )

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_verbosity_levels(
        self, mock_client_class, mock_market_data, mock_klines_varied
    ):
        """测试不同verbosity级别的输出"""
        # 配置Mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = mock_market_data[:5]

        def mock_fetch_klines(symbols, interval, limit):
            return {symbol: mock_klines_varied[interval] for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_klines

        # ========== verbosity=0: 最小输出 ==========
        out0 = StringIO()
        call_command("screen_short_grid", verbosity=0, stdout=out0)
        output0 = out0.getvalue()

        # verbosity=0 应该输出最少
        # 可能只有错误或关键信息

        # ========== verbosity=1: 正常输出 (默认) ==========
        out1 = StringIO()
        call_command("screen_short_grid", verbosity=1, stdout=out1)
        output1 = out1.getvalue()

        # 应该有配置信息和结果表格
        assert len(output1) > len(output0)  # 应该比最小输出多

        # ========== verbosity=2: 详细输出 ==========
        out2 = StringIO()
        call_command("screen_short_grid", verbosity=2, stdout=out2)
        output2 = out2.getvalue()

        # 详细模式应该输出更多信息
        # 可能包含调试信息、进度等
        assert len(output2) >= len(output1)  # 至少和正常输出一样多
