class AgentBusyError(Exception):
    """Agent is already running a task."""
    pass


class NoActiveAgentError(Exception):
    """No agent is currently running."""
    pass