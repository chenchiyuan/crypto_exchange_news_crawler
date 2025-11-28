"""
测试Scanner命令
Test Scanner Command
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from grid_trading.models import GridZone
from vp_squeeze.services.four_peaks_analyzer import FourPeaksBox, KeyLevel


@pytest.fixture
def mock_four_peaks_result():
    """Mock FourPeaksBox分析结果"""
    return FourPeaksBox(
        symbol='BTCUSDT',
        support2=KeyLevel(
            price=95000.0,
            original_peak=95050.0,
            volume=1000000.0,
            volume_strength=85,
            ma_adjusted=True,
            nearest_ma=95000.0,
            ma_type='MA25',
            confidence=88,
            level_type='support2'
        ),
        support1=KeyLevel(
            price=96000.0,
            original_peak=96020.0,
            volume=1200000.0,
            volume_strength=90,
            ma_adjusted=False,
            nearest_ma=None,
            ma_type=None,
            confidence=85,
            level_type='support1'
        ),
        resistance1=KeyLevel(
            price=98000.0,
            original_peak=98030.0,
            volume=1100000.0,
            volume_strength=88,
            ma_adjusted=True,
            nearest_ma=98000.0,
            ma_type='MA25',
            confidence=90,
            level_type='resistance1'
        ),
        resistance2=KeyLevel(
            price=99000.0,
            original_peak=99050.0,
            volume=1050000.0,
            volume_strength=86,
            ma_adjusted=False,
            nearest_ma=None,
            ma_type=None,
            confidence=87,
            level_type='resistance2'
        ),
        small_box={
            'support': 96000.0,
            'resistance': 98000.0,
            'midpoint': 97000.0,
            'width_pct': 2.08
        },
        large_box={
            'support': 95000.0,
            'resistance': 99000.0,
            'midpoint': 97000.0,
            'width_pct': 4.21
        },
        current_price=97000.0,
        position_in_box='in_small',
        overall_score=88,
        volume_quality=87,
        ma_alignment=85
    )


@pytest.mark.django_db
class TestScannerCommand:
    """Scanner命令测试"""

    @patch('grid_trading.management.commands.scanner.analyze_four_peaks')
    @patch('grid_trading.management.commands.scanner.analyze_multi_timeframe')
    def test_scanner_creates_four_zones(self, mock_multi_tf, mock_four_peaks, mock_four_peaks_result):
        """测试Scanner创建4个GridZone"""
        # Mock VP-Squeeze分析
        mock_multi_tf.return_value = ([], None)
        mock_four_peaks.return_value = mock_four_peaks_result

        # 执行命令
        out = StringIO()
        call_command('scanner', '--symbol', 'btc', stdout=out)

        # 验证创建了4个区间
        zones = GridZone.objects.filter(symbol='BTCUSDT', is_active=True)
        assert zones.count() == 4

        # 验证支撑区
        support_zones = zones.filter(zone_type='support').order_by('price_low')
        assert support_zones.count() == 2
        assert float(support_zones[0].price_low) == pytest.approx(95000.0 * 0.998, rel=0.01)
        assert float(support_zones[1].price_low) == pytest.approx(96000.0 * 0.998, rel=0.01)

        # 验证压力区
        resistance_zones = zones.filter(zone_type='resistance').order_by('price_low')
        assert resistance_zones.count() == 2
        assert float(resistance_zones[0].price_low) == pytest.approx(98000.0 * 0.998, rel=0.01)
        assert float(resistance_zones[1].price_low) == pytest.approx(99000.0 * 0.998, rel=0.01)

    @patch('grid_trading.management.commands.scanner.analyze_four_peaks')
    @patch('grid_trading.management.commands.scanner.analyze_multi_timeframe')
    def test_scanner_deactivates_old_zones(self, mock_multi_tf, mock_four_peaks, mock_four_peaks_result):
        """测试Scanner停用旧区间"""
        # 创建旧区间
        old_zone = GridZone.objects.create(
            symbol='BTCUSDT',
            zone_type='support',
            price_low=Decimal('94000.00'),
            price_high=Decimal('94500.00'),
            confidence=80,
            expires_at=timezone.now() + timedelta(hours=2),
            is_active=True
        )

        # Mock VP-Squeeze分析
        mock_multi_tf.return_value = ([], None)
        mock_four_peaks.return_value = mock_four_peaks_result

        # 执行命令
        call_command('scanner', '--symbol', 'btc')

        # 验证旧区间被停用
        old_zone.refresh_from_db()
        assert old_zone.is_active is False

        # 验证新区间被创建
        active_zones = GridZone.objects.filter(symbol='BTCUSDT', is_active=True)
        assert active_zones.count() == 4

    @patch('grid_trading.management.commands.scanner.analyze_four_peaks')
    @patch('grid_trading.management.commands.scanner.analyze_multi_timeframe')
    def test_scanner_sets_expiration_time(self, mock_multi_tf, mock_four_peaks, mock_four_peaks_result):
        """测试Scanner设置正确的过期时间"""
        # Mock VP-Squeeze分析
        mock_multi_tf.return_value = ([], None)
        mock_four_peaks.return_value = mock_four_peaks_result

        # 记录执行前时间
        before_time = timezone.now()

        # 执行命令
        call_command('scanner', '--symbol', 'btc')

        # 验证过期时间（应该是4小时后）
        zones = GridZone.objects.filter(symbol='BTCUSDT', is_active=True)
        for zone in zones:
            # 过期时间应该在 before_time + 4小时 附近（允许5分钟误差）
            expected_expiry = before_time + timedelta(hours=4)
            time_diff = abs((zone.expires_at - expected_expiry).total_seconds())
            assert time_diff < 300  # 5分钟 = 300秒

    @patch('grid_trading.management.commands.scanner.analyze_four_peaks')
    @patch('grid_trading.management.commands.scanner.analyze_multi_timeframe')
    def test_scanner_saves_confidence_scores(self, mock_multi_tf, mock_four_peaks, mock_four_peaks_result):
        """测试Scanner保存置信度分数"""
        # Mock VP-Squeeze分析
        mock_multi_tf.return_value = ([], None)
        mock_four_peaks.return_value = mock_four_peaks_result

        # 执行命令
        call_command('scanner', '--symbol', 'btc')

        # 验证置信度
        zones = GridZone.objects.filter(symbol='BTCUSDT', is_active=True).order_by('price_low')

        # S2: confidence=88
        assert zones[0].confidence == 88

        # S1: confidence=85
        assert zones[1].confidence == 85

        # R1: confidence=90
        assert zones[2].confidence == 90

        # R2: confidence=87
        assert zones[3].confidence == 87

    def test_scanner_invalid_symbol(self):
        """测试Scanner使用无效交易对"""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError, match="配置错误"):
            call_command('scanner', '--symbol', 'sol')

    @patch('grid_trading.management.commands.scanner.analyze_four_peaks')
    @patch('grid_trading.management.commands.scanner.analyze_multi_timeframe')
    def test_scanner_output_format(self, mock_multi_tf, mock_four_peaks, mock_four_peaks_result):
        """测试Scanner输出格式"""
        # Mock VP-Squeeze分析
        mock_multi_tf.return_value = ([], None)
        mock_four_peaks.return_value = mock_four_peaks_result

        # 执行命令
        out = StringIO()
        call_command('scanner', '--symbol', 'btc', stdout=out)

        output = out.getvalue()

        # 验证输出包含关键信息
        assert 'Scanner完成' in output
        assert 'BTCUSDT' in output
        assert '当前价格' in output
        assert '支撑' in output
        assert '压力' in output
        assert '总计创建: 4个区间' in output

    @pytest.mark.django_db
    def test_grid_zone_model_is_price_in_zone(self):
        """测试GridZone.is_price_in_zone()方法"""
        zone = GridZone.objects.create(
            symbol='BTCUSDT',
            zone_type='support',
            price_low=Decimal('96000.00'),
            price_high=Decimal('96500.00'),
            confidence=85,
            expires_at=timezone.now() + timedelta(hours=4),
            is_active=True
        )

        # 测试价格在区间内
        assert zone.is_price_in_zone(Decimal('96200.00')) is True

        # 测试价格在区间边界
        assert zone.is_price_in_zone(Decimal('96000.00')) is True
        assert zone.is_price_in_zone(Decimal('96500.00')) is True

        # 测试价格在区间外
        assert zone.is_price_in_zone(Decimal('95999.00')) is False
        assert zone.is_price_in_zone(Decimal('96501.00')) is False

    @pytest.mark.django_db
    def test_grid_zone_model_is_expired(self):
        """测试GridZone.is_expired()方法"""
        # 未过期区间
        future_zone = GridZone.objects.create(
            symbol='BTCUSDT',
            zone_type='support',
            price_low=Decimal('96000.00'),
            price_high=Decimal('96500.00'),
            confidence=85,
            expires_at=timezone.now() + timedelta(hours=2),
            is_active=True
        )
        assert future_zone.is_expired() is False

        # 已过期区间
        expired_zone = GridZone.objects.create(
            symbol='BTCUSDT',
            zone_type='support',
            price_low=Decimal('95000.00'),
            price_high=Decimal('95500.00'),
            confidence=80,
            expires_at=timezone.now() - timedelta(hours=1),
            is_active=True
        )
        assert expired_zone.is_expired() is True
