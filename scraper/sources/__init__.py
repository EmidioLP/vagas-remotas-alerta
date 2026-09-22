"""Registro de portais disponiveis."""

from __future__ import annotations

from .abler import AblerSource
from .base import JobSource
from .geekhunter import GeekHunterSource
from .gupy import GupySource
from .infojobs import InfoJobsSource
from .linkedin import LinkedInSource
from .mentoradados import MentoraDadosSource
from .querovagastech import QueroVagasTechSource
from .recrutei import RecruteiSource
from .solides import SolidesSource
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
    MentoraDadosSource.name: MentoraDadosSource,
    SolidesSource.name: SolidesSource,
    InfoJobsSource.name: InfoJobsSource,
    RecruteiSource.name: RecruteiSource,
    AblerSource.name: AblerSource,
}

AVAILABLE_SOURCES = list(SOURCE_REGISTRY)

__all__ = ["JobSource", "GupySource", "VagasComSource",
           "TramposSource", "LinkedInSource", "WeWorkRemotelySource",
           "GeekHunterSource", "QueroVagasTechSource", "MentoraDadosSource",
           "SolidesSource", "InfoJobsSource", "RecruteiSource", "AblerSource",
           "SOURCE_REGISTRY", "AVAILABLE_SOURCES"]
