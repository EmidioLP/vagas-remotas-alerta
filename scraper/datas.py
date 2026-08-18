"""Data de publicacao no mesmo formato, venha como vier do portal.

Quatro dos cinco portais ja entregam ISO (YYYY-MM-DD). O Vagas.com e a
excecao: mistura "03/08/2026" com texto relativo ("Ha 5 dias", "Hoje"), que
so faz sentido em relacao ao dia da coleta -- por isso `hoje` e parametro,
e nao `date.today()` escondido dentro da funcao.

Data desconhecida vira "" e, no filtro, e tratada como "nao da para provar
que e velha": a vaga fica. O oposto do filtro de remotas, onde a falta de
informacao derruba a vaga -- ali o silencio esconderia uma presencial, aqui
esconderia so a idade.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, timedelta

from .models import Job

logger = logging.getLogger(__name__)

ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
BRASILEIRA = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
RELATIVA = re.compile(
    r"ha\s+(?:mais\s+de\s+)?(\d+)\s+(dias?|semanas?|mes|meses|anos?)\b"
)
DIAS_POR_UNIDADE = {
    "dia": 1, "dias": 1,
    "semana": 7, "semanas": 7,
    "mes": 30, "meses": 30,
    "ano": 365, "anos": 365,
}


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn").lower()


def normalizar_data(bruto: str, hoje: date | None = None) -> str:
    """Devolve ISO YYYY-MM-DD, ou "" quando nao da para reconhecer nada."""
    texto = (bruto or "").strip()
    if not texto:
        return ""

    if achado := ISO.match(texto):
        return achado.group(0)

    if achado := BRASILEIRA.match(texto):
        dia, mes, ano = (int(g) for g in achado.groups())
        try:
            return date(ano, mes, dia).isoformat()
        except ValueError:
            return ""

    hoje = hoje or date.today()
    simples = _sem_acento(texto)
    if "hoje" in simples:
        return hoje.isoformat()
    if "ontem" in simples:
        return (hoje - timedelta(days=1)).isoformat()

    if achado := RELATIVA.search(simples):
        quantidade = int(achado.group(1))
        # "Ha mais de 30 dias" vira exatamente 30 dias: e o piso que o portal
        # garante, e arredondar para mais inventaria idade que ele nao afirma.
        return (hoje - timedelta(
            days=quantidade * DIAS_POR_UNIDADE[achado.group(2)])).isoformat()

    return ""


def dias_desde(publicada: str, hoje: date | None = None) -> int | None:
    """Idade em dias. None quando a data e desconhecida ou impossivel."""
    if not ISO.match(publicada or ""):
        return None
    try:
        dia = date.fromisoformat(publicada[:10])
    except ValueError:
        return None
    return ((hoje or date.today()) - dia).days


def filtrar_recentes(
    jobs: list[Job], dias_max: int, hoje: date | None = None
) -> list[Job]:
    """Descarta o que foi publicado ha mais de `dias_max` dias.

    Portal nao tira anuncio velho do ar: a coleta trouxe vaga de 2022, de
    painel ja desativado. Avisar sobre ela e ruido -- ninguem se candidata.
    `dias_max <= 0` desliga o filtro.
    """
    if dias_max <= 0:
        return jobs

    recentes = []
    for job in jobs:
        idade = dias_desde(job.published_date, hoje)
        if idade is not None and idade > dias_max:
            logger.debug("Vaga de %s (%d dias): %s",
                         job.published_date, idade, job.title)
            continue
        recentes.append(job)
    return recentes
