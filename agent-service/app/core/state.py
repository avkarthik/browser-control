from dataclasses import dataclass, field
from browser_use import Agent


@dataclass
class AgentState:
    agent: Agent | None = None
    task: str | None = None
    step: int = 0
    paused: bool = False
    provider: str | None = None


# Singleton — imported across routers and services
agent_state = AgentState()