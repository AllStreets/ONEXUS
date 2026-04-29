"""
Nexus CLI — entry point for the nexus command.
Commands: run, status, forget, allow, deny, install, uninstall,
         community list, community search, create module, create agent, validate
"""
import asyncio
import os
from pathlib import Path
import click
from nexus import __version__
from nexus.config import NexusConfig


@click.group()
@click.version_option(__version__, prog_name="nexus")
def main():
    """NEXUS — Autonomous Intelligence Operating System"""
    pass


@main.command()
def status():
    """Show Nexus system status."""
    cfg = NexusConfig()
    db_exists = os.path.exists(cfg.db_path)
    click.echo(f"Nexus v{__version__}")
    click.echo(f"Data directory: {cfg.data_dir}")
    click.echo(f"Database: {'exists' if db_exists else 'not initialized'}")
    click.echo(f"Model: {cfg.model_name}")
    click.echo(f"LLM port: {cfg.llm_port}")


@main.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def forget(yes):
    """Erase all Nexus memory (GDPR Article 17 — right to erasure)."""
    cfg = NexusConfig()
    if not yes:
        click.confirm("This will permanently delete all Nexus data. Continue?", abort=True)
    if os.path.exists(cfg.db_path):
        os.remove(cfg.db_path)
        click.echo("All Nexus memory erased.")
    else:
        click.echo("No data to erase.")


@main.command()
@click.argument("module_name")
def allow(module_name):
    """Allow a module to operate."""
    from nexus.kernel.aegis import Aegis
    cfg = NexusConfig()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()
    aegis.set_policy(module_name, allowed=True)
    click.echo(f"Module '{module_name}' is now allowed.")


@main.command()
@click.argument("module_name")
def deny(module_name):
    """Deny a module from operating."""
    from nexus.kernel.aegis import Aegis
    cfg = NexusConfig()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()
    aegis.set_policy(module_name, allowed=False)
    click.echo(f"Module '{module_name}' is now denied.")


@main.command()
@click.argument("module_path")
def install(module_path):
    """Install a community module (format: author/module_name)."""
    from nexus.community.installer import ModuleInstaller
    cfg = NexusConfig()
    community_root = Path(__file__).parent.parent / "community"
    install_dir = cfg.data_dir / "community_modules"
    install_dir.mkdir(parents=True, exist_ok=True)

    installer = ModuleInstaller(community_root=community_root, install_dir=install_dir)
    result = installer.install(module_path)

    if result.success:
        click.echo(f"Installed '{module_path}'")
        if result.keywords:
            click.echo(f"Keywords registered: {', '.join(result.keywords)}")
    else:
        click.echo(f"Error: {result.error}")


@main.command()
@click.argument("module_name")
def uninstall(module_name):
    """Uninstall a community module."""
    from nexus.community.installer import ModuleInstaller
    cfg = NexusConfig()
    community_root = Path(__file__).parent.parent / "community"
    install_dir = cfg.data_dir / "community_modules"

    installer = ModuleInstaller(community_root=community_root, install_dir=install_dir)
    result = installer.uninstall(module_name)

    if result.success:
        click.echo(f"Uninstalled '{module_name}'")
    else:
        click.echo(f"Error: {result.error}")


@main.group()
def community():
    """Community module management and marketplace."""
    pass


def _get_marketplace():
    """Create a Marketplace instance for CLI commands."""
    from nexus.community.marketplace import Marketplace
    registry_path = Path(__file__).parent.parent / "community" / "registry.json"
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return Marketplace(registry_path, data_dir)


def _render_stars(rating: float) -> str:
    """Render a rating as a 5-character star string like '****-'."""
    filled = int(round(rating))
    return "*" * filled + "-" * (5 - filled)


CATEGORY_LABELS = {
    "code": "Code & Development",
    "data": "Data & Analytics",
    "business": "Business & Finance",
    "content": "Content & Knowledge",
    "infrastructure": "Infrastructure & Ops",
}


@community.command("list")
def community_list():
    """List available community modules."""
    from nexus.community.registry import ModuleRegistry
    registry_path = Path(__file__).parent.parent / "community" / "registry.json"
    reg = ModuleRegistry(registry_path)
    modules = reg.list_all()

    if not modules:
        click.echo("No community modules available.")
        return

    for mod in modules:
        click.echo(f"  {mod['author']}/{mod['name']} v{mod['version']} -- {mod['description']}")


@community.command("search")
@click.argument("query")
def community_search(query):
    """Search community modules by name, keyword, or description."""
    from nexus.community.registry import ModuleRegistry
    registry_path = Path(__file__).parent.parent / "community" / "registry.json"
    reg = ModuleRegistry(registry_path)
    results = reg.search(query)

    if not results:
        click.echo(f"No modules matching '{query}'.")
        return

    for mod in results:
        click.echo(f"  {mod['author']}/{mod['name']} v{mod['version']} -- {mod['description']}")


@community.command("browse")
@click.option("--category", "-c", type=click.Choice(["code", "data", "business", "content", "infrastructure"], case_sensitive=False), default=None, help="Filter by category")
@click.option("--sort", "-s", type=click.Choice(["downloads", "rating", "newest", "trust"], case_sensitive=False), default="downloads", help="Sort order")
@click.option("--type", "type_filter", type=click.Choice(["module", "agent"], case_sensitive=False), default=None, help="Filter by type")
def community_browse(category, sort, type_filter):
    """Browse the marketplace with filtering and sorting."""
    mp = _get_marketplace()
    entries = mp.browse(category=category, sort=sort, type_filter=type_filter)

    if not entries:
        click.echo("No packages found.")
        return

    # Group by category for display
    if category:
        label = CATEGORY_LABELS.get(category, category.title())
        click.echo(f"  {label}")
        click.echo(f"  {'─' * len(label)}")
        for e in entries:
            stars = _render_stars(e.rating)
            rt = f"({e.rating:.1f})" if e.rating > 0 else "(--.-)"
            click.echo(f"  {e.author}/{e.name} v{e.version:<12} [{e.type}] {stars} {rt}  {e.downloads:>3} downloads")
            click.echo(f"    {e.description}")
    else:
        for e in entries:
            stars = _render_stars(e.rating)
            rt = f"({e.rating:.1f})" if e.rating > 0 else "(--.-)"
            click.echo(f"  {e.author}/{e.name} v{e.version:<12} [{e.type}] {stars} {rt}  {e.downloads:>3} downloads")
            click.echo(f"    {e.description}")


@community.command("info")
@click.argument("name")
def community_info(name):
    """Show detailed information about a package."""
    mp = _get_marketplace()
    entry = mp.get_details(name)

    if entry is None:
        click.echo(f"Package '{name}' not found.")
        return

    cat_label = CATEGORY_LABELS.get(entry.category, entry.category.title())
    click.echo(f"  {entry.name.title()} v{entry.version}")
    click.echo(f"  by {entry.author} | {entry.type} | {cat_label}")
    click.echo("")
    click.echo(f"  {entry.description}")
    click.echo("")

    stars = _render_stars(entry.rating)
    if entry.rating_count > 0:
        click.echo(f"  Rating: {stars} ({entry.rating:.1f} from {entry.rating_count} reviews)")
    else:
        click.echo(f"  Rating: ----- (no reviews yet)")
    click.echo(f"  Downloads: {entry.downloads}")
    if entry.trust_score is not None:
        click.echo(f"  Trust Score: {entry.trust_score}")
    click.echo(f"  License: {entry.license}")

    if entry.watch_events:
        click.echo("")
        click.echo(f"  Watch Events: {', '.join(entry.watch_events)}")
    if entry.coordination_targets:
        click.echo(f"  Coordinates With: {', '.join(entry.coordination_targets)}")

    if entry.keywords:
        click.echo("")
        click.echo(f"  Keywords: {', '.join(entry.keywords)}")

    badges = mp.reputation.get_badges(entry)
    if badges:
        click.echo(f"  Badges: {', '.join(badges)}")


@community.command("rate")
@click.argument("name")
@click.argument("score", type=int)
@click.option("--review", "-r", default="", help="Optional review text")
def community_rate(name, score, review):
    """Rate a package (1-5 stars)."""
    mp = _get_marketplace()
    try:
        mp.rate(name, score, review)
        click.echo(f"Rated '{name}' with {score} stars.")
    except ValueError as e:
        click.echo(f"Error: {e}")


@community.command("stats")
def community_stats():
    """Show marketplace statistics."""
    mp = _get_marketplace()
    stats = mp.get_stats()

    click.echo("  Marketplace Statistics")
    click.echo("  ─────────────────────")
    click.echo(f"  Total packages:  {stats.total_packages}")
    click.echo(f"  Modules:         {stats.total_modules}")
    click.echo(f"  Agents:          {stats.total_agents}")
    click.echo(f"  Total downloads: {stats.total_downloads}")
    click.echo(f"  Authors:         {stats.total_authors}")
    click.echo("")
    click.echo("  Categories:")
    for cat, count in sorted(stats.categories.items()):
        label = CATEGORY_LABELS.get(cat, cat.title())
        click.echo(f"    {label}: {count}")


@main.group()
def create():
    """Scaffold a new community module or agent."""
    pass


@create.command("module")
@click.argument("name")
def create_module(name):
    """Scaffold a new community module.

    NAME is the module name (lowercase, underscores allowed).
    """
    from nexus.sdk.module_template import generate_module

    author = click.prompt("Author (GitHub username)")
    description = click.prompt("Description")
    keywords_raw = click.prompt("Keywords (comma-separated)")
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    files = generate_module(
        name=name,
        description=description,
        author=author,
        keywords=keywords,
    )

    base_dir = Path(__file__).parent.parent / "community" / "modules" / author / name
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "tests").mkdir(parents=True, exist_ok=True)

    for filepath, content in files.items():
        full_path = base_dir / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    click.echo("")
    click.echo(f"Created module '{name}' at community/modules/{author}/{name}/")
    for filepath in sorted(files.keys()):
        pad = " " * (20 - len(filepath))
        if filepath == "module.py":
            click.echo(f"  {filepath}{pad}- NexusModule subclass")
        elif filepath == "manifest.json":
            click.echo(f"  {filepath}{pad}- Module metadata")
        elif filepath.startswith("tests/"):
            test_count = content.count("def test_") if filepath == list(files.keys())[-1] else 4
            click.echo(f"  {filepath}{pad}- {test_count} test stubs")
        elif filepath == "README.md":
            click.echo(f"  {filepath}{pad}- Usage documentation")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Implement handle() in module.py")
    click.echo(f"  2. Run tests: pytest community/modules/{author}/{name}/tests/ -v")
    click.echo("  3. Submit: git add . && git commit && open a PR")


@create.command("agent")
@click.argument("name")
def create_agent(name):
    """Scaffold a new community agent.

    NAME is the agent name (lowercase, underscores allowed).
    """
    from nexus.sdk.agent_template import generate_agent

    author = click.prompt("Author (GitHub username)")
    description = click.prompt("Description")
    keywords_raw = click.prompt("Keywords (comma-separated)")
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    watch_raw = click.prompt("Watch events (comma-separated, optional)", default="", show_default=False)
    watch_events = [e.strip() for e in watch_raw.split(",") if e.strip()] if watch_raw else []

    coord_raw = click.prompt("Coordination targets (comma-separated, optional)", default="", show_default=False)
    coordination_targets = [t.strip() for t in coord_raw.split(",") if t.strip()] if coord_raw else []

    files = generate_agent(
        name=name,
        description=description,
        author=author,
        keywords=keywords,
        watch_events=watch_events,
        coordination_targets=coordination_targets,
    )

    base_dir = Path(__file__).parent.parent / "community" / "agents" / author / name
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "tests").mkdir(parents=True, exist_ok=True)

    for filepath, content in files.items():
        full_path = base_dir / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    click.echo("")
    click.echo(f"Created agent '{name}' at community/agents/{author}/{name}/")
    for filepath in sorted(files.keys()):
        pad = " " * (20 - len(filepath))
        if filepath == "agent.py":
            click.echo(f"  {filepath}{pad}- AgentModule subclass with 4 tier methods")
        elif filepath == "manifest.json":
            click.echo(f"  {filepath}{pad}- Agent metadata")
        elif filepath.startswith("tests/"):
            click.echo(f"  {filepath}{pad}- 6 test stubs")
        elif filepath == "README.md":
            click.echo(f"  {filepath}{pad}- Usage documentation with trust tiers")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Implement analyze() in agent.py (must work without LLM)")
    click.echo("  2. Implement suggest(), monitor(), coordinate()")
    click.echo(f"  3. Run tests: pytest community/agents/{author}/{name}/tests/ -v")
    click.echo("  4. Submit: git add . && git commit && open a PR")


@main.command("validate")
@click.argument("path")
def validate_package(path):
    """Validate a community module or agent package."""
    from nexus.sdk.validator import PackageValidator

    validator = PackageValidator()

    # Determine type from manifest if it exists
    manifest_path = os.path.join(path, "manifest.json")
    pkg_type = "module"
    if os.path.isfile(manifest_path):
        import json
        try:
            with open(manifest_path) as f:
                data = json.load(f)
            if data.get("type") == "agent":
                pkg_type = "agent"
        except Exception:
            pass

    click.echo(f"Validating {pkg_type} package...")

    result = validator.validate(path)

    # Report individual checks
    checks = [
        ("manifest.json", validator.check_manifest(path)),
        ("code structure", validator.check_code(path)),
        ("tests", validator.check_tests(path)),
        ("README.md", validator.check_readme(path)),
    ]

    for label, errors in checks:
        if errors:
            for err in errors:
                click.echo(f"  [FAIL] {err}")
        else:
            click.echo(f"  [OK] {label} is valid")

    click.echo("")
    if result.valid:
        click.echo("Package is valid and ready for submission.")
    else:
        click.echo(f"Package has {len(result.errors)} error(s). Fix them before submitting.")
        raise SystemExit(1)


@main.command()
def run():
    """Start the Nexus interactive session."""
    cfg = NexusConfig()

    from nexus.kernel.engram import Engram
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.aegis import Aegis
    from nexus.kernel.pulse import Pulse
    from nexus.kernel.cortex import Cortex
    from nexus.modules.general import GeneralModule
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

    general = GeneralModule()
    cortex.register_module(general)
    aegis.set_policy("general", allowed=True)

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
            click.echo("Local LLM not detected — running in offline mode.")
            click.echo(f"Start llama.cpp on port {cfg.llm_port} for local inference.")
        else:
            click.echo(f"Using {cfg.default_provider} as default provider.")

    async def _llm_handler(msg):
        return await llm_client.chat(
            system="You are Nexus, an autonomous intelligence operating system. Be helpful, precise, and concise.",
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
    click.echo("NEXUS v" + __version__)
    click.echo("Type a message. Ctrl+C to exit.")
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
    """Start the Nexus interactive TUI (rich terminal dashboard)."""
    from nexus.tui.app import launch_tui
    cfg = NexusConfig()
    launch_tui(cfg)


@main.command()
@click.option("--suite", type=click.Choice(["security", "code", "data", "all"], case_sensitive=False), default="all", help="Suite to run (default: all)")
@click.option("--format", "fmt", type=click.Choice(["terminal", "markdown", "json"], case_sensitive=False), default="terminal", help="Output format")
@click.option("--output", "output_file", type=click.Path(), default=None, help="Write report to file")
def benchmark(suite, fmt, output_file):
    """Run benchmark suites against NEXUS agents."""
    from nexus.benchmarks.runner import BenchmarkRunner
    from nexus.benchmarks.report import ReportGenerator

    suites_to_run = []

    if suite in ("security", "all"):
        from nexus.benchmarks.suites.security import SECURITY_SUITE
        suites_to_run.append(SECURITY_SUITE)
    if suite in ("code", "all"):
        from nexus.benchmarks.suites.code import CODE_SUITE
        suites_to_run.append(CODE_SUITE)
    if suite in ("data", "all"):
        from nexus.benchmarks.suites.data import DATA_SUITE
        suites_to_run.append(DATA_SUITE)

    runner = BenchmarkRunner()
    reporter = ReportGenerator()
    all_results = []

    async def _run():
        for s in suites_to_run:
            result = await runner.run_suite(s)
            all_results.append(result)

    asyncio.run(_run())

    # Generate output
    parts = []
    for result in all_results:
        if fmt == "terminal":
            parts.append(reporter.to_terminal(result))
        elif fmt == "markdown":
            parts.append(reporter.to_markdown(result))
        elif fmt == "json":
            parts.append(reporter.to_json(result))
        parts.append("")

    if fmt == "terminal" and len(all_results) > 1:
        parts.append(reporter.to_summary(all_results))

    report = "\n".join(parts)

    if output_file:
        with open(output_file, "w") as f:
            f.write(report)
        click.echo(f"Report written to {output_file}")
    else:
        click.echo(report)


if __name__ == "__main__":
    main()
