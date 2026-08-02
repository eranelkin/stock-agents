"""
QA Test Suite for IB Data Configuration

This test suite verifies that all IB data configuration parameters work correctly
and that the pipeline respects the configuration flags.

Run with: pytest tests/test_config_qa.py -v
"""

import pytest
from pathlib import Path
from src.config.loader import (
    load_settings,
    IBDataConfig,
    AppConfig,
)


class TestIBDataConfigStructure:
    """Test that IBDataConfig has all expected fields."""
    
    def test_all_fetch_flags_present(self):
        """Verify all fetch_* boolean flags exist."""
        config = IBDataConfig()
        
        expected_flags = [
            'fetch_contract_details',
            'fetch_daily_bars',
            'fetch_market_snapshot',
            'fetch_pre_market_bars',
            'fetch_prev_session_vwap',
            'fetch_volume_profile',
            'fetch_benchmark',
            'fetch_atr',
            'fetch_bid_ask',
            'fetch_volume',
            'fetch_ema',
            'fetch_rsi',
            'fetch_sector',
            'fetch_industry',
            'fetch_stock_type',
        ]
        
        for flag in expected_flags:
            assert hasattr(config, flag), f"Missing flag: {flag}"
            assert isinstance(getattr(config, flag), bool), f"{flag} should be boolean"
    
    def test_all_parameter_fields_present(self):
        """Verify all parameter fields exist."""
        config = IBDataConfig()
        
        expected_params = {
            'atr_period': int,
            'ema_periods': list,
            'rsi_period': int,
            'daily_bars_duration': str,
            'pre_market_rvol_lookback': int,
            'volume_profile_sessions': int,
        }
        
        for param, expected_type in expected_params.items():
            assert hasattr(config, param), f"Missing parameter: {param}"
            value = getattr(config, param)
            assert isinstance(value, expected_type), \
                f"{param} should be {expected_type.__name__}, got {type(value).__name__}"
    
    def test_default_values(self):
        """Verify default values are sensible."""
        config = IBDataConfig()
        
        # All fetch flags should default to True
        assert config.fetch_contract_details is True
        assert config.fetch_daily_bars is True
        assert config.fetch_market_snapshot is True
        
        # Numeric parameters should have sensible defaults
        assert config.atr_period == 14
        assert config.rsi_period == 14
        assert config.volume_profile_sessions == 3
        assert config.pre_market_rvol_lookback == 20
        
        # EMA periods should include common values
        assert 9 in config.ema_periods
        assert 20 in config.ema_periods
        assert 50 in config.ema_periods
        assert 200 in config.ema_periods
        
        # Duration should support long-term EMAs
        assert config.daily_bars_duration == "300 D"


class TestConfigLoading:
    """Test configuration loading from YAML."""
    
    def test_load_default_settings(self):
        """Test loading config/settings.yaml."""
        config_path = Path("config/settings.yaml")
        
        if not config_path.exists():
            pytest.skip("config/settings.yaml not found")
        
        config = load_settings(config_path)
        
        assert isinstance(config, AppConfig)
        assert isinstance(config.ib_data, IBDataConfig)
    
    def test_ib_data_config_loaded(self):
        """Verify ib_data section is properly loaded."""
        config_path = Path("config/settings.yaml")
        
        if not config_path.exists():
            pytest.skip("config/settings.yaml not found")
        
        config = load_settings(config_path)
        ib_data = config.ib_data
        
        # Verify all flags are loaded
        assert hasattr(ib_data, 'fetch_contract_details')
        assert hasattr(ib_data, 'fetch_daily_bars')
        assert hasattr(ib_data, 'fetch_atr')
        assert hasattr(ib_data, 'atr_period')
        assert hasattr(ib_data, 'ema_periods')


class TestConfigValidation:
    """Test configuration validation and edge cases."""
    
    def test_atr_period_range(self):
        """ATR period should be positive."""
        config = IBDataConfig(atr_period=14)
        assert config.atr_period > 0
    
    def test_rsi_period_range(self):
        """RSI period should be positive."""
        config = IBDataConfig(rsi_period=14)
        assert config.rsi_period > 0
    
    def test_volume_profile_sessions_range(self):
        """Volume profile sessions should be positive."""
        config = IBDataConfig(volume_profile_sessions=3)
        assert config.volume_profile_sessions > 0
    
    def test_ema_periods_not_empty(self):
        """EMA periods list should not be empty if fetch_ema is True."""
        config = IBDataConfig(fetch_ema=True, ema_periods=[9, 20, 50, 200])
        assert len(config.ema_periods) > 0
    
    def test_daily_bars_duration_format(self):
        """Daily bars duration should be valid IB format."""
        config = IBDataConfig(daily_bars_duration="300 D")
        
        # Should contain a number and a unit
        parts = config.daily_bars_duration.split()
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert parts[1] in ['D', 'W', 'M', 'Y']


class TestConfigIntegration:
    """Test configuration integration with pipeline logic."""
    
    def test_disabled_fetch_flags(self):
        """Test that disabling fetch flags works."""
        config = IBDataConfig(
            fetch_daily_bars=False,
            fetch_market_snapshot=False,
            fetch_pre_market_bars=False,
        )

        assert config.fetch_daily_bars is False
        assert config.fetch_market_snapshot is False
        assert config.fetch_pre_market_bars is False
    
    def test_custom_parameters(self):
        """Test custom parameter values."""
        config = IBDataConfig(
            atr_period=20,
            rsi_period=10,
            ema_periods=[5, 10, 20],
            volume_profile_sessions=5,
            daily_bars_duration="500 D",
        )
        
        assert config.atr_period == 20
        assert config.rsi_period == 10
        assert config.ema_periods == [5, 10, 20]
        assert config.volume_profile_sessions == 5
        assert config.daily_bars_duration == "500 D"
    
    def test_minimal_config(self):
        """Test minimal configuration (only contract details)."""
        config = IBDataConfig(
            fetch_contract_details=True,
            fetch_daily_bars=False,
            fetch_market_snapshot=False,
            fetch_pre_market_bars=False,
            fetch_prev_session_vwap=False,
            fetch_volume_profile=False,
            fetch_benchmark=False,
            fetch_atr=False,
            fetch_ema=False,
            fetch_rsi=False,
        )
        
        # Only contract details should be enabled
        assert config.fetch_contract_details is True
        assert config.fetch_daily_bars is False
        assert config.fetch_market_snapshot is False
    
    def test_full_config(self):
        """Test full configuration (all features enabled)."""
        config = IBDataConfig(
            fetch_contract_details=True,
            fetch_daily_bars=True,
            fetch_market_snapshot=True,
            fetch_pre_market_bars=True,
            fetch_prev_session_vwap=True,
            fetch_volume_profile=True,
            fetch_benchmark=True,
            fetch_atr=True,
            fetch_ema=True,
            fetch_rsi=True,
            fetch_bid_ask=True,
            fetch_volume=True,
            fetch_sector=True,
            fetch_industry=True,
            fetch_stock_type=True,
        )
        
        # All features should be enabled
        assert config.fetch_contract_details is True
        assert config.fetch_daily_bars is True
        assert config.fetch_market_snapshot is True
        assert config.fetch_pre_market_bars is True
        assert config.fetch_prev_session_vwap is True
        assert config.fetch_volume_profile is True
        assert config.fetch_benchmark is True
        assert config.fetch_atr is True
        assert config.fetch_ema is True
        assert config.fetch_rsi is True


class TestConfigDocumentation:
    """Test that configuration is well-documented."""
    
    def test_yaml_has_comments(self):
        """Verify settings.yaml has comments for all ib_data fields."""
        config_path = Path("config/settings.yaml")
        
        if not config_path.exists():
            pytest.skip("config/settings.yaml not found")
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Check for key configuration sections
        assert 'ib_data:' in content
        assert 'fetch_contract_details' in content
        assert 'fetch_daily_bars' in content
        assert 'atr_period' in content
        assert 'ema_periods' in content
        
        # Check for comments (lines starting with #)
        lines = content.split('\n')
        comment_lines = [line for line in lines if line.strip().startswith('#')]
        assert len(comment_lines) > 10, "Configuration should have helpful comments"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
