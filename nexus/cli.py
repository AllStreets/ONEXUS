"""
ONEXUS CLI -- entry point for the onexus command.
Commands: run, serve, tui, dashboard, status, forget, allow, deny, revoke,
          trust, workflow, replay, federation, mcp
"""
import asyncio
import os
from pathlib import Path
import click
from nexus import __version__
from nexus.config import NexusConfig


@click.group()
@click.version_option(__version__, prog_name="onexus")
def main():
    """ONEXUS -- Open-Source Neural Executive for Unified Superintelligence"""
    pass


@main.command()
def status():
    """Show ONEXUS system status."""
    from nexus.kernel.aegis import Aegis, TrustTier
    cfg = NexusConfig()
    db_exists = os.path.exists(cfg.db_path)
    click.echo(f"ONEXUS v{__version__}")
    click.echo(f"Data directory: {cfg.data_dir}")
    click.echo(f"Database: {'exists' if db_exists else 'not initialized'}")
    click.echo(f"Model: {cfg.model_name}")
    click.echo(f"LLM port: {cfg.llm_port}")

    if db_exists:
        aegis = Aegis(str(cfg.db_path))
        aegis.init_db()
        click.echo("")
        click.echo("Modules:")
        for mod in ["council", "specter", "autonomic", "oracle", "wraith",
                     "legacy", "consciousness", "sentry", "echo"]:
            trust = aegis.get_trust(mod)
            tier = TrustTier.from_score(trust)
            click.echo(f"  {mod:<16} trust: {trust:.2f}  [{tier}]")


@main.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def forget(yes):
    """Erase all ONEXUS memory (GDPR Article 17 -- right to erasure)."""
    cfg = NexusConfig()
    if not yes:
        click.confirm("This will permanently delete all ONEXUS data. Continue?", abort=True)
    if os.path.exists(cfg.db_path):
        os.remove(cfg.db_path)
        click.echo("All ONEXUS memory erased.")
    else:
        click.echo("No data to erase.")


@main.command()
@click.argument("module_name")
def allow(module_name):
    """Allow a module to operate."""
    from nexus.kernel.aegis import Aegis
    cfg = NexusConfig()
    aegis = Aegis(str(cfg.db_path))
    aegis.init_db()
    aegis.set_policy(module_name, allowed=True)
    click.echo(f"Module '{module_name}' is now allowed.")


@main.command()
@click.argument("module_name")
def deny(module_name):
    """Deny a module from operating."""
    from nexus.kernel.aegis import Aegis
    cfg = NexusConfig()
    aegis = Aegis(str(cfg.db_path))
    aegis.init_db()
    aegis.set_policy(module_name, allowed=False)
    click.echo(f"Module '{module_name}' is now denied.")


@main.command()
@click.argument("module_name")
def revoke(module_name):
    """Revoke a module's trust (set to 0.0 immediately)."""
    from nexus.kernel.aegis import Aegis
    cfg = NexusConfig()
    aegis = Aegis(str(cfg.db_path))
    aegis.init_db()
    aegis.revoke(module_name)
    click.echo(f"Module '{module_name}' trust revoked to 0.0.")


@main.command()
@click.argument("module_name")
def trust(module_name):
    """Show trust history for a module."""
    from nexus.kernel.aegis import Aegis, TrustTier
    cfg = NexusConfig()
    aegis = Aegis(str(cfg.db_path))
    aegis.init_db()

    score = aegis.get_trust(module_name)
    tier = TrustTier.from_score(score)
    click.echo(f"  {module_name}: {score:.2f} [{tier}]")

    history = aegis.get_trust_history(module_name)
    if history:
        click.echo(f"  Last {min(len(history), 20)} changes:")
        for entry in history[-20:]:
            delta = entry.get("delta", 0)
            sign = "+" if delta >= 0 else ""
            click.echo(f"    {entry.get('timestamp', '?')[:19]}  {sign}{delta:.2f}  -> {entry.get('new_score', 0):.2f}  {entry.get('reason', '')}")
    else:
        click.echo("  No trust history.")


@main.command()
def run():
    """Start the ONEXUS interactive session."""
    cfg = NexusConfig()

    from nexus.kernel.engram import Engram
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.aegis import Aegis
    from nexus.kernel.pulse import Pulse
    from nexus.kernel.cortex import Cortex
    from nexus.inference.llm import LLMClient
    from nexus.inference.router import ProviderRouter
    from nexus.inference.local import LocalProvider

    engram = Engram(cfg.db_path)
    engram.init_db()
    chronicle = Chronicle(cfg.db_path)
    chronicle.init_db()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
        config=cfg,
    )
    cortex.register_builtin_manifests()

    # Register cognitive modules
    from nexus.modules.council import CouncilModule
    from nexus.modules.specter import SpecterModule
    from nexus.modules.autonomic import AutonomicModule
    from nexus.modules.oracle import OracleModule
    from nexus.modules.wraith import WraithModule
    from nexus.modules.legacy import LegacyModule
    from nexus.modules.consciousness import ConsciousnessModule
    from nexus.modules.sentry import SentryModule
    from nexus.modules.echo import EchoModule

    for ModuleClass in [CouncilModule, SpecterModule, AutonomicModule,
                        OracleModule, WraithModule, LegacyModule,
                        ConsciousnessModule, SentryModule, EchoModule]:
        module = ModuleClass()
        cortex.register_module(module)
        aegis.set_policy(module.name, allowed=True)

    # Build the provider router
    router = ProviderRouter(default=cfg.default_provider)

    # Always register local provider
    local = LocalProvider(base_url=f"http://localhost:{cfg.llm_port}")
    router.register(local)

    # Register cloud providers if API keys are configured
    if cfg.openai_api_key:
        from nexus.inference.openai_provider import OpenAIProvider
        router.register(OpenAIProvider(api_key=cfg.openai_api_key, model=cfg.openai_model))
        click.echo(f"OpenAI provider registered (model: {cfg.openai_model})")

    if cfg.anthropic_api_key:
        from nexus.inference.anthropic_provider import AnthropicProvider
        router.register(AnthropicProvider(api_key=cfg.anthropic_api_key, model=cfg.anthropic_model))
        click.echo(f"Anthropic provider registered (model: {cfg.anthropic_model})")

    llm_client = LLMClient(router=router)

    if asyncio.run(local.health()):
        click.echo(f"Local LLM connected at localhost:{cfg.llm_port}")
    else:
        if cfg.default_provider == "local":
            click.echo("Local LLM not detected -- running in offline mode.")
            click.echo(f"Start llama.cpp on port {cfg.llm_port} for local inference.")
        else:
            click.echo(f"Using {cfg.default_provider} as default provider.")

    async def _llm_handler(msg):
        return await llm_client.chat(
            system="You are ONEXUS, an autonomous intelligence operating system. Be helpful, precise, and concise.",
            user=msg,
        )

    cortex.set_llm(_llm_handler)

    # Start messaging bridges if configured
    from nexus.messaging.manager import BridgeManager
    bridge_manager = BridgeManager(pulse=pulse, cortex_process=cortex.process)

    if cfg.telegram_token and cfg.telegram_chat_ids:
        from nexus.messaging.telegram import TelegramBridge
        tg_bridge = TelegramBridge(token=cfg.telegram_token, allowed_chat_ids=cfg.telegram_chat_ids)
        bridge_manager.register(tg_bridge)
        click.echo(f"Telegram bridge registered ({len(cfg.telegram_chat_ids)} allowed chats)")

    if cfg.discord_token and cfg.discord_channel_ids:
        from nexus.messaging.discord_bridge import DiscordBridge
        dc_bridge = DiscordBridge(token=cfg.discord_token, allowed_channel_ids=cfg.discord_channel_ids)
        bridge_manager.register(dc_bridge)
        click.echo(f"Discord bridge registered ({len(cfg.discord_channel_ids)} allowed channels)")

    click.echo("")
    click.echo("ONEXUS v" + __version__)
    click.echo("9 cognitive modules loaded. Type a message. Ctrl+C to exit.")
    click.echo("---")

    async def session():
        await bridge_manager.start()
        try:
            while True:
                try:
                    user_input = click.prompt("", prompt_suffix="> ")
                except (click.Abort, EOFError):
                    click.echo("\nSession ended.")
                    break
                if not user_input.strip():
                    continue
                response = await cortex.process(user_input)
                click.echo(response)
                click.echo("")
        finally:
            await bridge_manager.stop()

    asyncio.run(session())


@main.command()
def tui():
    """Start the ONEXUS interactive TUI (rich terminal dashboard)."""
    try:
        from nexus.tui.app import launch_tui
    except ImportError:
        click.echo("Error: rich library required. Install with: pip install 'onexus[tui]'")
        raise SystemExit(1)
    cfg = NexusConfig()
    launch_tui(cfg)


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8765, type=int, help="Port number")
def serve(host, port):
    """Start the REST/WebSocket API server."""
    try:
        import uvicorn
    except ImportError:
        click.echo("Error: uvicorn required. Install with: pip install 'onexus[api]'")
        raise SystemExit(1)
    click.echo(f"Starting ONEXUS API server on {host}:{port}")
    uvicorn.run("nexus.api.server:app", host=host, port=port, log_level="info")


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8765, type=int, help="API server port for dashboard connection")
def dashboard(host, port):
    """Launch the live web dashboard."""
    try:
        import uvicorn
    except ImportError:
        click.echo("Error: uvicorn required. Install with: pip install 'onexus[api]'")
        raise SystemExit(1)
    import webbrowser
    click.echo(f"Starting ONEXUS dashboard at http://{host}:{port}/dashboard")
    webbrowser.open(f"http://{host}:{port}/dashboard")
    uvicorn.run("nexus.api.server:app", host=host, port=port, log_level="info")


@main.group()
def briefing():
    """Daily kernel briefings — autonomous reports of where ONEXUS stands."""
    pass


@briefing.command("daily")
@click.option("--dry", is_flag=True, help="Print to stdout without writing the file")
def briefing_daily(dry):
    """Render today's kernel briefing and write it to reports/YYYY-MM-DD.md."""
    from nexus.briefings.daily import render_briefing, write_briefing
    if dry:
        click.echo(render_briefing(), nl=False)
        return
    path = write_briefing()
    click.echo(f"wrote {path}")


@main.group()
def workflow():
    """Manage and run workflow pipelines."""
    pass


@workflow.command("run")
@click.argument("name")
@click.option("--vars", "variables", multiple=True, help="Variable overrides (key=value)")
def workflow_run(name, variables):
    """Run a built-in or custom workflow by name."""
    from nexus.workflow.engine import WorkflowEngine
    from nexus.workflow.builtins import ALL_BUILTINS
    from nexus.kernel.engram import Engram
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.aegis import Aegis
    from nexus.kernel.pulse import Pulse
    from nexus.kernel.cortex import Cortex

    cfg = NexusConfig()
    engram = Engram(cfg.db_path)
    engram.init_db()
    chronicle = Chronicle(cfg.db_path)
    chronicle.init_db()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram=engram, chronicle=chronicle, aegis=aegis, pulse=pulse, config=cfg)
    cortex.register_builtin_manifests()

    engine = WorkflowEngine(cortex=cortex, chronicle=chronicle, pulse=pulse)

    wf = ALL_BUILTINS.get(name)
    if wf is None:
        click.echo(f"Unknown workflow '{name}'. Available: {', '.join(ALL_BUILTINS.keys())}")
        raise SystemExit(1)

    for v in variables:
        if "=" in v:
            key, val = v.split("=", 1)
            wf.variables[key] = val

    async def _run():
        result = await engine.execute(wf)
        for step in result.steps:
            status = "SKIP" if step.skipped else ("OK" if step.success else "FAIL")
            click.echo(f"  [{status}] {step.step_name} ({step.duration:.1f}s)")
            if step.error:
                click.echo(f"         {step.error}")
        click.echo("")
        click.echo(f"Workflow '{name}': {'SUCCESS' if result.success else 'FAILED'} ({result.total_duration:.1f}s)")

    asyncio.run(_run())


@workflow.command("list")
def workflow_list():
    """List available built-in workflows."""
    from nexus.workflow.builtins import ALL_BUILTINS
    for name, wf in ALL_BUILTINS.items():
        click.echo(f"  {name:<20} {wf.description}")


@main.group()
def replay():
    """Time-travel through system history."""
    pass


@replay.command("timeline")
@click.option("--limit", default=50, type=int, help="Maximum events to show")
def replay_timeline(limit):
    """Show Chronicle timeline of system events."""
    from nexus.replay.engine import ReplayEngine
    from nexus.replay.formatter import ReplayFormatter
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.aegis import Aegis

    cfg = NexusConfig()
    chronicle = Chronicle(cfg.db_path)
    chronicle.init_db()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()

    engine = ReplayEngine(chronicle=chronicle, aegis=aegis)
    formatter = ReplayFormatter()

    events = engine.get_timeline(limit=limit)
    click.echo(formatter.format_timeline(events))


@replay.command("snapshot")
@click.argument("timestamp")
def replay_snapshot(timestamp):
    """Reconstruct system state at a point in time (ISO format)."""
    from nexus.replay.engine import ReplayEngine
    from nexus.replay.formatter import ReplayFormatter
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.aegis import Aegis

    cfg = NexusConfig()
    chronicle = Chronicle(cfg.db_path)
    chronicle.init_db()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()

    engine = ReplayEngine(chronicle=chronicle, aegis=aegis)
    formatter = ReplayFormatter()

    snapshot = engine.get_snapshot(timestamp)
    click.echo(formatter.format_snapshot(snapshot))


@replay.command("diff")
@click.argument("ts_from")
@click.argument("ts_to")
def replay_diff(ts_from, ts_to):
    """Compare system state between two timestamps."""
    from nexus.replay.engine import ReplayEngine
    from nexus.replay.formatter import ReplayFormatter
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.aegis import Aegis

    cfg = NexusConfig()
    chronicle = Chronicle(cfg.db_path)
    chronicle.init_db()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()

    engine = ReplayEngine(chronicle=chronicle, aegis=aegis)
    formatter = ReplayFormatter()

    diff = engine.get_diff(ts_from, ts_to)
    click.echo(formatter.format_diff(diff))


@main.group()
def federation():
    """Peer-to-peer federation management."""
    pass


@federation.command("status")
def federation_status():
    """Show federation status and connected peers."""
    from nexus.federation.protocol import FederationProtocol
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.aegis import Aegis

    cfg = NexusConfig()
    chronicle = Chronicle(cfg.db_path)
    chronicle.init_db()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()

    proto = FederationProtocol(
        instance_id="local",
        chronicle=chronicle,
        aegis=aegis,
    )
    click.echo(f"  Federation: {'enabled' if proto.enabled else 'disabled'}")
    click.echo(f"  Instance ID: {proto.instance_id}")
    peers = proto.list_peers()
    if peers:
        click.echo(f"  Connected peers: {len(peers)}")
        for p in peers:
            click.echo(f"    {p.instance_id} @ {p.url} (trust: {p.trust_score})")
    else:
        click.echo("  Connected peers: 0")


@federation.command("enable")
def federation_enable():
    """Enable federation (peer-to-peer networking)."""
    click.echo("Federation enabled. Set ONEXUS_FEDERATION_ENABLED=1 to persist.")
    click.echo("Warning: this allows network connections. See docs for security model.")


@federation.command("discover")
@click.option("--subnet", default="192.168.1", help="Subnet to scan (first 3 octets)")
@click.option("--port", default=8600, type=int, help="Port to scan")
def federation_discover(subnet, port):
    """Discover ONEXUS peers on the local network."""
    from nexus.federation.discovery import PeerDiscovery

    discovery = PeerDiscovery(scan_port=port)
    click.echo(f"Scanning {subnet}.0/24 on port {port}...")

    async def _scan():
        peers = await discovery.discover_local(subnet=subnet)
        if peers:
            click.echo(f"Found {len(peers)} peer(s):")
            for p in peers:
                click.echo(f"  {p}")
        else:
            click.echo("No peers found.")

    asyncio.run(_scan())


@main.command()
def mcp():
    """Start the MCP (Model Context Protocol) server."""
    from nexus.mcp.server import create_server

    try:
        server = create_server()
    except RuntimeError as e:
        click.echo(f"Error: {e}")
        raise SystemExit(1)

    click.echo("Starting ONEXUS MCP server (stdio transport)...")
    asyncio.run(server.run_stdio())


@main.group()
def workspace():
    """Manage ONEXUS workspaces."""
    pass


def _workspace_root(cfg: NexusConfig):
    """Return (and create) the workspaces root directory."""
    from pathlib import Path
    root = cfg.data_dir / "workspaces"
    root.mkdir(parents=True, exist_ok=True)
    return root


@workspace.command("list")
def workspace_list():
    """List all workspaces."""
    from nexus.workspaces.manager import WorkspaceManager
    cfg = NexusConfig()
    mgr = WorkspaceManager(_workspace_root(cfg))
    workspaces = mgr.list()
    active_id = mgr.active_id()

    if not workspaces:
        click.echo("No workspaces yet. Create one with: onexus workspace create --name <name>")
        return

    for ws in workspaces:
        marker = " *" if ws.workspace_id == active_id else ""
        click.echo(f"  {ws.workspace_id:<30} {ws.tone.value:<10} {ws.name}{marker}")


@workspace.command("create")
@click.option("--name", required=True, help="Display name for the workspace.")
@click.option("--id", "workspace_id", default=None, help="Kebab-case ID (auto-generated if omitted).")
@click.option("--tone", default="INDIGO",
              type=click.Choice(["INDIGO", "MAGENTA", "SAGE", "PLUM", "AMBER"], case_sensitive=False),
              help="Home tone.")
@click.option("--template", default=None,
              type=click.Choice(["coding", "design", "research", "writing", "personal", "blank"],
                                case_sensitive=False),
              help="Start from a built-in template.")
def workspace_create(name, workspace_id, tone, template):
    """Create a new workspace."""
    import re
    from nexus.workspaces.manager import WorkspaceManager

    cfg = NexusConfig()
    mgr = WorkspaceManager(_workspace_root(cfg))

    # Auto-generate ID from name if not provided
    if workspace_id is None:
        workspace_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
        if not workspace_id:
            workspace_id = "workspace"

    if template:
        from nexus.workspaces.templates import apply_template
        try:
            ws = apply_template(
                template,
                workspace_id=workspace_id,
                name=name,
                manager=mgr,
                tone_override=tone.upper(),
            )
        except FileExistsError:
            click.echo(f"Error: workspace '{workspace_id}' already exists.")
            raise SystemExit(1)
        except KeyError as e:
            click.echo(f"Error: {e}")
            raise SystemExit(1)
    else:
        try:
            ws = mgr.create(name=name, workspace_id=workspace_id, tone=tone.upper())
        except FileExistsError:
            click.echo(f"Error: workspace '{workspace_id}' already exists.")
            raise SystemExit(1)

    click.echo(f"Created workspace '{workspace_id}' ({ws.tone.value}) — {ws.name}")


@workspace.command("switch")
@click.argument("workspace_id")
def workspace_switch(workspace_id):
    """Switch the active workspace."""
    from nexus.workspaces.manager import WorkspaceManager
    cfg = NexusConfig()
    mgr = WorkspaceManager(_workspace_root(cfg))
    try:
        mgr.set_active(workspace_id)
        ws = mgr.get(workspace_id)
        click.echo(f"Switched to workspace '{workspace_id}' — {ws.name} ({ws.tone.value})")
    except KeyError:
        click.echo(f"Error: workspace '{workspace_id}' not found.")
        raise SystemExit(1)


@workspace.command("destroy")
@click.argument("workspace_id")
@click.option("--yes", is_flag=True, help="Skip confirmation.")
def workspace_destroy(workspace_id, yes):
    """Permanently delete a workspace and all its data."""
    from nexus.workspaces.manager import WorkspaceManager
    cfg = NexusConfig()
    mgr = WorkspaceManager(_workspace_root(cfg))

    ws = mgr.get(workspace_id)
    if ws is None:
        click.echo(f"Error: workspace '{workspace_id}' not found.")
        raise SystemExit(1)

    if not yes:
        click.confirm(
            f"Permanently delete workspace '{workspace_id}' ({ws.name})? This cannot be undone.",
            abort=True,
        )

    try:
        mgr.destroy(workspace_id)
        click.echo(f"Workspace '{workspace_id}' destroyed.")
    except KeyError:
        click.echo(f"Error: workspace '{workspace_id}' not found.")
        raise SystemExit(1)


@main.group()
def agent():
    """Manage installed agents."""
    pass


@agent.command("install")
@click.argument("manifest_source")
@click.option("--dry-run", is_flag=True, help="Show the install plan without persisting.")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def agent_install(manifest_source, dry_run, yes):
    """Install a manifest from a local path or URL."""
    from pathlib import Path
    from nexus.agents.installer import plan_from_manifest_path, install_from_plan

    cfg = NexusConfig()
    src = Path(manifest_source)
    if not src.exists():
        click.echo(f"manifest not found: {manifest_source}", err=True)
        raise SystemExit(1)

    plan = plan_from_manifest_path(src)
    click.echo(plan.short_summary())
    if dry_run:
        click.echo("(dry run — nothing was installed)")
        return

    if not yes:
        if not click.confirm("install this agent?"):
            return
    target = install_from_plan(plan, cfg.data_dir)
    click.echo(f"installed: {plan.slug} -> {target}")


@agent.command("uninstall")
@click.argument("slug")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def agent_uninstall(slug, yes):
    """Remove an installed agent."""
    from nexus.agents.installer import uninstall as _uninstall

    if not yes:
        if not click.confirm(f"uninstall {slug!r}? this removes all its data."):
            return
    cfg = NexusConfig()
    if _uninstall(slug, cfg.data_dir):
        click.echo(f"uninstalled: {slug}")
    else:
        click.echo(f"not installed: {slug}", err=True)
        raise SystemExit(1)


@agent.command("list")
def agent_list():
    """List installed agents."""
    from nexus.agents.installer import installed_slugs, load_installed_manifest

    cfg = NexusConfig()
    slugs = installed_slugs(cfg.data_dir)
    if not slugs:
        click.echo("no installed agents")
        return
    for slug in slugs:
        m = load_installed_manifest(slug, cfg.data_dir)
        if m is not None:
            click.echo(f"  {slug:24}  v{m.version}  [{m.publisher.handle}]")


if __name__ == "__main__":
    main()
