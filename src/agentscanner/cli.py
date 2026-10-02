"""Command-line interface for AgentScanner."""

import click
from pathlib import Path
from agentscanner.scanner import AgentScanner


@click.group()
@click.version_option()
def cli():
    """AgentScanner - Scan and analyze agents."""
    pass


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--format", "-f",
              type=click.Choice(["terminal", "json", "markdown", "sarif"]),
              default="terminal",
              help="Output format")
@click.option("--output", "-o",
              type=click.Path(),
              help="Output file path")
@click.option("--no-llm",
              is_flag=True,
              help="Skip semantic analysis (LLM checks)")
@click.option("--provider",
              type=click.Choice(["openai", "anthropic"]),
              help="LLM provider for semantic analysis")
def scan(path: str, format: str, output: str, no_llm: bool, provider: str):
    """Scan an agent or skill.

    Supports:
    - Local directories: agentscanner scan ./my-agent/
    - Single files: agentscanner scan ./SKILL.md
    - Git repositories: agentscanner scan https://github.com/user/my-agent
    - ZIP files: agentscanner scan ./my-agent.zip
    """
    click.echo(f"Scanning: {path}")

    scanner = AgentScanner(provider=provider if not no_llm else None)
    result = scanner.scan(path)

    output_text = scanner.get_results(format=format)

    if output:
        Path(output).write_text(output_text)
        click.echo(f"Report written to: {output}")
    else:
        click.echo(output_text)


@cli.command()
def version():
    """Show version information."""
    from agentscanner import __version__
    click.echo(f"AgentScanner v{__version__}")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
