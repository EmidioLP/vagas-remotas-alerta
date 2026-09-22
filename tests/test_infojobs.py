"""Testes do coletor do InfoJobs, com recortes reais do portal (offline)."""

from __future__ import annotations

import json
from datetime import date, timedelta

from scraper.config import Settings
from scraper.datas import filtrar_recentes
from scraper.locais import (FORTALEZA, RIO_GRANDE_DO_NORTE,
                            serve_presencialmente)
from scraper.models import HIBRIDO, NAO_INFORMADO, PRESENCIAL, REMOTO
from scraper.notificacao import montar_embed, url_valida
from scraper.seniority import filter_entry_level
from scraper.sources.infojobs import (FRAGMENTO_URL, PAGE_SIZE, PORTAL_URL,
                                      InfoJobsSource, slugify_term)

# Cards capturados em 22/09/2026, das listagens
#   /vagas-de-emprego-desenvolvedor-junior-trabalho-home-office.aspx
#   /vagas-de-emprego-analista-em-natal,-rn.aspx
#   /vagas-de-emprego-analista-em-fortaleza,-ce.aspx
# Dois cortes, e so: o `d` dos <svg> (icones, centenas de bytes cada) e o
# <span> do selo de verificacao, que so carrega tooltip. O resto, inclusive a
# indentacao colapsada e a descricao truncada pelo proprio portal, e como
# chegou.

# Vaga remota. A empresa tem pagina propria no portal (`/printi`), e o local e
# "Todo Brasil" -- o rotulo que o InfoJobs usa em vaga sem cidade.
CARD_REMOTO = """<div class="pt-24 px-24 cursor-pointer js_vacancyLoad js_rowCard js_cardLink" data-href="/vaga-de-quality-engineer-pleno-commerce-em-__12027162.aspx" data-id="12027162" id="vacancy12027162">
<div class="d-flex flex-wrap gap-8">
<div class="js_date" data-value="2026/09/17 11:14:00" hidden="">
<div class="tag mb-2 tag-outline-premium tag-sm">
<span>
NOVA
</span>
</div>
</div>
</div>
<div class="d-flex gap-8 justify-content-between">
<a class="text-decoration-none" href="/vaga-de-quality-engineer-pleno-commerce-em-__12027162.aspx">
<h2 class="h3 font-weight-bold text-body mb-2 js_vacancyTitle">
Quality Engineer Pleno - E-Commerce
</h2>
</a>
<div class="text-medium small text-nowrap">
17 set
</div>
</div>
<div class="d-flex align-items-baseline">
<div class="mr-8">
<div class="text-nowrap" style="line-height:24px;font-size:16px">
<span class="font-weight-bold text-body">4,4</span>
<svg></svg>
</div>
</div>
<div class="text-body">
<a class="text-body text-decoration-none" href="https://www.infojobs.com.br/printi">
<span class="text-nowrap">
PRINTI
</span>
</a>
</div>
</div>
<div class="mb-8">
Todo Brasil
</div>
<div class="d-inline-flex flex-wrap mb-8 text-medium" style="gap: 2px 16px">
<div>
<svg></svg>
A combinar
</div>
<div>
<svg></svg>
Ensino Superior
</div>
<div>
<svg></svg>
Home office
</div>
</div>
<div class="text-medium">
Missão do cargo: Desenvolver, manter e aprimorar estratégias de qualidade e automação de testes que garantam a confiabilidade, estabilidade e seguranç...
</div>
</div>"""

# Mesma listagem: aqui o anunciante nao se identifica, e nao ha <a> nenhum.
CARD_CONFIDENCIAL = """<div class="pt-24 px-24 cursor-pointer js_vacancyLoad js_rowCard js_cardLink" data-href="/vaga-de-desenvolvedor-plc-junior-pleno-em-sao-paulo__12005988.aspx" data-id="12005988" id="vacancy12005988">
<div class="d-flex flex-wrap gap-8">
<div class="js_date" data-value="2026/09/11 09:13:00" hidden="">
<div class="tag mb-2 tag-outline-premium tag-sm">
<span>
NOVA
</span>
</div>
</div>
</div>
<div class="d-flex gap-8 justify-content-between">
<a class="text-decoration-none" href="/vaga-de-desenvolvedor-plc-junior-pleno-em-sao-paulo__12005988.aspx">
<h2 class="h3 font-weight-bold text-body mb-2 js_vacancyTitle">
Desenvolvedor PLC JÚNIOR E PLENO
</h2>
</a>
<div class="text-medium small text-nowrap">
11 set
</div>
</div>
<div class="d-flex align-items-baseline">
<div class="text-body">
Empresa
<span class="text-nowrap">
confidencial
</span>
</div>
</div>
<div class="mb-8">
Indaiatuba - SP<span class="js_divUserVagaDistance" hidden="">, <span class="js_UserVagaDistance" data-vagalatitude="-23.1045928" data-vagalongitude="-47.1653253">0</span> Km de você.</span>
</div>
<div class="d-inline-flex flex-wrap mb-8 text-medium" style="gap: 2px 16px">
<div>
<svg></svg>
A combinar
</div>
<div>
<svg></svg>
Ensino Superior
</div>
<div>
<svg></svg>
Home office
</div>
</div>
<div class="text-medium">
*Desenvolvedor de Sistemas JÚNIOR (PLC) - Remoto* - Base de Contratação: Indaiatuba/SP
Salário à Combinar
Requisitos:
Formação completa em Engenharia...
</div>
</div>"""

# Presencial em Natal. O nome da empresa vem quebrado em dois nos por causa do
# selo, e o local carrega o <span hidden> da distancia.
CARD_NATAL = """<div class="pt-24 px-24 cursor-pointer js_vacancyLoad js_rowCard js_cardLink" data-href="/vaga-de-analista-suporte-ti-lagoa-nova,-natal-em-rio-grande-do-norte__11454526.aspx" data-id="11454526" id="vacancy11454526">
<div class="d-flex flex-wrap gap-8">
<div class="js_date" data-value="2026/09/21 12:44:00" hidden="">
<div class="tag mb-2 tag-outline-premium tag-sm">
<span>
NOVA
</span>
</div>
</div>
</div>
<div class="d-flex gap-8 justify-content-between">
<a class="text-decoration-none" href="/vaga-de-analista-suporte-ti-lagoa-nova,-natal-em-rio-grande-do-norte__11454526.aspx">
<h2 class="h3 font-weight-bold text-body mb-2 js_vacancyTitle">
Analista De Suporte TI -Lagoa Nova, Natal
</h2>
</a>
<div class="text-medium small text-nowrap">
Ontem
</div>
</div>
<div class="d-flex align-items-baseline">
<div class="mr-8">
<div class="text-nowrap" style="line-height:24px;font-size:16px">
<span class="font-weight-bold text-body">2,5</span>
<svg></svg>
</div>
</div>
<div class="text-body">
<a class="text-body text-decoration-none" href="https://www.infojobs.com.br/empresa-grupo-easy__-57056.aspx">
Grupo
<span class="text-nowrap">
Easy
</span>
</a>
</div>
</div>
<div class="mb-8">
Natal - RN<span class="js_divUserVagaDistance" hidden="">, <span class="js_UserVagaDistance" data-vagalatitude="-5.8264813" data-vagalongitude="-35.201173">0</span> Km de você.</span>
</div>
<div class="d-inline-flex flex-wrap mb-8 text-medium" style="gap: 2px 16px">
<div>
<svg></svg>
A combinar
</div>
<div>
<svg></svg>
Entre 1 e 3 anos
</div>
<div>
<svg></svg>
Curso Técnico
</div>
<div>
<svg></svg>
Presencial
</div>
</div>
<div class="text-medium">
Projetar e prestar manutenção em redes de computadores;
Responsável pela segurança dos recursos da rede (dados e serviços);
Prevenção contra invasões ...
</div>
</div>"""

# Hibrida em Fortaleza. O InfoJobs distingue as tres modalidades no card.
CARD_HIBRIDO = """<div class="pt-24 px-24 cursor-pointer js_vacancyLoad js_rowCard js_cardLink" data-href="/vaga-de-analista-fiscal-em-ceara__11625524.aspx" data-id="11625524" id="vacancy11625524">
<div class="d-flex flex-wrap gap-8">
<div class="js_date" data-value="2026/09/16 03:43:00" hidden="">
<div class="tag mb-2 tag-outline-premium tag-sm">
<span>

NOVA

</span>
</div>
</div>
</div>
<div class="d-flex gap-8 justify-content-between">
<a class="text-decoration-none" href="/vaga-de-analista-fiscal-em-ceara__11625524.aspx">
<h2 class="h3 font-weight-bold text-body mb-2 js_vacancyTitle">

Analista Fiscal

</h2>
</a>
<div class="text-medium small text-nowrap">

16 set

</div>
</div>
<div class="d-flex align-items-baseline">
<div class="text-body">
<a class="text-body text-decoration-none" href="https://www.infojobs.com.br/empresa-grupo-maktura__827291.aspx">

GRUPO

<span class="text-nowrap">

MAKTURA

</span>
</a>
</div>
</div>
<div class="mb-8">

Fortaleza - CE<span class="js_divUserVagaDistance" hidden="">, <span class="js_UserVagaDistance" data-vagalatitude="-3.7959878" data-vagalongitude="-38.4901263">0</span> Km de você.</span>
</div>
<div class="d-inline-flex flex-wrap mb-8 text-medium" style="gap: 2px 16px">
<div>
<svg></svg>

R$ 4.300,00

</div>
<div>
<svg></svg>

Entre 1 e 3 anos

</div>
<div>
<svg></svg>

Ensino Superior

</div>
<div>
<svg></svg>

Híbrido

</div>
</div>
<div class="text-medium">

Oportunidade | Área Contábil e Fiscal
Olá, candidatos!
Estamos com uma vaga no escritório de contabilidade para atuar no departamento Fiscal , com foc...

</div>
</div>"""


def _grid(*cards: str) -> str:
    """Envolve os cards no container de resultados, como o portal devolve.

    E o mesmo container nas duas superficies: a pagina HTML e o
    `listFragmentHTML` do fragmento abrem os dois com `js_vacanciesGridFragment`.
    """
    return ('<div class="js_vacanciesGridFragment mb-16">'
            + "".join(cards) + "</div>")


def _com_id(card: str, identificador: str) -> str:
    """O mesmo card com outro id, para exercitar dedupe e paginacao."""
    return card.replace("12027162", identificador)


def _cheia(inicio: int = 0) -> str:
    """Pagina cheia de 20 cards distintos.

    Pagina cheia importa porque `_paginar` so pede a proxima quando a atual
    encheu: com menos de PAGE_SIZE ele para, achando que acabou.
    """
    return _grid(*[_com_id(CARD_REMOTO, str(9000000 + inicio + i))
                   for i in range(PAGE_SIZE)])


class _Resposta:
    """O que `PoliteSession.get` devolve, reduzido ao que o coletor le."""

    def __init__(self, text: str, url: str) -> None:
        self.text = text
        self.url = url


class _Sessao:
    """Substitui a PoliteSession. Nenhum teste toca em rede.

    `paginas` alimenta o `get` (pagina 1) e `fragmentos` o `get_json` (2 em
    diante). Acabou a fila, devolve None -- que e como a sessao de verdade
    avisa que desistiu.
    """

    def __init__(self, paginas=(), fragmentos=()) -> None:
        self.paginas = list(paginas)
        self.fragmentos = list(fragmentos)
        self.chamadas: list[str] = []
        self.endpoints: list[str] = []
        self.request_count = 0

    def get(self, url, **kwargs):
        self.chamadas.append(url)
        self.request_count += 1
        if not self.paginas:
            return None
        item = self.paginas.pop(0)
        if item is None:
            return None
        # (html, url_final) quando o teste quer simular desvio; so html quando
        # o portal honrou a consulta.
        html, final = item if isinstance(item, tuple) else (item, url)
        return _Resposta(html, final)

    def get_json(self, url, params=None, **kwargs):
        self.endpoints.append(url)
        self.chamadas.append((params or {}).get("url", url))
        self.request_count += 1
        if not self.fragmentos:
            return None
        return self.fragmentos.pop(0)


def _fonte(sessao, **ajustes):
    return InfoJobsSource(session=sessao, settings=Settings(**ajustes))


def _parse(card: str, term: str = "desenvolvedor junior"):
    return InfoJobsSource(session=None, settings=Settings())._parse_page(
        _grid(card), term)


# ---- parser

def test_parse_mapeia_campos():
    (vaga,) = _parse(CARD_REMOTO)
    assert vaga.source == "infojobs"
    assert vaga.external_id == "12027162"
    assert vaga.title == "Quality Engineer Pleno - E-Commerce"
    assert vaga.company == "PRINTI"
    assert vaga.location == "Todo Brasil"
    assert vaga.search_term == "desenvolvedor junior"


def test_link_relativo_vira_absoluto():
    (vaga,) = _parse(CARD_REMOTO)
    assert vaga.url == (f"{PORTAL_URL}/vaga-de-quality-engineer-pleno"
                        "-commerce-em-__12027162.aspx")


def test_url_do_card_passa_na_validacao_do_discord():
    (vaga,) = _parse(CARD_REMOTO)
    assert url_valida(vaga.url)


def test_empresa_confidencial_nao_fica_vazia():
    """Sem <a> nenhum no bloco: ler so o link deixava a vaga sem empresa."""
    (vaga,) = _parse(CARD_CONFIDENCIAL)
    assert vaga.company == "Empresa confidencial"


def test_empresa_quebrada_pelo_selo_sai_inteira():
    """"Grupo" e "Easy" vem em nos separados por causa do selo de verificacao."""
    (vaga,) = _parse(CARD_NATAL)
    assert vaga.company == "Grupo Easy"


def test_local_ignora_a_distancia_escondida():
    """O card carrega ", 0 Km de voce" num <span hidden> dentro do local."""
    (vaga,) = _parse(CARD_NATAL)
    assert vaga.location == "Natal - RN"
    assert "Km" not in vaga.location


def test_card_sem_titulo_e_ignorado():
    sem_titulo = CARD_REMOTO.replace("js_vacancyTitle", "titulo-que-nao-existe")
    assert _parse(sem_titulo) == []


def test_card_fora_do_grid_nao_conta():
    """O rodape tem "Cargos Similares", que sao links de busca e nao vagas."""
    fonte = InfoJobsSource(session=None, settings=Settings())
    solto = f'<div class="card">{CARD_REMOTO}</div>'
    assert fonte._parse_page(solto, "x") == []


def test_pagina_sem_card_nenhum():
    fonte = InfoJobsSource(session=None, settings=Settings())
    assert fonte._parse_page("<html><body></body></html>", "x") == []


# ---- a descricao, que os termos do portal proibem reproduzir

def test_descricao_nunca_e_reproduzida():
    for card in (CARD_REMOTO, CARD_NATAL, CARD_HIBRIDO, CARD_CONFIDENCIAL):
        (vaga,) = _parse(card)
        assert vaga.reproduzir_descricao is False


def test_descricao_continua_classificando_a_vaga():
    """Ela nao vai para o Discord, mas ainda alimenta o portao de relevancia."""
    (vaga,) = _parse(CARD_REMOTO)
    assert "automacao de testes" in vaga.searchable_text()


def test_descricao_nao_chega_no_embed_do_discord():
    """A garantia que os termos do portal exigem, verificada no card final."""
    (vaga,) = _parse(CARD_NATAL)
    embed = montar_embed(vaga)
    assert not embed.get("description")
    assert "Projetar e prestar" not in json.dumps(embed, ensure_ascii=False)
    # o que o aviso leva, e so isso
    assert [c["name"] for c in embed["fields"]] == [
        "Empresa", "Modalidade", "Local", "Publicada em"]


def test_descricao_nao_pega_a_tira_de_atributos():
    """A tira ("A combinar", "Home office") tambem tem a classe text-medium."""
    (vaga,) = _parse(CARD_REMOTO)
    assert not vaga.description.startswith("A combinar")
    assert vaga.description.startswith("Missão do cargo")


# ---- modalidade

def test_home_office_vira_remoto():
    (vaga,) = _parse(CARD_REMOTO)
    assert vaga.workplace_type == REMOTO


def test_presencial_e_afirmado():
    (vaga,) = _parse(CARD_NATAL)
    assert vaga.workplace_type == PRESENCIAL


def test_hibrido_e_afirmado():
    """Diferente do Vagas.com, aqui o card distingue as tres modalidades."""
    (vaga,) = _parse(CARD_HIBRIDO)
    assert vaga.workplace_type == HIBRIDO


def test_sem_tira_de_atributos_fica_nao_informado():
    """Silencio nao e prova de remoto -- a vaga cai no filtro, e esta certo."""
    sem_tira = CARD_REMOTO.replace("d-inline-flex", "d-none")
    (vaga,) = _parse(sem_tira)
    assert vaga.workplace_type == NAO_INFORMADO


# ---- data

def test_data_sai_do_campo_escondido():
    """`data-value` vem "2026/09/17 11:14:00"; so a barra precisa virar hifen."""
    (vaga,) = _parse(CARD_REMOTO)
    assert vaga.published_date == "2026-09-17"


def test_ontem_vem_do_texto_quando_falta_o_campo():
    sem_campo = CARD_NATAL.replace('class="js_date"', 'class="js_date_ausente"')
    (vaga,) = _parse(sem_campo)
    assert vaga.published_date == (date.today() - timedelta(days=1)).isoformat()


def test_mes_por_extenso_nao_vira_data():
    """"17 set" nao tem ano; inventar um seria afirmar idade que o portal nao deu."""
    sem_campo = CARD_REMOTO.replace('class="js_date"', 'class="js_date_ausente"')
    (vaga,) = _parse(sem_campo)
    assert vaga.published_date == ""


def test_vaga_sem_data_sobrevive_ao_filtro_de_idade():
    sem_campo = CARD_REMOTO.replace('class="js_date"', 'class="js_date_ausente"')
    (vaga,) = _parse(sem_campo)
    assert filtrar_recentes([vaga], dias_max=60) == [vaga]


# ---- senioridade

def test_senioridade_fica_para_o_regex():
    """O portal nao tem nivel "Junior" no filtro `im`, entao nada e declarado."""
    (vaga,) = _parse(CARD_REMOTO)
    assert vaga.seniority == ""
    # "Pleno" no titulo: quem derruba e o regex, nao a fonte.
    assert filter_entry_level([vaga]) == []


# ---- por local

def test_local_consultado_fica_sempre_vazio():
    """A consulta por cidade e frouxa demais para valer como prova."""
    sessao = _Sessao(paginas=[_grid(CARD_NATAL)])
    vagas = _fonte(sessao).fetch_local(RIO_GRANDE_DO_NORTE,
                                       ["analista de dados junior"])
    assert vagas and all(v.local_consultado == "" for v in vagas)


def test_texto_do_card_prova_natal():
    (vaga,) = _parse(CARD_NATAL)
    assert serve_presencialmente(vaga, [RIO_GRANDE_DO_NORTE])


def test_texto_do_card_prova_fortaleza():
    (vaga,) = _parse(CARD_HIBRIDO)
    assert serve_presencialmente(vaga, [FORTALEZA])


def test_vaga_de_todo_brasil_nao_prova_local():
    """Medido: `natal,-rn` devolveu 88 cards, 83 deles fora de Natal.

    A mais comum das intrusas e justamente "Todo Brasil" (110 nas tres
    cidades). Ela entra como remota, que e o que ela e -- nunca como vaga do RN.
    """
    (vaga,) = _parse(CARD_REMOTO)
    assert not serve_presencialmente(vaga, [RIO_GRANDE_DO_NORTE, FORTALEZA])


def test_fetch_local_pede_as_cidades_com_a_uf():
    """Sem a UF o portal desvia para Sao Paulo; a virgula e literal na URL."""
    sessao = _Sessao(paginas=[_grid(CARD_NATAL), _grid(CARD_NATAL)])
    _fonte(sessao).fetch_local(RIO_GRANDE_DO_NORTE, ["qa junior"])
    assert sessao.chamadas == [
        f"{PORTAL_URL}/vagas-de-emprego-qa-junior-em-natal,-rn.aspx",
        f"{PORTAL_URL}/vagas-de-emprego-qa-junior-em-mossoro,-rn.aspx",
    ]


def test_fetch_term_usa_a_listagem_de_home_office():
    sessao = _Sessao(paginas=[_grid(CARD_REMOTO)])
    _fonte(sessao).fetch_term("desenvolvedor junior")
    assert sessao.chamadas == [
        f"{PORTAL_URL}/vagas-de-emprego-desenvolvedor-junior"
        "-trabalho-home-office.aspx"]


def test_slug_do_termo():
    assert slugify_term("análise de dados júnior") == "analise-de-dados-junior"


# ---- o desvio silencioso para Sao Paulo

def test_desvio_descarta_a_consulta_inteira():
    """`/empregos-em-natal.aspx` responde 200 com Sao Paulo, e nao 404.

    Aceitar a resposta poria vaga de outro estado no aviso -- e o erro do
    Trampos em outra roupa.
    """
    sessao = _Sessao(paginas=[
        (_grid(CARD_REMOTO), f"{PORTAL_URL}/empregos-em-sao-paulo.aspx")])
    assert _fonte(sessao).fetch_local(RIO_GRANDE_DO_NORTE, ["qa junior"]) == []


def test_desvio_nao_impede_a_proxima_consulta():
    sessao = _Sessao(paginas=[
        (_grid(CARD_REMOTO), f"{PORTAL_URL}/empregos-em-sao-paulo.aspx"),
        _grid(CARD_NATAL),
    ])
    vagas = _fonte(sessao).fetch_local(RIO_GRANDE_DO_NORTE, ["qa junior"])
    assert [v.external_id for v in vagas] == ["11454526"]


def test_consulta_honrada_e_aceita():
    url = f"{PORTAL_URL}/vagas-de-emprego-qa-junior-em-natal,-rn.aspx"
    sessao = _Sessao(paginas=[(_grid(CARD_NATAL), url)])
    assert len(_fonte(sessao).fetch_local(RIO_GRANDE_DO_NORTE, ["qa junior"])) == 1


# ---- paginacao

def test_pagina_2_vem_do_fragmento():
    sessao = _Sessao(
        paginas=[_cheia()],
        fragmentos=[{"eof": True, "listFragmentHTML": _grid(CARD_NATAL)}],
    )
    vagas = _fonte(sessao).fetch_term("estagio desenvolvimento")
    assert len(vagas) == PAGE_SIZE + 1
    alvo = (f"{PORTAL_URL}/vagas-de-emprego-estagio-desenvolvimento"
            "-trabalho-home-office.aspx?page=2")
    assert sessao.chamadas[1] == alvo
    # `page` so funciona pelo fragmento: na propria pagina HTML ele e ignorado
    # e o portal devolve de novo a primeira vaga.
    assert sessao.endpoints == [FRAGMENTO_URL]


def test_para_no_eof():
    sessao = _Sessao(
        paginas=[_cheia()],
        fragmentos=[{"eof": True, "listFragmentHTML": _cheia(inicio=100)},
                    {"eof": False, "listFragmentHTML": _cheia(inicio=200)}],
    )
    vagas = _fonte(sessao).fetch_term("estagio desenvolvimento")
    assert len(vagas) == PAGE_SIZE * 2
    assert len(sessao.fragmentos) == 1  # a terceira pagina nao foi pedida


def test_para_quando_a_pagina_nao_enche():
    sessao = _Sessao(paginas=[_grid(CARD_REMOTO)])
    _fonte(sessao).fetch_term("devops junior")
    assert sessao.request_count == 1


def test_pagina_repetida_encerra():
    sessao = _Sessao(
        paginas=[_cheia()],
        fragmentos=[{"eof": False, "listFragmentHTML": _cheia()}],
    )
    vagas = _fonte(sessao).fetch_term("estagio desenvolvimento")
    assert len(vagas) == PAGE_SIZE


def test_respeita_o_teto_de_paginas():
    sessao = _Sessao(
        paginas=[_cheia()],
        fragmentos=[{"eof": False, "listFragmentHTML": _cheia(inicio=100 * n)}
                    for n in range(1, 9)],
    )
    _fonte(sessao, max_pages_per_term=3).fetch_term("estagio desenvolvimento")
    assert sessao.request_count == 3


def test_fragmento_sem_envelope_encerra():
    sessao = _Sessao(paginas=[_cheia()], fragmentos=[["lista", "inesperada"]])
    assert len(_fonte(sessao).fetch_term("x")) == PAGE_SIZE


# ---- limites

def test_falha_de_rede_encerra_sem_derrubar_a_coleta():
    sessao = _Sessao(paginas=[None])
    assert _fonte(sessao).fetch_term("qa junior") == []


def test_fetch_isola_falha_de_um_termo():
    sessao = _Sessao(paginas=[None, _grid(CARD_REMOTO)])
    fonte = _fonte(sessao, locais_presenciais=[])
    vagas = fonte.fetch(["qa junior", "devops junior"])
    assert [v.external_id for v in vagas] == ["12027162"]
    assert fonte.stats.raw_jobs == 1
    assert fonte.stats.requests_made == 2
