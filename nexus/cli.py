"""
Nexus CLI — entry point for the nexus command.
Commands: run, status, forget, allow, deny
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
    """Community module management."""
    pass


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
        click.echo(f"  {mod['author']}/{mod['name']} v{mod['version']} — {mod['description']}")


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
        click.echo(f"  {mod['author']}/{mod['name']} v{mod['version']} — {mod['description']}")


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

    if local.health():
        click.echo(f"Local LLM connected at localhost:{cfg.llm_port}")
    else:
        if cfg.default_provider == "local":
            click.echo("Local LLM not detected — running in offline mode.")
            click.echo(f"Start llama.cpp on port {cfg.llm_port} for local inference.")
        else:
            click.echo(f"Using {cfg.default_provider} as default provider.")

    cortex.set_llm(lambda msg: llm_client.chat(
        system="You are Nexus, an autonomous intelligence operating system. Be helpful, precise, and concise.",
        user=msg,
    ))

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


if __name__ == "__main__":
    main()
