from click.testing import CliRunner
from hiveden.cli import main

def test_docker_help():
    runner = CliRunner()
    result = runner.invoke(main, ['docker', '--help'])
    assert result.exit_code == 0
    assert "Docker commands" in result.output
