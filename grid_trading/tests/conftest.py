"""
Pytest configuration for grid_trading tests.
"""
import os
import django
import pytest

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

@pytest.fixture(scope='session')
def django_db_setup():
    """Setup test database."""
    pass

@pytest.fixture
def grid_config_data():
    """Sample grid configuration data for testing."""
    return {
        'name': 'test_btc_short',
        'exchange': 'binance',
        'symbol': 'BTCUSDT',
        'grid_mode': 'short',
        'upper_price': 65000.00,
        'lower_price': 60000.00,
        'grid_levels': 20,
        'trade_amount': 0.01,
        'max_position_size': 0.20,
        'stop_loss_buffer_pct': 0.005,
        'refresh_interval_ms': 1000,
        'price_tick': 0.01,
        'qty_step': 0.001,
    }

@pytest.fixture
def mock_binance_client(mocker):
    """Mock Binance Futures client for testing."""
    client = mocker.Mock()
    client.futures_create_order = mocker.Mock(return_value={'orderId': '12345'})
    client.futures_cancel_order = mocker.Mock(return_value={'status': 'CANCELED'})
    return client
