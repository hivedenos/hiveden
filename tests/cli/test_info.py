from click.testing import CliRunner
from hiveden.cli import main

def test_info_help():
    runner = CliRunner()
    result = runner.invoke(main, ['info', '--help'])
    assert result.exit_code == 0
    assert "Get OS and hardware information." in result.output
