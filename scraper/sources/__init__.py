"""Registro de portais disponiveis."""

from __future__ import annotations

from .base import JobSource
from .geekhunter import GeekHunterSource
from .gupy import GupySource
from .linkedin import LinkedInSource
from .querovagastech import QueroVagasTechSource
from .trampos import TramposSource
from .vagas_com import VagasComSource
from .weworkremotely import WeWorkRemotelySource

SOURCE_REGISTRY: dict[str, type[JobSource]] = {
    GupySource.name: GupySource,
    VagasComSource.name: VagasComSource,
    TramposSource.name: TramposSource,
    LinkedInSource.name: LinkedInSource,
    WeWorkRemotelySource.name: WeWorkRemotelySource,
    GeekHunterSource.name: GeekHunterSource,
    QueroVagasTechSource.name: QueroVagasTechSource,
}

AVAILABLE_SOURCES = list(SOURCE_REGISTRY)

__all__ = ["JobSource", "GupySource", "VagasComSource",
           "TramposSource", "LinkedInSource", "WeWorkRemotelySource",
           "GeekHunterSource", "QueroVagasTechSource",
           "SOURCE_REGISTRY", "AVAILABLE_SOURCES"]
