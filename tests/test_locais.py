"""Reconhecimento do local e aceitação de vaga presencial."""

from __future__ import annotations

import pytest

from scraper.locais import (
    LOCAIS,
    RIO_GRANDE_DO_NORTE as RN,
    resolver,
    serve_presencialmente,
)
from scraper.models import NAO_INFORMADO, PRESENCIAL, REMOTO, Job


@pytest.mark.parametrize("local", [
    # Formatos reais, um de cada portal.
    "Natal, Rio Grande do Norte",      # Gupy
    "Natal, RN",                       # LinkedIn
    "Mossoró, Rio Grande do Norte",    # Gupy
    "Natal / RN A empresa aceita candidaturas de Natal",  # Vagas.com
    "Greater Natal",                   # LinkedIn
    "Parnamirim, Rio Grande do Norte",
    "São José de Mipibu, Rio Grande do Norte",
])
def test_reconhece_locais_do_rn(local):
    assert RN.reconhece(local)


@pytest.mark.parametrize("local", [
    "São Paulo, São Paulo",
    "Belo Horizonte / MG",
    "Rio de Janeiro, RJ",
    "Anywhere in the World",
    "",
    # Homônimas de propósito fora da lista: existem em outros estados.
    "Parnamirim, Pernambuco",
    "Santa Cruz do Sul, RS",
    "São Gonçalo do Amarante, Ceará",
])
def test_nao_reconhece_fora_do_rn(local):
    assert not RN.reconhece(local)


def test_rn_nao_casa_dentro_de_outra_palavra():
    """"RN" solto não pode casar em "Governador Valadares" e afins."""
    assert not RN.reconhece("Turnê Nacional, SP")
    assert not RN.reconhece("Cornélio Procópio, PR")


def _job(**kw):
    base = dict(source="gupy", external_id="1", title="Dev Júnior")
    return Job(**{**base, **kw})


def test_vaga_presencial_no_rn_serve():
    job = _job(location="Natal, Rio Grande do Norte", workplace_type=PRESENCIAL)
    assert serve_presencialmente(job, [RN])


def test_vaga_presencial_fora_do_rn_nao_serve():
    job = _job(location="São Paulo, SP", workplace_type=PRESENCIAL)
    assert not serve_presencialmente(job, [RN])


def test_modalidade_nao_informada_no_rn_serve():
    """Aqui o local é a prova; a modalidade não precisa ser afirmada."""
    job = _job(location="Natal, RN", workplace_type=NAO_INFORMADO)
    assert serve_presencialmente(job, [RN])


def test_vaga_do_trampos_sem_cidade_vale_pela_consulta():
    """O portal não publica cidade: a prova é ter vindo da busca por RN."""
    job = _job(source="trampos", location="", local_consultado="rn")
    assert serve_presencialmente(job, [RN])


def test_sem_locais_configurados_nada_serve():
    job = _job(location="Natal, RN", workplace_type=PRESENCIAL)
    assert not serve_presencialmente(job, [])


def test_resolver_ignora_slug_desconhecido():
    assert resolver(["rn", "xx"]) == [LOCAIS["rn"]]


def test_remota_de_outro_estado_nao_depende_deste_filtro():
    """Quem decide sobre remota é o pipeline; aqui ela não é "do RN"."""
    job = _job(location="São Paulo, SP", workplace_type=REMOTO)
    assert not serve_presencialmente(job, [RN])
