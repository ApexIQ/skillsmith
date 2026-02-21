import click
from .commands import (
    console,
    init_command,
    list_command,
    add_command,
    lint_command,
    compose_command,
    doctor_command,
    budget_command,
    update_command,
    rebuild_command,
    serve_command,
    snapshot_command,
    watch_command
)

@click.group()
def main():
    """Agentic Skills Library CLI"""
    pass

# Wire the modular commands
main.add_command(init_command, name="init")
main.add_command(list_command, name="list")
main.add_command(add_command, name="add")
main.add_command(lint_command, name="lint")
main.add_command(compose_command, name="compose")
main.add_command(doctor_command, name="doctor")
main.add_command(budget_command, name="budget")
main.add_command(update_command, name="update")
main.add_command(rebuild_command, name="rebuild")
main.add_command(serve_command, name="serve")
main.add_command(snapshot_command, name="snapshot")
main.add_command(watch_command, name="watch")

if __name__ == "__main__":
    main()
