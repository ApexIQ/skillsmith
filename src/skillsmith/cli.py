import click
from .commands import (
    console,
    init_command,
    align_command,
    sync_command,
    recommend_command,
    report_command,
    profile_command,
    discover_command,
    list_command,
    add_command,
    lint_command,
    compose_command,
    audit_command,
    doctor_command,
    eval_command,
    budget_command,
    update_command,
    rebuild_command,
    serve_command,
    snapshot_command,
    watch_command,
    context_index_command,
    registry_command,
    registry_service_command,
    trust_service_command,
)

@click.group()
def main():
    """Agentic Skills Library CLI"""
    pass

# Wire the modular commands
main.add_command(init_command, name="init")
main.add_command(align_command, name="align")
main.add_command(sync_command, name="sync")
main.add_command(recommend_command, name="recommend")
main.add_command(report_command, name="report")
main.add_command(profile_command, name="profile")
main.add_command(discover_command, name="discover")
main.add_command(list_command, name="list")
main.add_command(add_command, name="add")
main.add_command(lint_command, name="lint")
main.add_command(compose_command, name="compose")
main.add_command(audit_command, name="audit")
main.add_command(doctor_command, name="doctor")
main.add_command(eval_command, name="eval")
main.add_command(budget_command, name="budget")
main.add_command(update_command, name="update")
main.add_command(rebuild_command, name="rebuild")
main.add_command(serve_command, name="serve")
main.add_command(snapshot_command, name="snapshot")
main.add_command(watch_command, name="watch")
main.add_command(context_index_command, name="context-index")
main.add_command(context_index_command, name="context")
main.add_command(registry_command, name="registry")
main.add_command(registry_service_command, name="registry-service")
main.add_command(trust_service_command, name="trust-service")

if __name__ == "__main__":
    main()
