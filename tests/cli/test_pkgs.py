from click.testing import CliRunner
from hiveden.cli import main

def test_pkgs_help():
    runner = CliRunner()
    result = runner.invoke(main, ['pkgs', '--help'])
    assert result.exit_code == 0
    assert "Package management commands" in result.output
