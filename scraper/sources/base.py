"""Contrato comum a todos os portais."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..config import Settings
from ..http_client import PoliteSession
from ..locais import Local, resolver
from ..models import Job, SourceStats

logger = logging.getLogger(__name__)


class JobSource(ABC):
    """Um portal de vagas.

    Para adicionar um portal novo: herde desta classe, implemente
    `fetch_term` e registre a classe em `scraper/sources/__init__.py`.
    """

    name: str = "base"
    label: str = "Base"

    def __init__(self, session: PoliteSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.stats = SourceStats(source=self.name)

    @property
    def locais(self) -> list[Local]:
        """Locais que aceitam presencial, ja resolvidos da configuracao."""
        return resolver(self.settings.locais_presenciais)

    @abstractmethod
    def fetch_term(self, term: str) -> list[Job]:
        """Coleta as vagas de um unico termo de busca."""

    def fetch_local(self, local: Local, terms: list[str]) -> list[Job]:
        """Coleta as vagas daquele local, com os mesmos termos de busca.

        Consultar o local sem termo nenhum foi tentado antes e sai caro em
        ruido: o portal devolve o estado inteiro, de todas as areas, e o
        portao de relevancia deixa passar "Estagiario de Manutencao
        Industrial" so porque a descricao cita Excel e SAP. Com os termos, a
        consulta por local tem a mesma precisao que a nacional.

        Portal que nao sabe filtrar por local devolve lista vazia.
        """
        return []

    def fetch(self, terms: list[str]) -> list[Job]:
        """Coleta todos os termos, isolando falhas de um termo dos demais."""
        jobs: list[Job] = []
        for term in terms:
            try:
                found = self.fetch_term(term)
            except Exception as exc:  # nao derruba a coleta inteira
                message = f"{self.name}/{term}: {exc}"
                logger.warning("Erro coletando %s", message)
                self.stats.errors.append(message)
                continue
            logger.info("[%s] '%s' -> %d vagas", self.name, term, len(found))
            jobs.extend(found)

        for local in self.locais:
            try:
                found = self.fetch_local(local, terms)
            except Exception as exc:
                message = f"{self.name}/local:{local.slug}: {exc}"
                logger.warning("Erro coletando %s", message)
                self.stats.errors.append(message)
                continue
            if found:
                logger.info("[%s] local '%s' -> %d vagas",
                            self.name, local.slug, len(found))
            jobs.extend(found)

        self.stats.raw_jobs = len(jobs)
        self.stats.requests_made = self.session.request_count
        return jobs
