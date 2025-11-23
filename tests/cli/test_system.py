from click.testing import CliRunner
from hiveden.cli import main

def test_system_help():
    runner = CliRunner()
    result = runner.invoke(main, ['system', '--help'])
    assert result.exit_code == 0
    assert "System commands" in result.output
