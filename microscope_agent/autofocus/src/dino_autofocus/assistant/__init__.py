"""Claude in the app (PLAN.md 5절 "Claude 연동", X2).

`runner.Assistant` holds the conversations, `tools` the read and proposal tools, `providers`
the fake (default) and Anthropic model providers, `records` the assistant's record file.
Claude only proposes: an action reaches the engine after a person confirms it, and the
engine's gates and guards still apply. Importing this package loads neither `anthropic` nor
torch.
"""

from .runner import Answer, Assistant, AssistantConfig, connection_status
from .tools import Proposal, Sources, ToolSet

__all__ = [
    "Answer",
    "Assistant",
    "AssistantConfig",
    "Proposal",
    "Sources",
    "ToolSet",
    "connection_status",
]
