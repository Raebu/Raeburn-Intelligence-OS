from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .models import Evidence, SourceRecord


class SourceConnector(ABC):
    """Contract for ingestion connectors.

    Connectors fetch source data and emit normalized Evidence records. They must not
    create commercial signals directly; signal derivation belongs in a separate layer.
    """

    source: SourceRecord

    @abstractmethod
    async def collect(self) -> AsyncIterator[Evidence]:
        """Yield normalized evidence from the upstream source."""
        raise NotImplementedError


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, SourceConnector] = {}

    def register(self, connector: SourceConnector) -> None:
        source_id = connector.source.id
        if source_id in self._connectors:
            raise ValueError(f"Connector already registered for source: {source_id}")
        self._connectors[source_id] = connector

    def get(self, source_id: str) -> SourceConnector | None:
        return self._connectors.get(source_id)

    def all(self) -> list[SourceConnector]:
        return list(self._connectors.values())
