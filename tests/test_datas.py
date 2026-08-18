"""Normalização da data de publicação e descarte de vaga velha."""

from __future__ import annotations

from datetime import date

import pytest

from scraper.datas import dias_desde, filtrar_recentes, normalizar_data
from scraper.models import Job

HOJE = date(2026, 8, 17)


@pytest.mark.parametrize("bruto,esperado", [
    # Quatro dos cinco portais já entregam ISO e passam intactos.
    ("2026-08-17", "2026-08-17"),
    ("2026-08-17T13:45:00Z", "2026-08-17"),
    # O Vagas.com é a exceção: dd/mm/aaaa e texto relativo.
    ("03/08/2026", "2026-08-03"),
    ("9/7/2026", "2026-07-09"),
    ("Há 5 dias", "2026-08-12"),
    ("há 1 dia", "2026-08-16"),
    ("Hoje", "2026-08-17"),
    ("Ontem", "2026-08-16"),
    ("Há 2 semanas", "2026-08-03"),
    ("Há 3 meses", "2026-05-19"),
    ("Há 1 ano", "2025-08-17"),
])
def test_normaliza_para_iso(bruto, esperado):
    assert normalizar_data(bruto, hoje=HOJE) == esperado


def test_mais_de_30_dias_vira_exatamente_30():
    """É o piso que o portal garante; arredondar inventaria idade."""
    assert normalizar_data("Há mais de 30 dias", hoje=HOJE) == "2026-07-18"


@pytest.mark.parametrize("bruto", ["", "   ", "em breve", "32/13/2026", "sexta-feira"])
def test_data_irreconhecivel_vira_vazio(bruto):
    assert normalizar_data(bruto, hoje=HOJE) == ""


def test_dias_desde_conta_a_idade():
    assert dias_desde("2026-08-10", hoje=HOJE) == 7
    assert dias_desde("2026-08-17", hoje=HOJE) == 0


@pytest.mark.parametrize("valor", ["", "amanhã", "2026-13-45"])
def test_dias_desde_sem_data_devolve_none(valor):
    assert dias_desde(valor, hoje=HOJE) is None


def _job(data, titulo="Dev Júnior"):
    return Job(source="gupy", external_id=titulo, title=titulo, published_date=data)


def test_descarta_a_vaga_velha_e_mantem_a_recente():
    jobs = [_job("2026-08-10", "recente"), _job("2022-03-11", "de 2022")]
    ficaram = [j.title for j in filtrar_recentes(jobs, 60, hoje=HOJE)]
    assert ficaram == ["recente"]


def test_vaga_sem_data_fica():
    """Não dá para provar que é velha; o oposto do filtro de remotas."""
    jobs = [_job("", "sem data")]
    assert filtrar_recentes(jobs, 60, hoje=HOJE) == jobs


def test_limite_e_inclusivo_no_ultimo_dia():
    jobs = [_job("2026-06-18", "exatos 60 dias"), _job("2026-06-17", "61 dias")]
    ficaram = [j.title for j in filtrar_recentes(jobs, 60, hoje=HOJE)]
    assert ficaram == ["exatos 60 dias"]


def test_zero_desliga_o_filtro():
    jobs = [_job("2022-03-11", "de 2022")]
    assert filtrar_recentes(jobs, 0, hoje=HOJE) == jobs
