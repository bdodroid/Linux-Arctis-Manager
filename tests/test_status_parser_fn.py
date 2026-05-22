from linux_arctis_manager.status_parser_fn import int_int_mapping, int_str_mapping, on_off, percentage


def test_percentage():
    fn = percentage
    assert getattr(fn, '_status_type') == 'percentage'

    assert fn(0, 100, 0) == 0
    assert fn(-56, 0, -56) == 0

    assert fn(0, 100, 75) == 75
    assert fn(-200, 0, -50) == 75

    assert fn(0, 100, 100) == 100
    assert fn(-123, 123, 123) == 100

def test_on_off():
    fn = on_off
    assert getattr(fn, '_status_type') == 'on_off'

    assert fn(0x01, 0x01, 0) == 'on'
    assert fn(0, 1, 0) == 'off'
    assert fn(1, 1, 3) == 'on'
    assert fn(3, 2, 3) == 'off'

def test_int_str_mapping():
    fn = int_str_mapping
    mapping = {0x00: "off", 0x01: "-12db", 0x02: "on"}

    assert getattr(fn, '_status_type') == 'int_str_mapping'

    assert fn(mapping, 0x00) == "off"
    assert fn(mapping, 0x01) == "-12db"
    assert fn(mapping, 0x02) == "on"
    assert fn(mapping, 0x03) is None

def test_int_int_mapping():
    fn = int_int_mapping
    mapping = {0: 10, 1: 20, 2: 30}

    assert getattr(fn, '_status_type') == 'int_int_mapping'

    assert fn(mapping, 0) == 10
    assert fn(mapping, 1) == 20
    assert fn(mapping, 2) == 30
    assert fn(mapping, 3) is None


from unittest.mock import MagicMock, patch
import pytest
from pathlib import Path
from ruamel.yaml import YAML
from linux_arctis_manager.core import CoreEngine
from linux_arctis_manager.config import DeviceConfiguration


@pytest.fixture
def mock_dependencies():
    with patch('linux_arctis_manager.pactl.PulseAudioManager.get_instance') as mock_pa, \
         patch('linux_arctis_manager.usb_devices_monitor.USBDevicesMonitor.get_instance') as mock_usb_mon, \
         patch('linux_arctis_manager.settings.GeneralSettings.read_from_file') as mock_gen_settings:
        
        mock_pa.return_value = MagicMock()
        mock_usb_mon.return_value = MagicMock()
        
        gen_settings_inst = MagicMock()
        gen_settings_inst.redirect_audio_on_connect = False
        mock_gen_settings.return_value = gen_settings_inst
        
        yield {
            'pa': mock_pa.return_value,
            'usb_mon': mock_usb_mon.return_value,
            'gen_settings': gen_settings_inst
        }


def test_nova_elite_mixer_balance(mock_dependencies):
    # Load the real Nova Elite configuration yaml
    config_path = Path(__file__).parent.parent / 'src' / 'linux_arctis_manager' / 'devices' / 'nova_elite.yaml'
    yaml = YAML(typ='safe')
    config_yaml = yaml.load(config_path)
    config = DeviceConfiguration(config_yaml)
    
    with patch('linux_arctis_manager.core.load_device_configurations', return_value=[config]):
        engine = CoreEngine()
        
        # Setup mock device status and config
        engine.device_config = config
        engine.device_status = engine.new_device_status()
        engine.usb_device = MagicMock()
        
        # Verify sync_mixer_to_hardware is False for Nova Elite
        assert engine.device_config.sync_mixer_to_hardware is False
        
        # 1. Test set_mixer_balance (software change)
        engine.set_mixer_balance(25)  # 25 out of 100 -> media 100, chat 50
        
        # Audio manager set_mix should have been called
        engine.pa_audio_manager.set_mix.assert_called_with(100, 50)
        
        # device_status should be updated with new software values
        assert engine.device_status['media_mix'] == 100
        assert engine.device_status['chat_mix'] == 50
        
        # usb_device.write/ctrl_transfer should NOT have been called (no hardware sync)
        engine.usb_device.write.assert_not_called()
        engine.usb_device.ctrl_transfer.assert_not_called()
        
        # 2. Test handle_hw_mix_change (initialization of baseline)
        engine.handle_hw_mix_change(100, 100)
        
        # Baseline should be set
        assert engine._last_hw_media_mix == 100
        assert engine._last_hw_chat_mix == 100
        
        # Since it was baseline initialization, it should NOT override the software mix (which was set to 100/50)
        assert engine.media_mix == 100
        assert engine.chat_mix == 50
        assert engine.device_status['media_mix'] == 100
        assert engine.device_status['chat_mix'] == 50
        
        # 3. Test that minor changes (jitter/periodic reports below threshold of 3) DO NOT override software mix
        # e.g., minor fluctuation from 100 to 98 (diff of 2)
        engine.handle_hw_mix_change(100, 98)
        
        # Should be ignored (baseline remains 100, software mix remains 100/50)
        assert engine._last_hw_chat_mix == 100
        assert engine.media_mix == 100
        assert engine.chat_mix == 50
        assert engine.device_status['chat_mix'] == 50
        
        # 4. Test that actual physical rotation (change >= 3) DOES update software mix
        # e.g., turning dial from 100 to 90 (diff of 10)
        engine.handle_hw_mix_change(100, 90)
        
        # Baseline should update to 90
        assert engine._last_hw_media_mix == 100
        assert engine._last_hw_chat_mix == 90
        
        # Software mix should update to match
        assert engine.media_mix == 100
        assert engine.chat_mix == 90
        assert engine.device_status['media_mix'] == 100
        assert engine.device_status['chat_mix'] == 90
