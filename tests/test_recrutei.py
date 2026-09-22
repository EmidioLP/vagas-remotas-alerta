"""Testes do coletor do Recrutei, com recortes reais do portal (offline)."""

from __future__ import annotations

import re
from datetime import date, timedelta

from scraper.classifier import default_classifier
from scraper.config import Settings
from scraper.datas import filtrar_recentes
from scraper.locais import (FORTALEZA, RIO_GRANDE_DO_NORTE,
                            serve_presencialmente)
from scraper.models import HIBRIDO, NAO_INFORMADO, PRESENCIAL, REMOTO
from scraper.notificacao import url_valida
from scraper.seniority import filter_entry_level
from scraper.sources.recrutei import (LISTAGEM_REMOTA, MAX_PAGINAS, PAGE_SIZE,
                                      PORTAL_URL, RecruteiSource)

# Cards capturados em 22/09/2026, das listagens
#   /vagas-de-trabalho-remoto-home-office
#   /vagas/em/rn
#   /vagas/em/fortaleza-ce
#   /vagas/tecnologia?page=2   (so por causa do selo "Presencial ou Remoto",
#                               que nao aparece na listagem de home office)
# Nenhum corte em lugar nenhum: a indentacao larga, os `?has_bot=1`, o `<li>`
# vazio do terceiro selo e a descricao inteira do JSON-LD sao como chegaram.

# Vaga remota, a forma mais comum: local "Brasil" (108 dos 134 cards) e
# data em horas, que so aparece nas primeiras 24h.
CARD_REMOTO = """<div class="list-grid-item rounded position-relative">
                        <a href="https://empregos.recrutei.com.br/vaga/gex-corporation/158928-analista-de-atendimento?has_bot=1" 
                    class="position-absolute w-100 h-100"></a>
                        <div class="grid-item-content p-3">
                <div class="grid-list-img mt-3">
                                            <a href="https://empregos.recrutei.com.br/vaga/gex-corporation/158928-analista-de-atendimento?has_bot=1">
                                                                        <img src="https://recrutei-web.s3.amazonaws.com/storage/files/logos/BBQWfUgye4Sr6wUjaGVQbdXoGJ3NVceifvdqr19V.jpg" alt="Logo GEX Corporation" class="img-fluid d-block" loading="lazy">
                                            </a>
                </div>
                <div class="grid-list-desc mt-3">
                    <h6 class="mb-1">
                                                    <a href="https://empregos.recrutei.com.br/vaga/gex-corporation/158928-analista-de-atendimento?has_bot=1"
                        class="job-title">Analista de Atendimento</a>
                                            </h6>
                                                    <p class="text-muted f-14 mb-1"><i class="mdi mdi-bank mr-2 text-primary-light"></i>GEX Corporation</p>
                                                                            <p class="text-muted mb-1"><i class="mdi mdi-map-marker text-primary-light"></i>
                                                                    Brasil
                                                            </p>
                                                                                                    <p class="text-muted mb-1 small"><i class="fa fa-solid fa-comments-dollar text-primary-light"></i> Não informado</p>
                                            <p class="text-muted mb-1"><i
                        class="mdi mdi-clock-outline text-primary-light"></i>
                        <span class="small">
                            Publicada há 6 horas
                        </span>
                   </p>
                </div>
                <ul class="list-inline">
                    <li class="list-inline-item">
                                                <span class="badge bg-primary-light text-white">
                            Pessoa Jurídica
                        </span>
                                            </li>
                    <li class="list-inline-item ">
                        <span class="badge bg-primary text-white">Remoto</span>
                    </li>
                    <li class="list-inline-item">
                                            </li>
                </ul>
            </div>
            <div class="apply-button p-3 border-top bg-light text-right">
                                <a href="https://empregos.recrutei.com.br/vaga/gex-corporation/158928-analista-de-atendimento?has_bot=1" class="btn btn-sm btn-success mb-2">Candidate-se por <i class="fa fa-brands fa-whatsapp"></i> Whatsapp</a>
                                                    <a href="https://empregos.recrutei.com.br/vaga/gex-corporation/158928-analista-de-atendimento?has_bot=1" class="btn btn-sm btn-secondary">Candidatar-se</a>
                            </div>
        </div>"""

# Presencial em Natal, da consulta por UF. O titulo tem barra e pipe, e o
# selo de regime e "Estagio".
CARD_NATAL = """<div class="list-grid-item rounded position-relative">
                        <a href="https://empregos.recrutei.com.br/vaga/elo-solucoes-em-rh/158510-estagio-em-atendimento-academia-de-alto-padrao-em-natalrn" 
                    class="position-absolute w-100 h-100"></a>
                        <div class="grid-item-content p-3">
                <div class="grid-list-img mt-3">
                                            <a href="https://empregos.recrutei.com.br/vaga/elo-solucoes-em-rh/158510-estagio-em-atendimento-academia-de-alto-padrao-em-natalrn">
                                                                        <img src="https://recrutei-web.s3.amazonaws.com/storage/files/logos/CK8cyKpY15lhHTRU1rrKiVbTkE75OgGyVZyuY1sC.jpg" alt="Logo ELO SOLUÇÕES EM RH" class="img-fluid d-block" loading="lazy">
                                            </a>
                </div>
                <div class="grid-list-desc mt-3">
                    <h6 class="mb-1">
                                                    <a href="https://empregos.recrutei.com.br/vaga/elo-solucoes-em-rh/158510-estagio-em-atendimento-academia-de-alto-padrao-em-natalrn"
                        class="job-title">Estágio em Atendimento | Academia de Alto Padrão em Natal/RN</a>
                                            </h6>
                                                    <p class="text-muted f-14 mb-1"><i class="mdi mdi-bank mr-2 text-primary-light"></i>ELO SOLUÇÕES EM RH</p>
                                                                            <p class="text-muted mb-1"><i class="mdi mdi-map-marker text-primary-light"></i>
                                                                    Natal, RN, Brasil
                                                            </p>
                                                                                                    <p class="text-muted mb-1 small"><i class="fa fa-solid fa-comments-dollar text-primary-light"></i> Não informado</p>
                                            <p class="text-muted mb-1"><i
                        class="mdi mdi-clock-outline text-primary-light"></i>
                        <span class="small">
                            Publicada há 4 dias
                        </span>
                   </p>
                </div>
                <ul class="list-inline">
                    <li class="list-inline-item">
                                                <span class="badge bg-primary-light text-white">
                            Estágio
                        </span>
                                            </li>
                    <li class="list-inline-item ">
                        <span class="badge bg-primary text-white">Presencial</span>
                    </li>
                    <li class="list-inline-item">
                                            </li>
                </ul>
            </div>
            <div class="apply-button p-3 border-top bg-light text-right">
                                                    <a href="https://empregos.recrutei.com.br/vaga/elo-solucoes-em-rh/158510-estagio-em-atendimento-academia-de-alto-padrao-em-natalrn" class="btn btn-sm btn-secondary">Candidatar-se</a>
                            </div>
        </div>"""

# Veio da consulta de Fortaleza e NAO e de Fortaleza -- um dos 12 cards da
# regiao metropolitana que so o texto derruba. Tem salario declarado.
CARD_EUSEBIO = """<div class="list-grid-item rounded position-relative">
                        <a href="https://empregos.recrutei.com.br/vaga/vivaz-solucoes/158774-auxiliar-de-servicos-gerais-terrazo-shopping?has_bot=1" 
                    class="position-absolute w-100 h-100"></a>
                        <div class="grid-item-content p-3">
                <div class="grid-list-img mt-3">
                                            <a href="https://empregos.recrutei.com.br/vaga/vivaz-solucoes/158774-auxiliar-de-servicos-gerais-terrazo-shopping?has_bot=1">
                                                                        <img src="https://recrutei-web.s3.amazonaws.com/storage/files/logos/Diz81tl0m19Uq8B9ZDHHIHE7jJSumTwIVngHrbtO.png" alt="Logo Vivaz Soluções" class="img-fluid d-block" loading="lazy">
                                            </a>
                </div>
                <div class="grid-list-desc mt-3">
                    <h6 class="mb-1">
                                                    <a href="https://empregos.recrutei.com.br/vaga/vivaz-solucoes/158774-auxiliar-de-servicos-gerais-terrazo-shopping?has_bot=1"
                        class="job-title">Auxiliar de Serviços Gerais - Terrazo Shopping</a>
                                            </h6>
                                                    <p class="text-muted f-14 mb-1"><i class="mdi mdi-bank mr-2 text-primary-light"></i>Vivaz Soluções</p>
                                                                            <p class="text-muted mb-1"><i class="mdi mdi-map-marker text-primary-light"></i>
                                                                    Eusébio, CE, Brasil
                                                            </p>
                                                                                                    <p class="text-muted mb-1"><i class="fa fa-solid fa-comments-dollar text-primary-light"></i> R$ 1.658,00 p/ Mês</p>
                                            <p class="text-muted mb-1"><i
                        class="mdi mdi-clock-outline text-primary-light"></i>
                        <span class="small">
                            Publicada há 1 dia
                        </span>
                   </p>
                </div>
                <ul class="list-inline">
                    <li class="list-inline-item">
                                                <span class="badge bg-primary-light text-white">
                            CLT
                        </span>
                                            </li>
                    <li class="list-inline-item ">
                        <span class="badge bg-primary text-white">Presencial</span>
                    </li>
                    <li class="list-inline-item">
                                            </li>
                </ul>
            </div>
            <div class="apply-button p-3 border-top bg-light text-right">
                                <a href="https://empregos.recrutei.com.br/vaga/vivaz-solucoes/158774-auxiliar-de-servicos-gerais-terrazo-shopping?has_bot=1" class="btn btn-sm btn-success mb-2">Candidate-se por <i class="fa fa-brands fa-whatsapp"></i> Whatsapp</a>
                                                    <a href="https://empregos.recrutei.com.br/vaga/vivaz-solucoes/158774-auxiliar-de-servicos-gerais-terrazo-shopping?has_bot=1" class="btn btn-sm btn-secondary">Candidatar-se</a>
                            </div>
        </div>"""

# A quarta modalidade, que a listagem de home office nao traz: o portal a
# separa de "Remoto" no proprio filtro (`model=presential-remote`).
CARD_PRESENCIAL_OU_REMOTO = """<div class="list-grid-item rounded position-relative">
                        <a href="https://empregos.recrutei.com.br/vaga/digisystem/158985-consultor-funcional-tasy-assistencialfarmacia?has_bot=1" 
                    class="position-absolute w-100 h-100"></a>
                        <div class="grid-item-content p-3">
                <div class="grid-list-img mt-3">
                                            <a href="https://empregos.recrutei.com.br/vaga/digisystem/158985-consultor-funcional-tasy-assistencialfarmacia?has_bot=1">
                                                                        <img src="https://recrutei-web.s3.amazonaws.com/storage/files/logos/5p97eAOMjCHuQnd35hN7bhpEEwxRVZW9y9JlRZhq.jpg" alt="Logo Digisystem" class="img-fluid d-block" loading="lazy">
                                            </a>
                </div>
                <div class="grid-list-desc mt-3">
                    <h6 class="mb-1">
                                                    <a href="https://empregos.recrutei.com.br/vaga/digisystem/158985-consultor-funcional-tasy-assistencialfarmacia?has_bot=1"
                        class="job-title">Consultor Funcional Tasy Assistencial/Farmácia</a>
                                            </h6>
                                                    <p class="text-muted f-14 mb-1"><i class="mdi mdi-bank mr-2 text-primary-light"></i>Digisystem</p>
                                                                            <p class="text-muted mb-1"><i class="mdi mdi-map-marker text-primary-light"></i>
                                                                    São Paulo, SP, Brasil
                                                            </p>
                                                                                                    <p class="text-muted mb-1 small"><i class="fa fa-solid fa-comments-dollar text-primary-light"></i> Não informado</p>
                                            <p class="text-muted mb-1"><i
                        class="mdi mdi-clock-outline text-primary-light"></i>
                        <span class="small">
                            Publicada há 3 horas
                        </span>
                   </p>
                </div>
                <ul class="list-inline">
                    <li class="list-inline-item">
                                            </li>
                    <li class="list-inline-item ">
                        <span class="badge bg-primary text-white">Presencial ou Remoto</span>
                    </li>
                    <li class="list-inline-item">
                                            </li>
                </ul>
            </div>
            <div class="apply-button p-3 border-top bg-light text-right">
                                <a href="https://empregos.recrutei.com.br/vaga/digisystem/158985-consultor-funcional-tasy-assistencialfarmacia?has_bot=1" class="btn btn-sm btn-success mb-2">Candidate-se por <i class="fa fa-brands fa-whatsapp"></i> Whatsapp</a>
                                                    <a href="https://empregos.recrutei.com.br/vaga/digisystem/158985-consultor-funcional-tasy-assistencialfarmacia?has_bot=1" class="btn btn-sm btn-secondary">Candidatar-se</a>
                            </div>
        </div>"""

# Os dois JSON-LD da pagina da vaga, na ordem em que ela os traz.
_LD_JOB_POSTING = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"ENGENHEIRO DE IA JR","description":"BM VAGAS em parceria com Bhaskara Consultoria em Inteligencia Artificial seleciona ENGENHEIRO DE IA JR para cidade de São José dos Campos.ResponsabilidadesDesenvolver e evoluir o Post4u, produto de IA para planejamento, criação e publicação de conteúdo em redes sociais.Implementar funcionalidades no frontend e backend, integrar APIs de IA, redes sociais, pagamentos e banco de dados, corrigir bugs e melhorar a experiência do usuário.Trabalhar a partir de prioridades e critérios de aceite, registrar decisões e evidências das entregas, escrever e executar testes proporcionais ao risco e acompanhar o produto em produção.Usar ferramentas de IA intensivamente para acelerar pesquisa, implementação, revisão e documentação, mantendo raciocínio crítico, segurança e qualidade técnica.RequisitosAprendizado rápido, abertura a feedback, curiosidade, autonomia, organização, pensamento crítico, uso prático de inteligência artificial, criação de prompts, programação com IA assistida (SDD, TDD), Python, RAG, tools, MCP, Git e GitHub, banco de dados SQL, PostgreSQL, integração com APIs externas, autenticação, testes automatizados, depuração de bugs, fundamentos de segurança de aplicações, leitura de documentação técnica, comunicação clara, atenção a detalhesSuperior Incompleto / cursandoDeterminado e gosta de desafiosHorário0","datePosted":"2026-08-23T01:58:05.000000Z","validThrough":"2026-10-23T01:58:05+00:00","employmentType":["FULL_TIME"],"jobBenefits":"","industry":"","skills":"TypeScript, JavaScript, React, HTML, CSS, APIs REST, programação com IA assistida (SDD, TDD), Python, RAG, tools, MCP, Git e GitHub, banco de dados SQL, PostgreSQL, integração com APIs externas, autenticação, testes automatizados, depuração de bugs, fundamentos de segurança de aplicações, leitura de documentação técnica, aprendizado rápido, autonomia, organização, pensamento crítico, comunicação clara, atenção a detalhes","workHours":"0","salaryCurrency":"BRL","hiringOrganization":{"@type":"Organization","name":"BM VAGAS","sameAs":"","logo":"https://d2bxzineatl84k.cloudfront.net/storage/files/logos/P0JDnmDSmhB2hDgjNgu9pOqPKgukqC25InMwmNms.png"},"jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"São José dos Campos","addressRegion":"SP","addressCountry":"Brasil"}}}</script>"""

_LD_BREADCRUMB = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Início","item":"https://empregos.recrutei.com.br"},{"@type":"ListItem","position":2,"name":"SP","item":"https://empregos.recrutei.com.br/vagas/em/sp"},{"@type":"ListItem","position":3,"name":"ENGENHEIRO DE IA JR","item":"https://empregos.recrutei.com.br/vaga/bm-vagas/155283-engenheiro-de-ia-jr"}]}</script>"""

URL_REMOTA = f"{PORTAL_URL}/vaga/gex-corporation/158928-analista-de-atendimento"
URL_NATAL = (f"{PORTAL_URL}/vaga/elo-solucoes-em-rh/158510-estagio-em-"
             "atendimento-academia-de-alto-padrao-em-natalrn")
URL_RN = f"{PORTAL_URL}/vagas/em/rn"
URL_FORTALEZA = f"{PORTAL_URL}/vagas/em/fortaleza-ce"

_TITULO_RE = re.compile(r'(class="job-title">)[^<]*(</a>)')


def _pagina(*cards: str) -> str:
    """Envolve os cards no esqueleto da listagem, como o portal devolve."""
    return ('<html><body><div class="row">' + "".join(cards)
            + "</div></body></html>")


def _com_id(card: str, identificador: str) -> str:
    """O mesmo card com outro id, para exercitar dedupe e paginacao."""
    return re.sub(r"/(\d{6})-", f"/{identificador}-", card)


def _com_titulo(card: str, titulo: str) -> str:
    return _TITULO_RE.sub(lambda m: m.group(1) + titulo + m.group(2), card)


def _cheia(inicio: int = 0) -> str:
    """Pagina cheia de PAGE_SIZE cards distintos.

    Pagina cheia importa porque `_listar` so pede a proxima quando a atual
    encheu: com menos de PAGE_SIZE ele para, achando que acabou.
    """
    return _pagina(*[_com_id(CARD_REMOTO, str(900000 + inicio + i))
                     for i in range(PAGE_SIZE)])


def _detalhe(posting: str = "", breadcrumb: bool = True) -> str:
    """A pagina da vaga, reduzida ao que o coletor le."""
    partes = [posting or _LD_JOB_POSTING]
    if breadcrumb:
        # O breadcrumb vem ANTES na pagina real; e o distrator do seletor.
        partes.insert(0, _LD_BREADCRUMB)
    return "<html><head>" + "".join(partes) + "</head><body></body></html>"


class _Resposta:
    """O que `PoliteSession.get` devolve, reduzido ao que o coletor le."""

    def __init__(self, text: str, url: str) -> None:
        self.text = text
        self.url = url


class _Sessao:
    """Substitui a PoliteSession. Nenhum teste toca em rede.

    O dicionario vai de URL para corpo; URL que nao esta nele devolve None --
    que e como a sessao de verdade avisa que desistiu, e tambem como o portal
    encerra a paginacao (pagina alem do fim responde 200 sem card, e este
    dicionario simplesmente nao a tem).
    """

    def __init__(self, respostas: dict | None = None) -> None:
        self.respostas = dict(respostas or {})
        self.chamadas: list[str] = []
        self.request_count = 0

    def get(self, url, **kwargs):
        self.chamadas.append(url)
        self.request_count += 1
        corpo = self.respostas.get(url)
        if corpo is None:
            return None
        return _Resposta(corpo, url)


def _fonte(sessao, **ajustes):
    return RecruteiSource(session=sessao, settings=Settings(**ajustes))


def _parse(card: str):
    return RecruteiSource(session=None,
                          settings=Settings())._parse_page(_pagina(card))


# ---- parser

def test_parse_mapeia_campos():
    (vaga,) = _parse(CARD_REMOTO)
    assert vaga.source == "recrutei"
    assert vaga.external_id == "158928"
    assert vaga.title == "Analista de Atendimento"
    assert vaga.company == "GEX Corporation"
    assert vaga.location == "Brasil"
    assert vaga.workplace_type == REMOTO
    assert vaga.url == URL_REMOTA


def test_query_de_rastreio_sai_da_url():
    """`?has_bot=1` e `?utm_source=` sao rastreio; a pagina responde sem eles."""
    assert "?" not in _parse(CARD_REMOTO)[0].url
    assert "has_bot" in CARD_REMOTO  # o recorte e mesmo o que o portal manda


def test_url_da_vaga_serve_para_o_discord():
    assert url_valida(_parse(CARD_REMOTO)[0].url)


def test_id_sai_do_caminho_da_url():
    (vaga,) = _parse(CARD_NATAL)
    assert vaga.external_id == "158510"
    assert vaga.url == URL_NATAL


def test_card_sem_titulo_e_ignorado():
    assert _parse(_com_titulo(CARD_REMOTO, "")) == []


def test_card_sem_id_no_caminho_e_ignorado():
    quebrado = CARD_REMOTO.replace("158928-analista-de-atendimento",
                                   "analista-de-atendimento")
    assert _parse(quebrado) == []


def test_pagina_sem_card_devolve_vazio():
    assert _parse("<p>Nenhuma vaga encontrada</p>") == []


def test_empresa_local_e_data_vem_de_paragrafos_irmaos():
    """Os tres sao <p> no mesmo bloco; so o icone os distingue."""
    (vaga,) = _parse(CARD_NATAL)
    assert vaga.company == "ELO SOLUÇÕES EM RH"
    assert vaga.location == "Natal, RN, Brasil"
    # O <p> do salario fica entre eles e nao entra em nenhum campo.
    assert "Não informado" not in (vaga.company + vaga.location)


# ---- modalidade

def test_modalidade_remoto():
    assert _parse(CARD_REMOTO)[0].workplace_type == REMOTO


def test_modalidade_presencial():
    assert _parse(CARD_NATAL)[0].workplace_type == PRESENCIAL


def test_presencial_ou_remoto_e_hibrido_e_nao_remoto():
    """O portal separa `model=remote` de `model=presential-remote`.

    `normalize_workplace` leria o selo como REMOTO, so por achar "remoto" na
    string, e a vaga entraria no aviso nacional sem o portal ter dito que e
    remota. Por isso o de-para do coletor e explicito.
    """
    assert _parse(CARD_PRESENCIAL_OU_REMOTO)[0].workplace_type == HIBRIDO


def test_selo_de_regime_nao_vira_modalidade():
    """O selo de regime vem antes: "Estagio", "CLT", "Pessoa Juridica"."""
    assert "Estágio" in CARD_NATAL and "CLT" in CARD_EUSEBIO
    assert _parse(CARD_NATAL)[0].workplace_type == PRESENCIAL
    assert _parse(CARD_EUSEBIO)[0].workplace_type == PRESENCIAL


def test_card_sem_selo_de_modalidade_fica_nao_informado():
    sem_selo = CARD_REMOTO.replace(
        '<span class="badge bg-primary text-white">Remoto</span>', "")
    assert _parse(sem_selo)[0].workplace_type == NAO_INFORMADO


# ---- data

def test_data_relativa_em_dias():
    (vaga,) = _parse(CARD_NATAL)  # "Publicada há 4 dias"
    assert vaga.published_date == (date.today() - timedelta(days=4)).isoformat()


def test_data_em_horas_e_hoje():
    """4 dos 134 cards de remotas vieram datados em horas."""
    (vaga,) = _parse(CARD_REMOTO)  # "Publicada há 6 horas"
    assert vaga.published_date == date.today().isoformat()


def test_vaga_sem_data_sobrevive_ao_filtro_de_idade():
    sem_data = CARD_REMOTO.replace("Publicada há 6 horas", "")
    (vaga,) = _parse(sem_data)
    assert vaga.published_date == ""
    assert filtrar_recentes([vaga], 30) == [vaga]


# ---- a descricao, que so a pagina da vaga tem

def test_descricao_vem_do_json_ld_da_pagina():
    (vaga,) = _parse(CARD_REMOTO)
    sessao = _Sessao({URL_REMOTA: _detalhe()})
    _fonte(sessao)._preencher_detalhe(vaga)
    assert "BM VAGAS em parceria" in vaga.description
    assert sessao.chamadas == [URL_REMOTA]


def test_descricao_pode_ir_para_o_discord():
    """Os termos do portal nao proibem reproduzir -- ao contrario do InfoJobs."""
    assert _parse(CARD_REMOTO)[0].reproduzir_descricao is True


def test_data_exata_do_json_ld_sobrescreve_a_do_card():
    (vaga,) = _parse(CARD_REMOTO)
    assert vaga.published_date == date.today().isoformat()
    _fonte(_Sessao({URL_REMOTA: _detalhe()}))._preencher_detalhe(vaga)
    assert vaga.published_date == "2026-08-23"  # `datePosted` do JSON-LD


def test_pagina_sem_json_ld_nao_derruba():
    (vaga,) = _parse(CARD_REMOTO)
    _fonte(_Sessao({URL_REMOTA: "<html><body>vaga encerrada</body></html>"}
                   ))._preencher_detalhe(vaga)
    assert vaga.description == ""


def test_json_ld_quebrado_nao_derruba():
    quebrado = '<script type="application/ld+json">{"@type": </script>'
    (vaga,) = _parse(CARD_REMOTO)
    _fonte(_Sessao({URL_REMOTA: _detalhe(quebrado)}))._preencher_detalhe(vaga)
    assert vaga.description == ""


def test_breadcrumb_nao_e_confundido_com_a_vaga():
    """A pagina traz dois JSON-LD, e o BreadcrumbList vem primeiro."""
    (vaga,) = _parse(CARD_REMOTO)
    pagina = "<html><head>" + _LD_BREADCRUMB + "</head></html>"
    _fonte(_Sessao({URL_REMOTA: pagina}))._preencher_detalhe(vaga)
    assert vaga.description == ""


def test_falha_de_rede_na_pagina_da_vaga_nao_derruba():
    (vaga,) = _parse(CARD_REMOTO)
    _fonte(_Sessao())._preencher_detalhe(vaga)
    assert vaga.description == ""


def test_e_a_descricao_que_faz_a_vaga_passar_no_portao_tech():
    """O motivo de existir a requisicao por vaga, em um teste.

    "ENGENHEIRO DE IA JR" e reprovado com o titulo sozinho e aprovado com a
    descricao. Sem abrir a pagina, esta fonte perderia justamente as vagas que
    o funil procura.
    """
    (vaga,) = _parse(_com_titulo(CARD_REMOTO, "ENGENHEIRO DE IA JR"))
    classificador = default_classifier()
    assert classificador.is_tech(vaga.title, vaga.description) is False

    _fonte(_Sessao({URL_REMOTA: _detalhe()}))._preencher_detalhe(vaga)
    assert classificador.is_tech(vaga.title, vaga.description) is True


# ---- senioridade

def test_nivel_nao_vem_da_fonte():
    """O card nao declara nivel; quem decide e o regex de `seniority.py`."""
    (vaga,) = _parse(CARD_REMOTO)
    assert vaga.seniority == ""
    assert filter_entry_level([vaga]) == []  # "Analista de Atendimento"


# ---- pre-filtro: quem nao passaria no pipeline nao vira requisicao

def test_vaga_sem_nivel_de_entrada_nao_abre_pagina():
    sessao = _Sessao({LISTAGEM_REMOTA: _pagina(CARD_REMOTO)})
    assert _fonte(sessao).fetch([]) == []
    # As tres listagens, e nenhuma pagina de vaga.
    assert sessao.chamadas == [LISTAGEM_REMOTA, URL_RN, URL_FORTALEZA]


def test_presencial_fora_dos_locais_nao_abre_pagina():
    """Junior, recente, e ainda assim descartada: e presencial em Sao Paulo."""
    junior = _com_titulo(CARD_PRESENCIAL_OU_REMOTO, "Desenvolvedor Junior")
    sessao = _Sessao({LISTAGEM_REMOTA: _pagina(junior)})
    assert _fonte(sessao).fetch([]) == []
    assert sessao.chamadas == [LISTAGEM_REMOTA, URL_RN, URL_FORTALEZA]


def test_presencial_no_local_abre_pagina():
    """CARD_NATAL e estagio presencial em Natal: o local salva a vaga."""
    sessao = _Sessao({URL_RN: _pagina(CARD_NATAL),
                      URL_NATAL: _detalhe()})
    (vaga,) = _fonte(sessao).fetch([])
    assert vaga.external_id == "158510"
    assert URL_NATAL in sessao.chamadas


def test_pre_filtro_respeita_o_corte_de_idade():
    velha = CARD_NATAL.replace("Publicada há 4 dias", "Publicada há 8 meses")
    sessao = _Sessao({URL_RN: _pagina(velha)})
    assert _fonte(sessao, dias_max=60).fetch([]) == []


# ---- por local

def test_fetch_pede_as_duas_consultas_por_local():
    sessao = _Sessao()
    _fonte(sessao).fetch([])
    assert sessao.chamadas == [LISTAGEM_REMOTA, URL_RN, URL_FORTALEZA]


def test_local_consultado_fica_vazio():
    """`fortaleza-ce` traz Eusebio e Maracanau: a consulta nao prova o local."""
    sessao = _Sessao({URL_FORTALEZA: _pagina(CARD_NATAL),
                      URL_NATAL: _detalhe()})
    (vaga,) = _fonte(sessao).fetch([])
    assert vaga.local_consultado == ""


def test_texto_do_card_prova_natal_e_nao_prova_eusebio():
    (natal,) = _parse(CARD_NATAL)
    (eusebio,) = _parse(CARD_EUSEBIO)
    locais = [RIO_GRANDE_DO_NORTE, FORTALEZA]
    assert serve_presencialmente(natal, locais) is True
    assert serve_presencialmente(eusebio, locais) is False


def test_caminhos_configurados_dos_locais():
    assert RIO_GRANDE_DO_NORTE.recrutei_caminhos == ("rn",)
    assert FORTALEZA.recrutei_caminhos == ("fortaleza-ce",)


# ---- paginacao

def test_segue_para_a_pagina_seguinte_quando_a_atual_enche():
    sessao = _Sessao({LISTAGEM_REMOTA: _cheia(),
                      f"{LISTAGEM_REMOTA}?page=2": _pagina(CARD_NATAL)})
    listadas = _fonte(sessao)._listar(LISTAGEM_REMOTA)
    assert len(listadas) == PAGE_SIZE + 1
    assert sessao.chamadas[:2] == [LISTAGEM_REMOTA,
                                   f"{LISTAGEM_REMOTA}?page=2"]


def test_pagina_incompleta_encerra():
    sessao = _Sessao({LISTAGEM_REMOTA: _pagina(CARD_REMOTO)})
    assert len(_fonte(sessao)._listar(LISTAGEM_REMOTA)) == 1
    assert sessao.request_count == 1


def test_pagina_vazia_encerra():
    """`?page=99` responde 200 sem card nenhum, e nao repete a primeira."""
    sessao = _Sessao({LISTAGEM_REMOTA: _cheia(),
                      f"{LISTAGEM_REMOTA}?page=2": _pagina()})
    assert len(_fonte(sessao)._listar(LISTAGEM_REMOTA)) == PAGE_SIZE
    assert sessao.request_count == 2


def test_pagina_repetida_encerra():
    sessao = _Sessao({LISTAGEM_REMOTA: _cheia(),
                      f"{LISTAGEM_REMOTA}?page=2": _cheia()})
    assert len(_fonte(sessao)._listar(LISTAGEM_REMOTA)) == PAGE_SIZE
    assert sessao.request_count == 2


def test_respeita_o_teto_de_paginas():
    respostas = {LISTAGEM_REMOTA: _cheia()}
    respostas.update({f"{LISTAGEM_REMOTA}?page={p}": _cheia(p * PAGE_SIZE)
                      for p in range(2, MAX_PAGINAS + 5)})
    sessao = _Sessao(respostas)
    _fonte(sessao)._listar(LISTAGEM_REMOTA)
    assert sessao.request_count == MAX_PAGINAS


def test_a_mesma_vaga_nas_duas_listagens_abre_a_pagina_uma_vez():
    """Remota sediada em Natal aparece na listagem nacional e na do RN."""
    remota_em_natal = _com_titulo(CARD_NATAL, "Desenvolvedor Junior").replace(
        '<span class="badge bg-primary text-white">Presencial</span>',
        '<span class="badge bg-primary text-white">Remoto</span>')
    sessao = _Sessao({LISTAGEM_REMOTA: _pagina(remota_em_natal),
                      URL_RN: _pagina(remota_em_natal),
                      URL_NATAL: _detalhe()})
    vagas = _fonte(sessao).fetch([])
    assert len(vagas) == 1
    assert sessao.chamadas.count(URL_NATAL) == 1


# ---- limites

def test_falha_de_rede_encerra_sem_derrubar_a_coleta():
    sessao = _Sessao()
    assert _fonte(sessao)._listar(LISTAGEM_REMOTA) == []
    assert sessao.request_count == 1


def test_fetch_ignora_os_termos_e_fecha_as_estatisticas():
    sessao = _Sessao({URL_RN: _pagina(CARD_NATAL), URL_NATAL: _detalhe()})
    fonte = _fonte(sessao)
    vagas = fonte.fetch(["desenvolvedor junior", "qa junior"])
    assert len(vagas) == 1
    assert fonte.stats.raw_jobs == 1
    assert fonte.stats.requests_made == sessao.request_count
    assert fonte.stats.errors == []


def test_fetch_term_nao_e_usado():
    """O `robots.txt` bloqueia `/busca?keyword=`; nao ha busca textual."""
    sessao = _Sessao()
    assert _fonte(sessao).fetch_term("desenvolvedor junior") == []
    assert sessao.chamadas == []
