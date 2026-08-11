from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ProviderCandidate:
    provider: str
    model: str
    secret: str
    source: str
    key_id: int | None
    base_url: str | None = None


class ProviderRouter:
    """Selects credentials supplied by the request, with configurable fallbacks."""

    def candidates(self, selected: ProviderCandidate, available: list[ProviderCandidate], level: str) -> list[ProviderCandidate]:
        ordered = [selected] + [item for item in available if (item.provider, item.model, item.key_id) != (selected.provider, selected.model, selected.key_id)]
        configured = self._configured(level)
        if not configured:
            return ordered
        rank = {f"{provider.lower()}:{model.lower()}": index for index, (provider, model) in enumerate(configured)}
        return sorted(ordered, key=lambda item: rank.get(f"{item.provider.lower()}:{item.model.lower()}", len(rank) + 1))

    def _configured(self, level: str) -> list[tuple[str, str]]:
        raw = os.getenv(f"AI_ROUTING_{level}", "")
        result = []
        for item in raw.split(","):
            if ":" in item:
                provider, model = item.split(":", 1)
                if provider.strip() and model.strip():
                    result.append((provider.strip(), model.strip()))
        return result
