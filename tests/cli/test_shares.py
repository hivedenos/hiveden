from click.testing import CliRunner
from hiveden.cli import main

def test_shares_help():
    runner = CliRunner()
    result = runner.invoke(main, ['shares', '--help'])
    assert result.exit_code == 0
    assert "Manage shares." in result.output

def test_zfs_help():
    runner = CliRunner()
    result = runner.invoke(main, ['shares', 'zfs', '--help'])
    assert result.exit_code == 0
    assert "Manage ZFS shares." in result.output

def test_samba_help():
    runner = CliRunner()
    result = runner.invoke(main, ['shares', 'samba', '--help'])
    assert result.exit_code == 0
    assert "Manage Samba shares." in result.output
