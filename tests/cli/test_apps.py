from click.testing import CliRunner
from hiveden.cli import main
from unittest.mock import patch, MagicMock
import os
import json

def test_apps_help():
    runner = CliRunner()
    result = runner.invoke(main, ['apps', '--help'])
    assert result.exit_code == 0
    assert "Manage apps." in result.output

def test_pihole_help():
    runner = CliRunner()
    result = runner.invoke(main, ['apps', 'pihole', '--help'])
    assert result.exit_code == 0
    assert "Manage Pi-hole." in result.output

@patch('hiveden.cli.apps_cli.get_pihole_config')
@patch('hiveden.apps.pihole.PiHoleManager')
def test_pihole_dns_list(mock_manager_class, mock_get_config):
    # Mock config
    mock_get_config.return_value = ('http://pihole.local', 'password')
    
    # Mock manager instance
    mock_manager_instance = mock_manager_class.return_value
    mock_manager_instance.list_dns_entries.return_value = [{'domain': 'test.com', 'ip': '1.2.3.4'}]
    
    runner = CliRunner()
    # IMPORTANT: Since hiveden.cli.apps_cli imports PiHoleManager from hiveden.apps.pihole,
    # and hiveden.cli.apps_cli is imported by hiveden.cli.__init__, 
    # the class is already bound.
    # We should verify if patching hiveden.apps.pihole.PiHoleManager affects the bound one.
    # It usually does if apps_cli does "from hiveden.apps.pihole import PiHoleManager"
    # because patch mocks the name in the source module if we patch the source.
    # Wait, "from module import Name" binds Name to the object. Patching module.Name later 
    # changes module.Name, but not the already bound Name in the importer.
    # So we MUST patch `hiveden.cli.apps_cli.PiHoleManager`.
    
    pass 
    
@patch('hiveden.cli.apps_cli.get_pihole_config')
@patch('hiveden.cli.apps_cli.PiHoleManager')
def test_pihole_dns_list_correct(mock_manager_class, mock_get_config):
    mock_get_config.return_value = ('http://pihole.local', 'password')
    mock_manager_instance = mock_manager_class.return_value
    mock_manager_instance.list_dns_entries.return_value = [{'domain': 'test.com', 'ip': '1.2.3.4'}]
    
    runner = CliRunner()
    result = runner.invoke(main, ['apps', 'pihole', 'dns', 'list'])
    
    assert result.exit_code == 0
    assert "test.com -> 1.2.3.4" in result.output

@patch('hiveden.cli.apps_cli.get_pihole_config')
@patch('hiveden.cli.apps_cli.PiHoleManager')
def test_pihole_dns_add(mock_manager_class, mock_get_config):
    mock_get_config.return_value = ('http://pihole.local', 'password')
    
    runner = CliRunner()
    result = runner.invoke(main, ['apps', 'pihole', 'dns', 'add', 'test.com', '1.2.3.4'])
    
    assert result.exit_code == 0
    mock_manager_class.return_value.add_dns_entry.assert_called_with('test.com', '1.2.3.4')

@patch('hiveden.cli.apps_cli.get_pihole_config')
@patch('hiveden.cli.apps_cli.PiHoleManager')
def test_pihole_block_add(mock_manager_class, mock_get_config):
    mock_get_config.return_value = ('http://pihole.local', 'password')
    
    runner = CliRunner()
    result = runner.invoke(main, ['apps', 'pihole', 'block', 'add', 'bad.com'])
    
    assert result.exit_code == 0
    mock_manager_class.return_value.add_to_blacklist.assert_called_with('bad.com')
