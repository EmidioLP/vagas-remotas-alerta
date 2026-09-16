"""Reconhecimento do local e aceitação de vaga presencial."""

from __future__ import annotations

import pytest

from scraper.config import Settings
from scraper.locais import (
    FORTALEZA,
    LOCAIS,
    RIO_GRANDE_DO_NORTE as RN,
    resolver,
    serve_presencialmente,
)
from scraper.models import NAO_INFORMADO, PRESENCIAL, REMOTO, Job
from scraper.sources.base import JobSource
from scraper.sources.gupy import GupySource
from scraper.sources.trampos import TramposSource


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


def test_vaga_vinda_de_consulta_pelo_rn_vale_pela_consulta():
    """No RN a consulta é prova: cada portal devolve só o estado."""
    job = _job(source="linkedin", location="", local_consultado="rn")
    assert serve_presencialmente(job, [RN])
    assert not serve_presencialmente(job, [FORTALEZA]), "consulta de um local não vale para outro"


@pytest.mark.parametrize("local", [
    # Medido: vieram da consulta do LinkedIn por Fortaleza.
    "Maracanaú, CE",
    "Eusébio, CE",
    # Rótulo da região metropolitana inteira.
    "Greater Fortaleza",
    "",
])
def test_em_fortaleza_a_consulta_nao_basta(local):
    """O geoId do LinkedIn cobre a região metropolitana; o pedido é só a capital."""
    job = _job(source="linkedin", location=local, local_consultado="fortaleza")
    assert not serve_presencialmente(job, [FORTALEZA])


def test_capital_vinda_da_consulta_continua_entrando():
    job = _job(source="linkedin", location="Fortaleza, CE", local_consultado="fortaleza")
    assert serve_presencialmente(job, [FORTALEZA])


def test_capital_entra_pelo_texto_mesmo_sem_consulta():
    """Vale para fontes sem consulta por local, como a GeekHunter."""
    job = _job(source="geekhunter", location="Fortaleza, CE")
    assert serve_presencialmente(job, [FORTALEZA])


# --- Fortaleza -------------------------------------------------------------

@pytest.mark.parametrize("local", [
    # Formatos medidos, um de cada portal.
    "Fortaleza, Ceará",                                  # Gupy
    "Fortaleza, Ceará, Brazil",                          # LinkedIn
    "Fortaleza, CE",                                     # LinkedIn
    "Fortaleza / CE A empresa aceita candidaturas de Fortaleza",  # Vagas.com
    "Fortaleza, Ceará, BR",                              # Quero Vagas Tech
    "Fortaleza - CE",
])
def test_reconhece_fortaleza(local):
    assert FORTALEZA.reconhece(local)


@pytest.mark.parametrize("local", [
    # Homônimas medidas no typeahead do LinkedIn.
    "Fortaleza dos Valos, Rio Grande do Sul",
    "Fortaleza de Minas, Minas Gerais",
    "Fortaleza dos Nogueiras, Maranhão",
    "Cruzeiro da Fortaleza, MG",
    # Pedido foi a capital, não o Ceará nem a região metropolitana.
    "Caucaia, Ceará",
    "Maracanaú, CE",
    "Greater Fortaleza",
    "Juazeiro do Norte, CE",
    # Sem estado não dá para saber qual Fortaleza é.
    "Fortaleza",
])
def test_nao_reconhece_fora_de_fortaleza(local):
    assert not FORTALEZA.reconhece(local)


def test_rn_e_fortaleza_nao_se_confundem():
    assert not FORTALEZA.reconhece("Natal, RN")
    assert not RN.reconhece("Fortaleza, Ceará")


def test_fortaleza_esta_ativa_por_padrao():
    assert "fortaleza" in Settings().locais_presenciais


# --- Consultas por local nos portais --------------------------------------

class _SessaoGravadora:
    def __init__(self):
        self.params = []
        self.request_count = 0

    def get_json(self, url, params=None, **kwargs):
        self.params.append(params)
        return None


def test_gupy_consulta_fortaleza_pela_cidade_e_o_rn_pelo_estado():
    """Pedir `state=Ceará` traria Caucaia e Juazeiro, aceitos pela consulta."""
    sessao = _SessaoGravadora()
    fonte = GupySource(session=sessao, settings=Settings())

    fonte.fetch_local(FORTALEZA, ["desenvolvedor"])
    assert sessao.params[-1]["city"] == "Fortaleza"
    assert "state" not in sessao.params[-1]

    fonte.fetch_local(RN, ["desenvolvedor"])
    assert sessao.params[-1]["state"] == "Rio Grande do Norte"
    assert "city" not in sessao.params[-1]


def test_trampos_nao_consulta_por_local():
    """Medido: `lc=Natal`, `lc=Fortaleza` e `lc=CidadeQueNaoExisteXYZ`
    devolvem a mesma vaga. Consultar por local ali aceitaria vaga de fora."""
    assert TramposSource.fetch_local is JobSource.fetch_local
    fonte = TramposSource(session=_SessaoGravadora(), settings=Settings())
    for local in LOCAIS.values():
        assert fonte.fetch_local(local, ["desenvolvedor"]) == []


def test_nenhum_local_tem_parametro_do_trampos():
    for local in LOCAIS.values():
        assert not hasattr(local, "trampos_lc")


def test_sem_locais_configurados_nada_serve():
    job = _job(location="Natal, RN", workplace_type=PRESENCIAL)
    assert not serve_presencialmente(job, [])


def test_resolver_ignora_slug_desconhecido():
    assert resolver(["rn", "xx"]) == [LOCAIS["rn"]]


def test_remota_de_outro_estado_nao_depende_deste_filtro():
    """Quem decide sobre remota é o pipeline; aqui ela não é "do RN"."""
    job = _job(location="São Paulo, SP", workplace_type=REMOTO)
    assert not serve_presencialmente(job, [RN])
