"""Orquestracao: coleta -> nivel de entrada -> dedupe -> remotas -> classifica.

Diferente do projeto de analise que originou este codigo, aqui nao ha CSV,
grafico nem relatorio: a saida e uma lista de vagas na memoria, que o
`alerta.py` compara com o estado e manda para o Discord.
"""

from __future__ import annotations

import logging

from .classifier import classify_jobs, default_classifier, filter_tech
from .config import Settings
from .datas import filtrar_recentes
from .dedupe import deduplicate
from .http_client import PoliteSession
from .models import REMOTO, Job
from .seniority import filter_entry_level
from .skills import attach_skills
from .sources import SOURCE_REGISTRY

logger = logging.getLogger(__name__)


def coletar_vagas(settings: Settings) -> list[Job]:
    """Devolve as vagas de nivel de entrada, remotas e de tecnologia."""
    brutas: list[Job] = []

    for nome in settings.sources:
        origem = SOURCE_REGISTRY.get(nome)
        if origem is None:
            logger.warning("Portal desconhecido, ignorando: %s", nome)
            continue

        logger.info("=== Coletando em %s ===", origem.label)
        with PoliteSession(
            user_agent=settings.user_agent,
            delay_seconds=settings.delay_seconds,
            timeout_seconds=settings.timeout_seconds,
            max_retries=settings.max_retries,
            backoff_factor=settings.backoff_factor,
        ) as sessao:
            fonte = origem(sessao, settings)
            achadas = fonte.fetch(settings.search_terms)
            brutas.extend(achadas)
            for erro in fonte.stats.errors:
                logger.warning("Erro em %s", erro)

        logger.info("%s: %d vagas brutas", origem.label, len(achadas))

    logger.info("Total bruto: %d vagas", len(brutas))

    jobs = filter_entry_level(brutas)
    logger.info("Nivel de entrada: %d (-%d)", len(jobs), len(brutas) - len(jobs))

    antes = len(jobs)
    jobs, _ = deduplicate(jobs)
    logger.info("Apos deduplicacao: %d (-%d)", len(jobs), antes - len(jobs))

    antes = len(jobs)
    jobs, _ = filter_tech(jobs, default_classifier())
    logger.info("De tecnologia: %d (-%d)", len(jobs), antes - len(jobs))

    if settings.dias_max > 0:
        antes = len(jobs)
        jobs = filtrar_recentes(jobs, settings.dias_max)
        logger.info("Publicadas nos ultimos %d dias: %d (-%d)",
                    settings.dias_max, len(jobs), antes - len(jobs))

    if settings.somente_remotas:
        antes = len(jobs)
        jobs = [j for j in jobs if j.workplace_type == REMOTO]
        logger.info("Remotas: %d (-%d)", len(jobs), antes - len(jobs))

    jobs = classify_jobs(jobs, default_classifier())
    return attach_skills(jobs)
