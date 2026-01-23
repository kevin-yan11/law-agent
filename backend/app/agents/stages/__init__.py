"""Stage implementations for adaptive legal agent workflow."""

from app.agents.stages.safety_gate import safety_gate_node, route_after_safety

__all__ = ["safety_gate_node", "route_after_safety"]
