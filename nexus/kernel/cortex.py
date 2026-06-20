"""
Cortex -- the Nexus router and orchestrator.
Receives user input, classifies intent via semantic signals, routes to the
appropriate cognitive module, enforces trust/permissions through Aegis,
logs to Chronicle, and stores interactions in Engram.
"""
from __future__ import annotations

import os
import re
from collections import deque
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.kernel.pulse import Pulse, Message
from nexus.modules.base import NexusModule
from nexus.config import NexusConfig

# Lazy import — WorkspaceConfig lives in workspaces layer (above the kernel).
# We use TYPE_CHECKING + string annotation to avoid the circular import at
# module load time.  The actual object is only used at runtime inside methods.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from nexus.workspaces.config import WorkspaceConfig


# ---------------------------------------------------------------------------
# Intent classification primitives
# ---------------------------------------------------------------------------

@dataclass
class ScoredIntent:
    """A single intent match with its cumulative score."""
    name: str
    module: str
    score: float
    signals: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"ScoredIntent({self.name}, module={self.module}, score={self.score:.3f})"


@dataclass
class Intent:
    """Declarative definition of an intent category."""
    name: str
    module: str
    description: str
    patterns: list[re.Pattern]
    semantic_signals: list[str]


# Signal weights
_W_PATTERN = 0.40       # regex match -- strong
_W_SEMANTIC = 0.25      # phrase detection -- medium
_W_STRUCTURE = 0.10     # question/command/reflection -- weak
_W_CONTEXT = 0.15       # recent routing history bias -- weak
_W_LLM = 0.50           # LLM classification -- strong override

# Trust floor: modules below this score are skipped for implicit routing
_TRUST_FLOOR = 0.25

# Follow-up detection signals
_FOLLOWUP_TOKENS = re.compile(
    r"^(yes|no|sure|ok|okay|yeah|yep|nah|continue|go on|more|elaborate|explain"
    r"|why|how|what about|and|also|that|it|this|them|those|do it|go ahead|right)\b",
    re.IGNORECASE,
)

_SHORT_MESSAGE_THRESHOLD = 40  # chars -- short messages are likely follow-ups


def _compile(raw: list[str]) -> list[re.Pattern]:
    """Compile a list of raw regex strings into pattern objects."""
    return [re.compile(p, re.IGNORECASE) for p in raw]


# ---------------------------------------------------------------------------
# Canonical intent definitions (maps to the 9 cognitive modules)
# ---------------------------------------------------------------------------

_INTENT_DEFS: list[dict[str, Any]] = [
    {
        "name": "DELIBERATE",
        "module": "council",
        "description": "Multi-perspective deliberation: decisions, ethics, trade-offs, negotiations",
        "patterns": [
            r"\bshould\s+i\b", r"\bpros\s+and\s+cons\b", r"\bweigh\b", r"\btrade-?off\b",
            r"\bdeliberat\w*\b", r"\bnegotiat\w*\b", r"\bethic(al|s)?\b", r"\bmoral(ly)?\b",
            r"\bright\s+thing\b", r"\bdecide\b", r"\bdecision\b", r"\bcouncil\b",
            r"\bwhat\s+if\b.*\bvs\b", r"\badvise\b", r"\bsimulat\w*\b",
            r"\bperspective\b", r"\bdebate\b", r"\bconsider\b",
        ],
        "semantic_signals": [
            "should i", "pros and cons", "what if", "weigh options", "ethical question",
            "negotiate", "decision", "deliberate", "multiple perspectives", "trade-off",
            "think through", "advise me", "help me decide", "is it right to",
            "simulation", "synthesis", "verification", "lateral thinking",
        ],
    },
    {
        "name": "CHALLENGE",
        "module": "specter",
        "description": "Adversarial analysis, red-teaming, stress-testing ideas",
        "patterns": [
            r"\bstress\s+test\b", r"\bred\s+team\b", r"\bdevil'?s?\s+advocate\b",
            r"\bwhat\s+could\s+go\s+wrong\b", r"\brisk\s+analysis\b",
            r"\bcounter-?argument\b", r"\bchallenge\s+(this|that|my)\b",
            r"\bvulnerabilit\w*\b", r"\bharden\b", r"\bweakness\w*\b",
            r"\bpoke\s+holes?\b", r"\bspecter\b",
        ],
        "semantic_signals": [
            "stress test", "red team", "devil's advocate", "what could go wrong",
            "risk analysis", "counter-argument", "challenge this", "find flaws",
            "adversarial", "worst case", "attack surface", "poke holes",
        ],
    },
    {
        "name": "AUTOMATE",
        "module": "autonomic",
        "description": "Earned autonomy, routines, pattern learning, delegation",
        "patterns": [
            r"\bautomat\w*\b", r"\broutine\b", r"\bautopilot\b", r"\bautonomous\b",
            r"\bon\s+my\s+behalf\b", r"\bhandle\s+it\b", r"\btake\s+care\s+of\b",
            r"\bmanage\s+for\s+me\b", r"\bdo\s+it\s+for\s+me\b", r"\bautonomic\b",
            r"\btrust\s+status\b", r"\bdomain\s+trust\b", r"\bdelegat\w*\b",
        ],
        "semantic_signals": [
            "do this automatically", "handle it", "take care of", "automate",
            "routine", "on my behalf", "manage for me", "autonomous",
            "trust management", "delegate", "run on autopilot",
        ],
    },
    {
        "name": "ANTICIPATE",
        "module": "oracle",
        "description": "Anticipatory pattern detection, threat sensing, early warnings",
        "patterns": [
            r"\bpredict\w*\b", r"\banticipat\w*\b", r"\btrigger\b", r"\balert\b",
            r"\bmonitor\b", r"\bscan\b", r"\bpattern\s+(detect|scan)\w*\b",
            r"\bwatch\s+for\b", r"\bearly\s+warning\b", r"\bthreat\s+detect\w*\b",
            r"\boracle\b", r"\bforecast\b", r"\btrend\b",
        ],
        "semantic_signals": [
            "predict", "anticipate", "trigger", "alert", "monitor",
            "scan for patterns", "watch for", "early warning", "threat detection",
            "forecast", "trend analysis", "what's coming",
        ],
    },
    {
        "name": "SPAWN",
        "module": "wraith",
        "description": "Ephemeral sub-agent spawning, parallel tasks, background work",
        "patterns": [
            r"\bspawn\b", r"\bparallel\s+task\b", r"\bsimultaneous(ly)?\b",
            r"\bmulti-?task\b", r"\bbackground\s+(work|task|job)\b",
            r"\bresearch\s+\w+\s+and\s+\w+\b", r"\bwraith\b",
            r"\bsub-?agent\b", r"\bfork\b",
        ],
        "semantic_signals": [
            "spawn", "parallel tasks", "research X and Y simultaneously",
            "multi-task", "background work", "sub-agent", "fork off",
            "do both at once", "work on these in parallel",
        ],
    },
    {
        "name": "SUMMON",
        "module": "agents",
        "description": "Browse, search, and summon runnable agents from the ONEXUS-Agents catalog",
        "patterns": [
            r"\bsummon\b", r"\blaunch\s+agent\b", r"\bstart\s+agent\b",
            r"\bstop\s+agent\b", r"\bdismiss\s+agent\b", r"\bkill\s+agent\b",
            r"\binvoke\s+agent\b", r"\blist\s+agents?\b", r"\bagent\s+catalog\b",
            r"\brunning\s+agents?\b", r"\bonexus[- ]?agents?\b",
            r"\bsearch\s+agents?\b", r"\bfind\s+agent\b",
        ],
        "semantic_signals": [
            "summon", "launch agent", "start agent", "stop agent",
            "list agents", "running agents", "agent catalog",
            "find agent", "search agents", "invoke agent",
        ],
    },
    {
        "name": "CRYSTALLIZE",
        "module": "legacy",
        "description": "Knowledge crystallization, playbook extraction, heuristic distillation",
        "patterns": [
            r"\bcrystallize\b", r"\bdistill\b", r"\bplaybook\b", r"\bframework\b",
            r"\bheuristic\b", r"\bwhat\s+have\s+i\s+learned\b",
            r"\bpattern\s+extract\w*\b", r"\bwisdom\b", r"\blegacy\b",
            r"\blesson\w*\s+learned\b", r"\bknowledge\s+base\b",
        ],
        "semantic_signals": [
            "distill knowledge", "playbook", "what have I learned", "framework",
            "heuristics", "crystallize", "lessons learned", "codify knowledge",
            "extract patterns", "wisdom", "build a guide from experience",
        ],
    },
    {
        "name": "REFLECT",
        "module": "consciousness",
        "description": "Self-reflection, introspection, reasoning transparency, journaling",
        "patterns": [
            r"\bhow\s+are\s+you\b", r"\bjournal\b", r"\bself[- ]?reflect\w*\b",
            r"\bintrospect\w*\b", r"\bconsciousness\b", r"\breasoning\s+trace\b",
            r"\bcontradiction\b", r"\bdream\b", r"\bwhat\s+are\s+you\s+(doing|thinking)\b",
            r"\bimplicit\s+goals?\b", r"\bemergent\b", r"\bshow\s+reasoning\b",
            r"\bwhy\s+do\s+you\s+think\b", r"\bhow\s+did\s+you\b",
        ],
        "semantic_signals": [
            "journal", "self-reflection", "introspection", "how are you",
            "reasoning trace", "contradictions", "dreams", "consciousness",
            "emergent goals", "what are you doing", "implicit goals",
            "provenance", "show your reasoning", "how did you decide",
        ],
    },
    {
        "name": "REGULATE",
        "module": "sentry",
        "description": "Cognitive load monitoring, focus state, fatigue detection",
        "patterns": [
            r"\bcognitive\b", r"\bfocus\b", r"\bfatigue\b", r"\bstress\b",
            r"\bflow\s+state\b", r"\benergy\b", r"\btired\b",
            r"\bhow\s+am\s+i\s+doing\b", r"\bmental\s+state\b",
            r"\bsentry\b", r"\bworkload\b", r"\bburn-?out\b",
        ],
        "semantic_signals": [
            "cognitive state", "focus", "fatigue", "stress level",
            "flow state", "energy", "how am I doing", "mental state",
            "workload", "burnout", "am I overloaded",
        ],
    },
    {
        "name": "PROFILE",
        "module": "echo",
        "description": "Behavioral fingerprinting, user modeling, social graph",
        "patterns": [
            r"\bbehavioral\b", r"\bfingerprint\b", r"\bstyle\b.*\banalyz\w*\b",
            r"\bprofile\b", r"\bwriting\s+style\b", r"\bwho\s+is\b",
            r"\brelationship\b", r"\bsocial\s+graph\b", r"\bcontact\b",
            r"\buser\s+model\w*\b", r"\becho\b", r"\bpersonalit\w*\b",
        ],
        "semantic_signals": [
            "behavioral patterns", "fingerprint", "user profile", "writing style",
            "who is", "relationships", "social graph", "contacts",
            "user modeling", "personality", "how do I usually",
        ],
    },
]


class IntentClassifier:
    """
    Semantic intent classification engine.
    Uses layered scoring: regex patterns, semantic phrase matching,
    structural analysis, and routing context to rank intents.
    """

    def __init__(self, intents: list[Intent] | None = None) -> None:
        self._intents: list[Intent] = []
        self._routing_history: deque[str] = deque(maxlen=5)
        if intents is not None:
            self._intents = list(intents)
        else:
            # Phase 2: default to loading from the built-in registry.
            try:
                registry = default_builtin_registry()
                self._intents = self._intents_from_registry(registry)
            except Exception:
                # Fallback to the legacy hardcoded defs if registry boot fails
                # (e.g., when an existing test instantiates without all modules importable).
                self._load_intents_legacy()

    @classmethod
    def from_registry(cls, registry) -> "IntentClassifier":
        instance = cls.__new__(cls)
        instance._intents = instance._intents_from_registry(registry)
        instance._routing_history = deque(maxlen=5)
        return instance

    # ── intent construction ──────────────────────────────────────────────

    def _intents_from_registry(self, registry) -> list[Intent]:
        out: list[Intent] = []
        for manifest in registry.manifests():
            for intent_decl in manifest.intents:
                out.append(Intent(
                    name=intent_decl.name,
                    module=manifest.slug,
                    description=manifest.tagline,
                    patterns=_compile(intent_decl.patterns),
                    semantic_signals=list(intent_decl.semantic_signals),
                ))
        return out

    def _load_intents_legacy(self) -> None:
        """Fallback: build from the hardcoded `_INTENT_DEFS` (preserved during Phase 2)."""
        for defn in _INTENT_DEFS:
            self._intents.append(Intent(
                name=defn["name"],
                module=defn["module"],
                description=defn["description"],
                patterns=_compile(defn["patterns"]),
                semantic_signals=defn["semantic_signals"],
            ))

    # -- scoring layers ----------------------------------------------------

    def _score_patterns(self, message: str, intent: Intent) -> tuple[float, list[str]]:
        """Regex pattern matching -- strong signal."""
        hits: list[str] = []
        for pat in intent.patterns:
            if pat.search(message):
                hits.append(pat.pattern)
        if not hits:
            return 0.0, hits
        # Diminishing returns: first match counts full, extras add less
        score = min(1.0, 0.5 + 0.15 * len(hits))
        return score, hits

    def _score_semantic(self, message: str, intent: Intent) -> tuple[float, list[str]]:
        """Semantic phrase detection -- medium signal."""
        msg_lower = message.lower()
        hits: list[str] = []
        for phrase in intent.semantic_signals:
            if phrase.lower() in msg_lower:
                hits.append(phrase)
        if not hits:
            return 0.0, hits
        score = min(1.0, 0.4 + 0.12 * len(hits))
        return score, hits

    def _score_structure(self, message: str, intent: Intent) -> float:
        """
        Question structure analysis -- weak signal.
        Boosts certain intents based on whether the message is a question,
        a command, or a reflective statement.
        """
        msg_stripped = message.strip()
        is_question = msg_stripped.endswith("?")
        # Commands often start with a verb / imperative
        is_command = bool(re.match(
            r"^(do|run|start|stop|find|show|give|make|create|build|spawn|handle|set|check)\b",
            msg_stripped, re.IGNORECASE,
        ))
        is_reflective = bool(re.match(
            r"^(i feel|i think|i wonder|i notice|how am i|what have i)\b",
            msg_stripped, re.IGNORECASE,
        ))

        # Contextual nudges
        question_intents = {"DELIBERATE", "ANTICIPATE", "REFLECT", "REGULATE"}
        command_intents = {"AUTOMATE", "SPAWN", "CHALLENGE"}
        reflective_intents = {"REFLECT", "CRYSTALLIZE", "REGULATE", "PROFILE"}

        score = 0.0
        if is_question and intent.name in question_intents:
            score = 0.6
        elif is_command and intent.name in command_intents:
            score = 0.5
        elif is_reflective and intent.name in reflective_intents:
            score = 0.7
        return score

    def _score_context(self, intent: Intent) -> float:
        """Routing history bias -- weak signal for follow-up detection."""
        if not self._routing_history:
            return 0.0
        last_module = self._routing_history[-1]
        if intent.module == last_module:
            return 0.8
        # Check if module appeared recently (not just last)
        recent = list(self._routing_history)
        count = recent.count(intent.module)
        if count >= 2:
            return 0.4
        return 0.0

    def _is_followup(self, message: str) -> bool:
        """Detect likely follow-up messages (short or pronoun-heavy)."""
        if len(message.strip()) < _SHORT_MESSAGE_THRESHOLD:
            if _FOLLOWUP_TOKENS.search(message.strip()):
                return True
        return False

    # -- main classification -----------------------------------------------

    def classify(self, message: str) -> list[ScoredIntent]:
        """
        Classify a message into scored intents, best first.
        Returns all intents with score > 0, sorted descending.
        """
        is_followup = self._is_followup(message)
        results: list[ScoredIntent] = []

        for intent in self._intents:
            signals: list[str] = []
            raw_score = 0.0

            # Layer 1: pattern matching
            pat_score, pat_hits = self._score_patterns(message, intent)
            raw_score += pat_score * _W_PATTERN
            if pat_hits:
                signals.append(f"pattern:{len(pat_hits)}")

            # Layer 2: semantic phrase detection
            sem_score, sem_hits = self._score_semantic(message, intent)
            raw_score += sem_score * _W_SEMANTIC
            if sem_hits:
                signals.append(f"semantic:{len(sem_hits)}")

            # Layer 3: question/command/reflection structure
            struct_score = self._score_structure(message, intent)
            raw_score += struct_score * _W_STRUCTURE
            if struct_score > 0:
                signals.append("structure")

            # Layer 4: context from routing history
            ctx_score = self._score_context(intent)
            if is_followup:
                # Heavily boost context for follow-up messages
                raw_score += ctx_score * (_W_CONTEXT * 3.0)
                if ctx_score > 0:
                    signals.append("followup_context")
            else:
                raw_score += ctx_score * _W_CONTEXT
                if ctx_score > 0:
                    signals.append("context")

            if raw_score > 0:
                results.append(ScoredIntent(
                    name=intent.name,
                    module=intent.module,
                    score=round(raw_score, 4),
                    signals=signals,
                ))

        results.sort(key=lambda s: s.score, reverse=True)
        return results

    def record_routing(self, module: str) -> None:
        """Record a routing decision for context-aware follow-up detection."""
        self._routing_history.append(module)


def default_builtin_registry():
    """Build the registry of the 10 built-in NexusModule classes.

    Lazy imports — these modules import the kernel transitively, so
    a module-level import here would create a circular dependency at
    `import nexus.kernel.cortex` time.
    """
    from nexus.agents.registry import BuiltinRegistry
    from nexus.modules.council import CouncilModule
    from nexus.modules.specter import SpecterModule
    from nexus.modules.autonomic import AutonomicModule
    from nexus.modules.oracle import OracleModule
    from nexus.modules.wraith import WraithModule
    from nexus.modules.legacy import LegacyModule
    from nexus.modules.consciousness import ConsciousnessModule
    from nexus.modules.sentry import SentryModule
    from nexus.modules.echo import EchoModule
    from nexus.modules.agent_dispatcher import AgentDispatcherModule
    from nexus.modules.sigil import SigilModule
    from nexus.modules.atlas import AtlasModule
    from nexus.modules.chronos import ChronosModule
    from nexus.modules.prism import PrismModule
    from nexus.modules.herald import HeraldModule
    from nexus.modules.serendipity import SerendipityModule

    return BuiltinRegistry.from_modules([
        CouncilModule, SpecterModule, AutonomicModule, OracleModule,
        WraithModule, LegacyModule, ConsciousnessModule, SentryModule,
        EchoModule, AgentDispatcherModule, SigilModule, AtlasModule,
        ChronosModule, PrismModule, HeraldModule, SerendipityModule,
    ])


def specter_autoactivation_enabled(config: NexusConfig) -> bool:
    """Kill switch for Sigil → Specter auto-activation (spec invariant).

    Disabled by env NEXUS_SIGIL_SPECTER_AUTOACTIVATE=0/false/no, or by the
    presence of <data_dir>/sigil-specter.kill (ecosystem kill-switch file).
    """
    if os.environ.get("NEXUS_SIGIL_SPECTER_AUTOACTIVATE", "1").lower() in ("0", "false", "no"):
        return False
    return not (Path(config.data_dir) / "sigil-specter.kill").exists()


# ---------------------------------------------------------------------------
# Cortex -- the central router
# ---------------------------------------------------------------------------

class Cortex:
    """
    Central routing engine for ONEXUS.
    Classifies user intent, enforces trust and permissions, dispatches to
    the appropriate cognitive module, and records everything.
    """

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
        self._classifier = IntentClassifier()
        # Active workspace routing pins — set via set_workspace_config().
        # List of (intent_name_or_None, category_or_None, agent_slug).
        self._workspace_pins: list[tuple[str | None, str | None, str]] = []

    # -- public API (preserved) --------------------------------------------

    def set_workspace_config(self, config: "WorkspaceConfig | None") -> None:
        """Load (or clear) routing pins from the active workspace config.

        Called by the workspace switcher when a workspace is activated or
        deactivated.  Passing ``None`` clears all pins.

        The pins are consulted in :meth:`_select_module` *before* the
        semantic scoring engine, so a pin bypasses Cortex's intent
        classifier for the specified intents / categories.
        """
        if config is None:
            self._workspace_pins = []
            return
        self._workspace_pins = [
            (pin.intent, pin.category, pin.agent)
            for pin in config.routing_pins
        ]

    def set_llm(self, llm_fn) -> None:
        """Set the LLM inference function used by modules and fallback classification."""
        self._llm = llm_fn

    def register_module(self, module: NexusModule) -> None:
        self._modules[module.name] = module

    def register_builtin_manifests(self) -> None:
        """Register every built-in module's manifest with Aegis.

        Called once at kernel boot. Idempotent — registering the same
        manifest twice overwrites the dict entry but does not duplicate
        any DB rows (Aegis seeds trust only if the row is at 0.0).
        """
        registry = default_builtin_registry()
        registry.register_all(self._aegis)
        try:
            self._chronicle.log("cortex", "builtins_registered", {
                "slugs": registry.slugs(),
            })
        except Exception:
            # Chronicle failures must never block kernel boot.
            pass

    async def unregister_module(self, name: str) -> None:
        module = self._modules.pop(name, None)
        if module:
            await module.on_unload(self._build_context())

    def list_modules(self) -> list[str]:
        return list(self._modules.keys())

    def get_module(self, name: str) -> NexusModule | None:
        """Public module lookup (used by Sigil to read Sentry state)."""
        return self._modules.get(name)

    async def initialize_modules(self) -> None:
        """Call on_load for all registered modules with kernel context."""
        context = self._build_context()
        for module in self._modules.values():
            await module.on_load(context)

    # -- emergency routing bypass (N1.1) -------------------------------------

    def attach_emergency_bypass(self) -> None:
        """Give EMERGENCY-priority Pulse messages a routing bypass.

        Emergency broadcasts (Sigil detections) skip intent classification
        and the trust floor entirely: they are logged to Chronicle and, when
        the payload requests it and the kill switch allows, dispatched
        straight to Specter for an adversarial read. Idempotent.
        """
        if getattr(self, "_emergency_sub", None):
            return
        self._emergency_sub = self._pulse.subscribe("*", self._on_emergency_message)

    async def _on_emergency_message(self, msg: Message) -> None:
        from nexus.kernel.pulse import Priority
        if msg.priority != Priority.EMERGENCY or msg.source == "cortex":
            return
        payload = msg.payload or {}
        self._chronicle.log("cortex", "emergency_bypass", {
            "topic": msg.topic, "source": msg.source, "msg_id": msg.msg_id,
            "rule": payload.get("rule"), "module": payload.get("module"),
        })
        if not payload.get("activate_specter"):
            return
        if not specter_autoactivation_enabled(self._config):
            self._chronicle.log("cortex", "specter_autoactivation_skipped",
                                {"reason": "kill_switch", "rule": payload.get("rule")})
            return
        specter = self._modules.get("specter")
        if specter is None:
            return
        try:
            self._aegis.check("specter", "handle")
        except PermissionDenied:
            self._chronicle.log("cortex", "permission_denied", {
                "module": "specter", "message_preview": "sigil emergency adversarial read",
            })
            return
        prompt = (
            "Adversarial read requested by Sigil threat radar. Stress test the "
            f"triggering context: rule={payload.get('rule', 'unknown')} "
            f"module={payload.get('module', 'unknown')} "
            f"evidence={payload.get('evidence', [])}"
        )
        try:
            response = await specter.handle(prompt, self._build_context())
        except Exception as exc:
            self._chronicle.log("cortex", "module_error",
                                {"module": "specter", "error": str(exc)})
            return
        self._chronicle.log("cortex", "specter_auto_activated", {
            "trigger_msg_id": msg.msg_id, "rule": payload.get("rule"),
            "module": payload.get("module"), "response_preview": response[:200],
        })
        await self._pulse.publish(Message(
            topic="cortex.emergency_response", source="cortex",
            payload={"module": "specter", "trigger": msg.topic,
                     "rule": payload.get("rule"), "response": response},
        ))

    # -- context builder ---------------------------------------------------

    def _build_context(self) -> dict[str, Any]:
        return {
            "llm": self._llm,
            "engram": self._engram,
            "chronicle": self._chronicle,
            "aegis": self._aegis,
            "pulse": self._pulse,
            "cortex": self,
        }

    # -- intent selection --------------------------------------------------

    def _select_module(self, message: str) -> tuple[str, list[ScoredIntent]]:
        """
        Select the best module for this message using semantic intent
        classification, trust filtering, and optional LLM fallback.

        Returns (module_name, scored_intents).
        """
        if not self._modules:
            return "", []

        # 1. Classify intent
        scored = self._classifier.classify(message)

        # 1a. Workspace pin resolution — highest priority after classification.
        #     If the top-ranked intent matches a workspace pin, route directly.
        if self._workspace_pins and scored:
            top_intent = scored[0]
            for pin_intent, pin_category, pin_agent in self._workspace_pins:
                if pin_intent is not None and pin_intent == top_intent.name:
                    if pin_agent in self._modules:
                        return pin_agent, scored
                # Category pins apply when the top intent's module matches category.
                if pin_category is not None and pin_category == top_intent.module:
                    if pin_agent in self._modules:
                        return pin_agent, scored

        # 2. Check for explicit module invocation.
        #    Strong forms (prefix, @mention, "Module:") win over weak forms
        #    (bare module name appearing anywhere in the message).
        msg_lower = message.lower()
        msg_stripped = msg_lower.lstrip()
        for mod_name in self._modules:
            # Strong: "@oracle ...", "Oracle: ...", "oracle, ..."
            for prefix in (f"@{mod_name}", f"{mod_name}:", f"{mod_name},", f"{mod_name} —"):
                if msg_stripped.startswith(prefix):
                    return mod_name, scored
        for mod_name in self._modules:
            # Weak: bare module name anywhere in the message
            if mod_name in msg_lower:
                return mod_name, scored

        # 3. Filter by availability, permissions, and trust floor
        for intent in scored:
            if intent.module not in self._modules:
                continue
            trust = self._aegis.get_trust(intent.module)
            if trust < _TRUST_FLOOR:
                # Module is OBSERVER tier -- skip for implicit routing
                continue
            return intent.module, scored

        # 4. LLM fallback if no intent scored and LLM is available
        if not scored and self._llm is not None:
            llm_module = self._llm_classify(message)
            if llm_module and llm_module in self._modules:
                llm_intent = ScoredIntent(
                    name="LLM_CLASSIFIED",
                    module=llm_module,
                    score=_W_LLM,
                    signals=["llm_fallback"],
                )
                return llm_module, [llm_intent]

        # 5. Absolute fallback: council (safest default for ambiguous queries)
        if "council" in self._modules:
            return "council", scored

        # 6. Last resort: first available module
        return next(iter(self._modules)), scored

    def _llm_classify(self, message: str) -> str | None:
        """
        Use the LLM to classify intent when pattern matching fails.
        Returns a module name or None.
        """
        if self._llm is None:
            return None

        module_list = ", ".join(self._modules.keys())
        prompt = (
            f"Classify the following user message into exactly one of these modules: {module_list}\n"
            f"Respond with ONLY the module name, nothing else.\n\n"
            f"Message: {message}"
        )
        try:
            result = self._llm(prompt)
            if result:
                candidate = result.strip().lower().split()[0]
                if candidate in self._modules:
                    return candidate
        except Exception:
            pass
        return None

    # -- main processing pipeline ------------------------------------------

    async def _emit_engram_write(self, tier: str, source: str, content: str) -> None:
        """Stream an Engram write onto Pulse so the live kernel scene can render
        memory forming (a mote settling into the working/episodic/semantic/atlas
        strata). Best-effort: the store itself already succeeded, so a failed
        broadcast must never break routing."""
        try:
            preview = (content or "").strip().replace("\n", " ")[:80]
            await self._pulse.publish(Message(
                topic="engram.write",
                source="engram",
                payload={"tier": tier, "source": source, "preview": preview},
            ))
        except Exception:
            pass

    async def process(self, message: str) -> str:
        """Route a user message to the appropriate module and return the response."""
        # 1. Classify intent -> get scored list of module matches
        target, scored_intents = self._select_module(message)

        if not target:
            return "[Nexus] No modules loaded."

        # 2. Check permissions
        try:
            self._aegis.check(target, "handle")
        except PermissionDenied:
            self._chronicle.log("cortex", "permission_denied", {
                "module": target,
                "message_preview": message[:100],
                "intent_scores": [
                    {"name": s.name, "module": s.module, "score": s.score}
                    for s in scored_intents[:3]
                ],
            })
            return f"[Nexus] Module '{target}' is not allowed to respond. Enable it with: nexus allow {target}"

        # 3. Check network permission for peer-aware modules
        module = self._modules[target]
        if module.requires_network and not self._aegis.is_network_allowed(target):
            self._chronicle.log("cortex", "network_denied", {
                "module": target, "message_preview": message[:100],
            })
            return (
                f"[Nexus] Module '{target}' requires network access but it is not enabled. "
                f"Grant it with: nexus allow --network {target}"
            )

        # 4. Log the routing decision with classification scores
        self._chronicle.log("cortex", "route", {
            "target": target,
            "message_preview": message[:100],
            "intent_scores": [
                {"name": s.name, "module": s.module, "score": s.score, "signals": s.signals}
                for s in scored_intents[:5]
            ],
            "trust_tier": self._aegis.get_tier(target),
        })

        # 4b. Stream the routing decision live (N1.3 kernel visualization)
        await self._pulse.publish(Message(
            topic="kernel.route",
            source="cortex",
            payload={
                "target": target,
                "trust_tier": self._aegis.get_tier(target),
                "message_preview": message[:100],
                "signals": [
                    {"name": s.name, "module": s.module, "score": s.score,
                     "signals": s.signals}
                    for s in scored_intents[:5]
                ],
            },
        ))

        # 5. Store the user message in episodic memory
        self._engram.episodic.store(f"User: {message}", source="user_input")
        await self._emit_engram_write("episodic", "user_input", message)

        # 6. Build context dict (includes aegis)
        context = self._build_context()

        # 7. Execute module.handle()
        try:
            response = await module.handle(message, context)
        except Exception as exc:
            self._chronicle.log("cortex", "module_error", {
                "module": target, "error": str(exc),
            })
            self._aegis.record_outcome(target, False)
            return f"[Nexus] Module '{target}' encountered an error and could not complete your request."

        # 8. Trust adjustment deferred -- applied via user feedback (accept/reject)

        # 9. Record routing decision in classifier history
        self._classifier.record_routing(target)

        # 10. Store the response in episodic memory
        self._engram.episodic.store(f"Nexus ({target}): {response}", source=f"module.{target}")
        await self._emit_engram_write("episodic", f"module.{target}", response)

        # 11. Log completion
        self._chronicle.log("cortex", "response", {
            "module": target, "response_preview": response[:200],
        })

        # 12. Publish to Pulse for any listening modules
        await self._pulse.publish(Message(
            topic="cortex.response",
            source="cortex",
            payload={"module": target, "message": message, "response": response},
        ))

        return response
