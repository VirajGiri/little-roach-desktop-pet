"""Optional local-AI extension point. The first version intentionally uses no model."""

from typing import Protocol


class PetAssistant(Protocol):
    def respond(self, interaction: str) -> str:
        """Return a short pet response without requiring a network service."""


class OfflineAssistant:
    """Safe default behavior until a local model adapter is configured."""

    def respond(self, interaction: str) -> str:
        return "Thanks for saying hello!" if interaction == "greet" else "*antennae wiggle*"
