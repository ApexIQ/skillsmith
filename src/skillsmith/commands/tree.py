from pathlib import Path
import json
import yaml

import click
from rich.tree import Tree
from . import console

@click.command(name="tree")
@click.argument("source", required=False, type=click.Path(exists=True))
@click.option("--trace", "trace_only", is_flag=True, help="Visualize the latest workflow trace only.")
@click.option("--output", "-o", type=click.Path(), help="Output the tree to a markdown file (e.g., .agent/TREE.md).")
def tree_command(source, trace_only, output):
    """Visualize the current agentic Thinking Tree (AND/OR Logic)."""
    cwd = Path.cwd()
    
    # Priority 1: Provided source file
    if source:
        source_path = Path(source)
    # Priority 2: Latest trace
    elif trace_only:
        trace_dir = cwd / ".agent" / "context" / "traces"
        if not trace_dir.exists():
            console.print("[red][ERROR][/red] No traces found in .agent/context/traces/.")
            return
        traces = sorted(trace_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not traces:
            console.print("[red][ERROR][/red] No workflow traces found.")
            return
        source_path = traces[0]
    # Priority 3: Default workflow_test.json or standard state
    else:
        candidates = [cwd / "workflow_test.json", cwd / "workflow.json", cwd / ".agent" / "STATE.md"]
        source_path = next((c for c in candidates if c.exists()), None)
        
    if not source_path:
        console.print("[yellow][WARN][/yellow] No Thinking Tree source found (workflow.json or .agent/STATE.md).")
        return

    console.print(f"[bold blue]Skillsmith Thinking Tree[/bold blue] ({source_path.relative_to(cwd) if source_path.is_relative_to(cwd) else source_path.name})")
    
    try:
        content = ""
        if source_path.suffix == ".json":
            tree, content = _render_json_tree(source_path)
            console.print(tree)
        elif source_path.suffix == ".md":
            tree, content = _render_markdown_state(source_path)
            console.print(tree)
        else:
            console.print(f"[red][ERROR][/red] Unsupported record type: {source_path.suffix}")
            return
            
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Add header to markdown
            md_output = f"# Thinking Tree: {source_path.name}\n\n" + content
            output_path.write_text(md_output, encoding="utf-8")
            console.print(f"\n[bold green]Tree Exported:[/bold green] {output}")
            
    except Exception as e:
        console.print(f"[red][ERROR][/red] Failed to render tree: {e}")

def _render_json_tree(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    
    # Extract workflow if it exists
    workflow = data.get("workflow", data)
    goal = workflow.get("goal", "Root Goal")
    
    root = Tree(f"[bold magenta]Goal:[/bold magenta] {goal}")
    md_content = f"## 🎯 Goal: {goal}\n\n"
    
    stages = workflow.get("stages", [])
    for i, stage in enumerate(stages):
        node_type = stage.get("node_type", "AND")
        name = stage.get("name", "Unnamed Stage")
        state = stage.get("state", "pending")
        
        # Color coding for states (Console)
        state_color = "yellow" if state == "pending" else "green" if state == "success" else "red"
        node_label = f"[[blue]{node_type}[/blue]] [bold]{name.upper()}[/bold] ([{state_color}]{state}[/])"
        
        branch = root.add(node_label)
        
        # Markdown label
        md_content += f"### {'✅' if state == 'success' else '⏳'} Stage {i+1}: {name.upper()} ({node_type})\n"
        
        # Add objectives
        for obj in stage.get("objectives", []):
            branch.add(f"[dim]○ {obj}[/dim]")
            md_content += f"- [ ] {obj}\n"
            
        # Add strategies if OR node
        if node_type == "OR" and "strategies" in stage:
            md_content += "\n#### 🔮 Recursive Strategies (OR Fallbacks)\n"
            for strat in stage["strategies"]:
                strat_name = strat.get("name", "Strategy")
                strat_node = strat.get("node_type", "AND")
                strat_branch = branch.add(f"[[cyan]Strategy[/cyan]] {strat_name} ({strat_node})")
                md_content += f"- **Strategy: {strat_name}** ({strat_node})\n"
                
                # Add recovery trigger if present
                if "recovery_trigger" in strat:
                    strat_branch.add(f"[italic red]Trigger: {strat['recovery_trigger']}[/italic red]")
                    md_content += f"  - *Trigger:* `{strat['recovery_trigger']}`\n"
        
        md_content += "\n"

    return root, md_content

def _render_markdown_state(path: Path):
    content = path.read_text(encoding="utf-8")
    # Simple visualization for STATE.md
    root = Tree("[bold green]Agent State (STATE.md)[/bold green]")
    md_content = f"## 📃 Agent State: {path.name}\n\n"
    
    lines = content.splitlines()
    parsing_next_steps = False
    
    steps_node = None
    for line in lines:
        if "## Next Steps" in line:
            parsing_next_steps = True
            steps_node = root.add("[bold cyan]Scheduled Tasks[/bold cyan]")
            md_content += "### 📋 Next Steps\n"
            continue
        
        if parsing_next_steps and (line.strip().startswith("1.") or line.strip().startswith("-")):
            clean_task = line.strip().lstrip("1. ").lstrip("- ")
            if steps_node:
                steps_node.add(clean_task)
            md_content += f"- [ ] {clean_task}\n"
        elif parsing_next_steps and line.strip().startswith("##"):
            parsing_next_steps = False
            
    return root, md_content
