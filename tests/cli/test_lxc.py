from click.testing import CliRunner
from hiveden.cli import main

def test_lxc_help():
    runner = CliRunner()
    result = runner.invoke(main, ['lxc', '--help'])
    assert result.exit_code == 0
    assert "LXC container management commands" in result.output
