"""Parser da Solides, com recortes reais da API (offline)."""

from __future__ import annotations

import pytest

from scraper.config import Settings
from scraper.locais import (
    FORTALEZA,
    RIO_GRANDE_DO_NORTE,
    Local,
    serve_presencialmente,
)
from scraper.models import PRESENCIAL, REMOTO
from scraper.seniority import filter_entry_level
from scraper.sources.solides import (
    API_URL,
    FILTROS,
    MAX_PAGINAS,
    PAGE_SIZE,
    PORTAL_URL,
    SolidesSource,
    url_publica,
)

# Recortes reais de
# GET /jobs/v3/portal-vacancies?occupationAreas=tecnologia&seniorities=junior
# capturados em 21/09/2026. A descricao vem cortada; o resto e como chegou.

# Vaga remota. Repare que `homeOffice` e False mesmo com `jobType` "remoto":
# e o `jobType` que carrega a modalidade neste portal.
REMOTA = {
    "id": 924564,
    "title": "Analista de Suporte e Implantação - Hospitalar ",
    "description": "<p><strong>Quem somos:</strong></p>\n<p>Nós somos a "
                   "Inovadora. Uma das principais empresas de software na "
                   "área da saúde e assistência social do Brasil.</p>",
    "companyName": "INOVADORA SISTEMAS DE GESTAO LTDA",
    "state": {"id": 22, "name": "Santa Catarina", "code": "SC"},
    "city": {"id": 4447, "name": "Joaçaba", "state_id": 22},
    "slug": "inovadorasistemas",
    "redirectLink": "https://inovadorasistemas.solides.jobs/vacancies/924564?origem=portal",
    "type": "externa",
    "homeOffice": False,
    "jobType": "remoto",
    "seniority": [{"id": 4, "name": "Junior", "level": None}],
    "createdAt": "2026-09-20",
}

# Vaga presencial no RN, vinda de `locations=RN`.
NO_RN = {
    "id": 924136,
    "title": "ANALISTA DE REDE JR",
    "description": "<p>A TCM é um grupo multissetorial, dividido entre os "
                   "nichos de telecomunicações e empreendimentos.</p>",
    "companyName": "GRUPO TCM",
    "state": {"id": 11, "name": "Rio Grande do Norte", "code": "RN"},
    "city": {"id": 1163, "name": "Mossoró", "state_id": 11},
    "slug": "tcmtelecom",
    "redirectLink": "https://tcmtelecom.solides.jobs/vacancies/924136?origem=portal",
    "type": "externa",
    "homeOffice": False,
    "jobType": "presencial",
    "seniority": [{"id": 4, "name": "Junior", "level": None}],
    "createdAt": "2026-09-18",
}

# Vinda de `title=estagiario`: o portal devolve `seniority` vazio nessa busca.
ESTAGIO = {
    "id": 924743,
    "title": "ESTAGIÁRIO(A) DE PLM ",
    "description": "<p><strong>Resumo das atividades:</strong></p>",
    "companyName": "KUKA SYSTEMS DO BRASIL LTDA",
    "state": {"id": 20, "name": "São Paulo", "code": "SP"},
    "city": {"id": 3420, "name": "Diadema", "state_id": 20},
    "slug": "kuka",
    "redirectLink": "https://kuka.solides.jobs/vacancies/924743?origem=portal",
    "type": "externa",
    "homeOffice": False,
    "jobType": "presencial",
    "seniority": [],
    "createdAt": "2026-09-21",
}

# Caso medido: o filtro `seniorities=junior` aceita titulo misto, que este
# projeto tambem aceita de proposito.
MISTA = {
    **REMOTA,
    "id": 900001,
    "title": "Analista Full Stack Júnior / Pleno",
    "seniority": [
        {"id": 4, "name": "Junior", "level": None},
        {"id": 5, "name": "Pleno", "level": None},
    ],
}


class _Sessao:
    """Substitui a PoliteSession: devolve as paginas na ordem programada."""

    def __init__(self, paginas):
        self.paginas = list(paginas)
        self.chamadas = []
        self.request_count = 0

    def get_json(self, url, params=None, **kwargs):
        self.chamadas.append((url, dict(params or {})))
        self.request_count += 1
        return self.paginas.pop(0) if self.paginas else None


def _envelope(itens, **extra):
    """Envelope aninhado da API: a lista vive em `data.data`."""
    return {"success": True, "errors": [],
            "data": {"count": len(itens), "currentPage": 1,
                     "totalPages": 1, "data": list(itens), **extra}}


def _fonte(sessao, **ajustes):
    return SolidesSource(session=sessao, settings=Settings(**ajustes))


def _vazia():
    return _envelope([])


def _cheia(inicio=0, **campos):
    """Pagina cheia (PAGE_SIZE itens de ids distintos).

    Pagina curta significa fim da listagem, entao teste que exercita a
    paginacao precisa de pagina cheia -- senao para na primeira por esse
    motivo, e nao pelo que o teste quer medir.
    """
    return _envelope([{**REMOTA, "id": inicio + n, **campos}
                      for n in range(PAGE_SIZE)])


# --------------------------------------------------------------------- parser


def test_parse_traz_os_campos_da_vaga():
    fonte = _fonte(_Sessao([]))
    job = fonte._parse(REMOTA, "junior", "")

    assert job.source == "solides"
    assert job.external_id == "924564"
    assert job.title == "Analista de Suporte e Implantação - Hospitalar"
    assert job.company == "INOVADORA SISTEMAS DE GESTAO LTDA"
    assert job.location == "Joaçaba, SC"
    assert job.published_date == "2026-09-20"
    assert job.search_term == "junior"
    # O HTML da descricao e limpo pelo proprio modelo.
    assert "<p>" not in job.description
    assert "Inovadora" in job.description


def test_modalidade_vem_do_jobtype_e_nao_do_homeoffice():
    """A vaga remota real chegou com `homeOffice` False e `jobType` remoto."""
    fonte = _fonte(_Sessao([]))
    assert fonte._parse(REMOTA, "junior", "").workplace_type == REMOTO
    assert fonte._parse(NO_RN, "junior", "").workplace_type == PRESENCIAL


def test_homeoffice_tambem_conta_quando_marcado():
    fonte = _fonte(_Sessao([]))
    bruto = {**NO_RN, "homeOffice": True}
    assert fonte._parse(bruto, "junior", "").workplace_type == REMOTO


def test_vaga_sem_id_ou_sem_titulo_e_descartada():
    fonte = _fonte(_Sessao([]))
    assert fonte._parse({**REMOTA, "id": None}, "junior", "") is None
    assert fonte._parse({**REMOTA, "title": "  "}, "junior", "") is None


# ------------------------------------------------------------------ o link


def test_link_usa_a_pagina_canonica_do_portal():
    """`redirectLink` aponta para subdominio desativado; nao serve de link."""
    job = _fonte(_Sessao([]))._parse(REMOTA, "junior", "")
    assert job.url == (f"{PORTAL_URL}/vaga/924564/"
                       "analista-de-suporte-e-implantacao-hospitalar")
    assert "solides.jobs" not in job.url


def test_url_publica_sem_titulo_utilizavel_devolve_vazio():
    assert url_publica("123", "!!!") == ""
    assert url_publica("", "Analista") == ""


# ------------------------------------------------------------- senioridade


def test_filtro_nativo_de_junior_preenche_o_nivel():
    """Medido confiavel: 2 titulos com nivel alto em 150 amostrados."""
    job = _fonte(_Sessao([]))._parse(REMOTA, "junior", "")
    assert job.seniority == "Júnior"


def test_busca_por_titulo_deixa_o_nivel_para_o_regex():
    """`title=` casa frouxo, entao quem decide o nivel e o titulo."""
    job = _fonte(_Sessao([]))._parse(ESTAGIO, "estagiario", "")
    assert job.seniority == ""
    # E o filtro do pipeline resolve, pelo titulo.
    assert filter_entry_level([job])[0].seniority == "Estágio"


def test_titulo_misto_do_filtro_junior_sobrevive_ao_pipeline():
    job = _fonte(_Sessao([]))._parse(MISTA, "junior", "")
    assert filter_entry_level([job]) == [job]


# ------------------------------------------------------------- paginacao


def test_para_na_pagina_vazia():
    sessao = _Sessao([_cheia(), _vazia()])
    jobs = _fonte(sessao)._paginar({"seniorities": "junior"}, filtro="junior")

    assert len(jobs) == PAGE_SIZE
    assert len(sessao.chamadas) == 2
    assert sessao.chamadas[0][0] == API_URL
    assert [p["page"] for _, p in sessao.chamadas] == [1, 2]


def test_pagina_curta_encerra_a_listagem():
    sessao = _Sessao([_envelope([REMOTA]), _cheia()])
    jobs = _fonte(sessao)._paginar({"seniorities": "junior"}, filtro="junior")

    assert [j.external_id for j in jobs] == ["924564"]
    assert len(sessao.chamadas) == 1


def test_todas_as_consultas_levam_o_recorte_de_tecnologia():
    sessao = _Sessao([_envelope([REMOTA]), _vazia()])
    _fonte(sessao)._paginar({"seniorities": "junior"}, filtro="junior")

    _, params = sessao.chamadas[0]
    assert params["occupationAreas"] == "tecnologia"
    assert params["seniorities"] == "junior"
    assert params["page"] == 1


def test_para_quando_a_api_repete_a_mesma_pagina():
    """Pagina cheia so de ids ja vistos nao rende nada; seguir seria inutil."""
    repetida = _cheia(900000)
    sessao = _Sessao([repetida, repetida, repetida])
    jobs = _fonte(sessao)._paginar({"seniorities": "junior"}, filtro="junior")

    assert len(jobs) == PAGE_SIZE
    assert len(sessao.chamadas) == 2


def test_para_quando_a_pagina_inteira_passou_do_corte_de_idade():
    """A listagem vem da mais nova para a mais velha."""
    sessao = _Sessao([_cheia(createdAt="2022-06-23"), _cheia(900000)])
    jobs = _fonte(sessao, dias_max=60)._paginar(
        {"seniorities": "junior"}, filtro="junior")

    # As velhas ainda sao devolvidas -- quem descarta e o filtro do pipeline.
    assert len(jobs) == PAGE_SIZE
    assert len(sessao.chamadas) == 1


def test_vaga_sem_data_na_pagina_nao_autoriza_parar():
    """Data ausente nao prova que e velha; parar ali esconderia as seguintes."""
    velha = _cheia(createdAt="2022-06-23")
    velha["data"]["data"][-1]["createdAt"] = None
    sessao = _Sessao([velha, _vazia()])
    _fonte(sessao, dias_max=60)._paginar({"seniorities": "junior"},
                                         filtro="junior")

    assert len(sessao.chamadas) == 2


def test_sem_filtro_de_idade_nao_para_por_data():
    sessao = _Sessao([_cheia(createdAt="2022-06-23"), _vazia()])
    _fonte(sessao, dias_max=0)._paginar({"seniorities": "junior"},
                                        filtro="junior")

    assert len(sessao.chamadas) == 2


# ---------------------------------------------------------- filtros nativos


def test_fetch_troca_os_termos_do_projeto_pelos_filtros_nativos():
    paginas = []
    for _ in FILTROS:
        paginas += [_envelope([REMOTA]), _vazia()]
    sessao = _Sessao(paginas)
    _fonte(sessao, locais_presenciais=[]).fetch(["desenvolvedor junior"])

    pedidos = {p.get("seniorities") or p.get("title")
               for _, p in sessao.chamadas}
    assert pedidos == {"junior", "estagio", "estagiario", "trainee", "aprendiz"}


def test_estagio_e_estagiario_sao_buscas_separadas():
    """Medido: `title=estagio` (113) nao cobre `title=estagiario` (119)."""
    assert FILTROS["estagio"] == {"title": "estagio"}
    assert FILTROS["estagiario"] == {"title": "estagiario"}


def test_so_o_filtro_junior_usa_seniorities():
    """`seniorities` so entende `junior`; os outros valores nao filtram."""
    usam = [k for k, v in FILTROS.items() if "seniorities" in v]
    assert usam == ["junior"]


# -------------------------------------------------------------- por local


def test_fetch_local_pede_a_uf_em_locations():
    paginas = []
    for _ in FILTROS:
        paginas += [_envelope([NO_RN]), _vazia()]
    sessao = _Sessao(paginas)
    jobs = _fonte(sessao).fetch_local(RIO_GRANDE_DO_NORTE, ["ignorado"])

    assert all(p["locations"] == "RN" for _, p in sessao.chamadas)
    assert all(j.local_consultado == "rn" for j in jobs)


def test_fortaleza_pede_a_uf_inteira_mas_nao_confia_nela():
    """A consulta traz o Ceara todo, entao o texto e que prova a capital."""
    assert FORTALEZA.solides_uf == "CE"
    assert FORTALEZA.consulta_e_prova is False


def test_local_montado_casa_com_o_reconhecedor_dos_locais():
    """"Cidade, UF" e o formato que o reconhecedor estrito espera.

    Importa para Fortaleza, que nao aceita a consulta como prova e exige a
    cidade escrita: se o local fosse so a UF, a vaga da capital seria perdida.
    """
    fonte = _fonte(_Sessao([]))

    em_fortaleza = fonte._parse(
        {**NO_RN, "city": {"name": "Fortaleza"},
         "state": {"name": "Ceará", "code": "CE"}}, "junior", "fortaleza")
    assert em_fortaleza.location == "Fortaleza, CE"
    assert serve_presencialmente(em_fortaleza, [FORTALEZA])

    assert serve_presencialmente(fonte._parse(NO_RN, "junior", "rn"),
                                 [RIO_GRANDE_DO_NORTE])


def test_vaga_do_ceara_fora_da_capital_nao_passa_por_fortaleza():
    """A consulta traz a UF inteira, e so a capital serve."""
    fonte = _fonte(_Sessao([]))
    em_caucaia = fonte._parse(
        {**NO_RN, "city": {"name": "Caucaia"},
         "state": {"name": "Ceará", "code": "CE"}}, "junior", "fortaleza")

    assert em_caucaia.location == "Caucaia, CE"
    assert not serve_presencialmente(em_caucaia, [FORTALEZA])


def test_local_sem_uf_configurada_fica_de_fora():
    sessao = _Sessao([])
    sem_uf = Local(slug="x", nome="X", uf="XX", reconhecer=("x",))
    assert _fonte(sessao).fetch_local(sem_uf, ["termo"]) == []
    assert sessao.chamadas == []


# ------------------------------------------------------------------ limites


def test_teto_de_paginas_existe_para_quando_a_idade_esta_desligada():
    sessao = _Sessao([_cheia(n * PAGE_SIZE)
                      for n in range(MAX_PAGINAS + 5)])
    jobs = _fonte(sessao, dias_max=0)._paginar({"seniorities": "junior"},
                                               filtro="junior")

    assert len(sessao.chamadas) == MAX_PAGINAS
    assert len(jobs) == MAX_PAGINAS * PAGE_SIZE


def test_falha_de_rede_encerra_sem_derrubar_a_coleta():
    sessao = _Sessao([_cheia(), None])
    jobs = _fonte(sessao)._paginar({"seniorities": "junior"}, filtro="junior")

    assert len(jobs) == PAGE_SIZE
    assert len(sessao.chamadas) == 2
