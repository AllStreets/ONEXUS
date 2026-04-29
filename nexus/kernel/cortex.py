"""
Cortex — the Nexus router and orchestrator.
Receives user input, selects the appropriate module, enforces permissions,
logs to Chronicle, and stores interactions in Engram.
"""
from typing import Any
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.kernel.pulse import Pulse, Message
from nexus.modules.base import NexusModule
from nexus.config import NexusConfig


class Cortex:
    # Module keyword hints for routing
    _MODULE_KEYWORDS: dict[str, list[str]] = {
        "oracle": ["trigger", "alert", "monitor", "scan", "anticipat", "pattern"],
        "sentry": ["cognitive", "focus", "fatigue", "stress", "flow", "state", "energy", "tired"],
        "atlas": ["fact", "know about", "world model", "knowledge", "who is", "what is"],
        "cipher": ["trust", "source", "provenance", "conflict", "verify", "credib"],
        "prism": ["synthesize", "connection", "cross-domain", "insight", "relate"],
        "wraith": ["phantom", "spawn", "agent", "swarm", "research task"],
        "echo": ["behavioral", "fingerprint", "style", "voice", "profile", "writing"],
        "herald": ["external agent", "a2a", "communicate", "connected agent"],
        "weave": ["contact", "network", "relationship", "social graph", "reconnect"],
        "sigil": ["threat", "danger", "security", "breach", "risk", "radar"],
        "specter": ["counter-argument", "devil's advocate", "risk analysis", "stress test this decision"],
        "serendipity": ["surprising", "unexpected", "serendip", "random", "adjacent", "diverse"],
        "forge": ["negotiat", "bargain", "offer", "counter-offer", "concession", "deal"],
        "collective": ["federated", "peer", "distributed", "swarm learning", "model sharing"],
        "legacy": ["crystallize", "distill", "framework", "playbook", "wisdom", "pattern extract"],
        "council": ["deliberate", "debate", "council", "perspectives", "weigh", "consider",
                     "should i", "decide", "pros and cons", "think through", "advise"],
        "autonomic": ["automate", "routine", "autopilot", "autonomous", "on my behalf",
                       "handle it", "take care of", "manage for me", "do it for me",
                       "autonomic", "trust status", "domain trust"],
        "dream_loop": ["dream", "dreams", "insights", "idle", "background", "patterns while idle"],
        "adversarial": ["stress test", "red team", "self improve", "vulnerability", "harden"],
        "tripwire": ["my patterns", "decision history", "contradictions", "tripwire", "mirror"],
        "provenance": ["why do you think", "reasoning", "show reasoning", "provenance", "trace", "how did you"],
        "sandbox": ["what if", "simulate", "hypothetical", "sandbox", "fork", "test scenario"],
        "symbiosis": ["neural pathways", "module connections", "routing map", "symbiosis"],
        "consciousness": ["how are you", "journal", "self reflect", "introspect", "consciousness",
                          "emergent goals", "unintended behavior", "what are you doing", "implicit goals"],
        "ethical_prism": ["ethically", "ethical", "moral", "ethics", "right thing", "should i morally"],
        "scribe": ["meeting", "transcript", "minutes", "action items", "summarize meeting", "notes"],
        "vex": ["vulnerability", "security scan", "owasp", "exploit", "code security", "sast"],
        "ledger": ["transaction", "bank statement", "spending", "budget", "categorize", "financial"],
        "arbiter": ["code review", "review this", "pull request", "diff", "review code", "pr review"],
        "thesis": ["paper", "literature", "academic", "research paper", "abstract", "citation"],
        "scaffold": ["scaffold", "boilerplate", "project template", "generate project", "new project", "starter"],
        "remedy": ["error", "traceback", "stack trace", "exception", "debug", "diagnose"],
        "compass": ["learn", "roadmap", "study plan", "curriculum", "learning path", "teach me"],
        "tally": ["projection", "runway", "forecast", "revenue model", "burn rate", "financial model"],
        "redline": ["contract", "legal", "agreement", "clause", "terms", "nda", "liability"],
        "carve": ["refactor", "complexity", "extract function", "code smell", "nesting", "simplify code"],
        "vigil": ["log analysis", "logs", "anomaly", "incident", "root cause", "log file", "timeline"],
        "mandate": ["compliance", "gdpr", "soc2", "hipaa", "audit", "regulatory", "gap analysis"],
        "flux": ["sql", "query", "database", "table schema", "select from", "natural language sql"],
        "kindle": ["expand", "blog post", "polish", "content", "write up", "draft", "outline to prose"],
    }

    def __init__(
        self,
        engram: Engram,
        chronicle: Chronicle,
        aegis: Aegis,
        pulse: Pulse,
        config: NexusConfig,
    ):
        self._engram = engram
        self._chronicle = chronicle
        self._aegis = aegis
        self._pulse = pulse
        self._config = config
        self._modules: dict[str, NexusModule] = {}
        self._llm = None

    def set_llm(self, llm_fn) -> None:
        """Set the LLM inference function used by modules."""
        self._llm = llm_fn

    def register_module(self, module: NexusModule) -> None:
        self._modules[module.name] = module

    async def unregister_module(self, name: str) -> None:
        module = self._modules.pop(name, None)
        if module:
            await module.on_unload(self._build_context())

    def _build_context(self) -> dict[str, Any]:
        return {
            "llm": self._llm,
            "engram": self._engram,
            "chronicle": self._chronicle,
            "pulse": self._pulse,
        }

    async def initialize_modules(self) -> None:
        """Call on_load for all registered modules with kernel context."""
        context = self._build_context()
        for module in self._modules.values():
            await module.on_load(context)

    def register_keywords(self, module_name: str, keywords: list[str]) -> None:
        """Register routing keywords for a module (used by community installer)."""
        self._MODULE_KEYWORDS[module_name] = keywords

    def unregister_keywords(self, module_name: str) -> None:
        """Remove routing keywords for a module."""
        self._MODULE_KEYWORDS.pop(module_name, None)

    def list_modules(self) -> list[str]:
        return list(self._modules.keys())

    def _select_module(self, message: str) -> str:
        """
        Select which module should handle this message.
        Uses keyword matching against registered modules, falls back to 'general'.
        """
        if not self._modules:
            return ""

        msg_lower = message.lower()
        best_module = ""
        best_score = 0

        for mod_name, keywords in self._MODULE_KEYWORDS.items():
            if mod_name not in self._modules:
                continue
            score = sum(1 for kw in keywords if kw in msg_lower)
            if score > best_score:
                best_score = score
                best_module = mod_name

        if best_module:
            return best_module

        # Fallback to general, or first available module
        if "general" in self._modules:
            return "general"
        return next(iter(self._modules))

    async def process(self, message: str) -> str:
        """Route a user message to the appropriate module and return the response."""
        target = self._select_module(message)

        if not target:
            return "[Nexus] No modules loaded."

        # Check permissions
        try:
            self._aegis.check(target, "handle")
        except PermissionDenied:
            self._chronicle.log("cortex", "permission_denied", {
                "module": target, "message_preview": message[:100],
            })
            return f"[Nexus] Module '{target}' is not allowed to respond. Enable it with: nexus allow {target}"

        # Check network permission for peer-aware modules
        module = self._modules[target]
        if module.requires_network and not self._aegis.is_network_allowed(target):
            self._chronicle.log("cortex", "network_denied", {
                "module": target, "message_preview": message[:100],
            })
            return (
                f"[Nexus] Module '{target}' requires network access but it is not enabled. "
                f"Grant it with: nexus allow --network {target}"
            )

        # Log the routing decision
        self._chronicle.log("cortex", "route", {
            "target": target, "message_preview": message[:100],
        })

        # Store the user message in episodic memory
        self._engram.episodic.store(f"User: {message}", source="user_input")

        # Build context for the module
        context = self._build_context()

        # Execute
        response = await module.handle(message, context)

        # Store the response in episodic memory
        self._engram.episodic.store(f"Nexus ({target}): {response}", source=f"module.{target}")

        # Log completion
        self._chronicle.log("cortex", "response", {
            "module": target, "response_preview": response[:200],
        })

        # Publish to Pulse for any listening modules
        await self._pulse.publish(Message(
            topic="cortex.response",
            source="cortex",
            payload={"module": target, "message": message, "response": response},
        ))

        return response
