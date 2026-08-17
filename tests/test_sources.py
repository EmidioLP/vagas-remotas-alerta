"""Testes dos parsers, usando respostas reais capturadas dos portais (offline)."""

import pytest

from scraper.config import Settings
from scraper.sources.gupy import GupySource
from scraper.sources.linkedin import GEO_ID_BRASIL, LinkedInSource
from scraper.sources.trampos import TramposSource
from scraper.sources.vagas_com import VagasComSource, slugify_term
from scraper.sources.weworkremotely import CATEGORIAS, WeWorkRemotelySource

# Recorte real da resposta de
# GET https://employability-portal.gupy.io/api/v1/jobs?jobName=desenvolvedor+junior
GUPY_JOB = {
    "id": 11617525,
    "companyId": 551,
    "name": "Desenvolvedor de Sistema Junior",
    "description": "<p>Buscamos um(a) Desenvolvedor(a) Full Stack J&uacute;nior "
                   "para atuar com Java no back-end.</p>",
    "careerPageId": 166261,
    "careerPageName": "Minsait",
    "careerPageUrl": "https://minsait.gupy.io/",
    "type": "vacancy_type_effective",
    "publishedDate": "2026-07-31T14:00:13.962Z",
    "applicationDeadline": "2026-08-14",
    "isRemoteWork": False,
    "city": "São Paulo",
    "state": "São Paulo",
    "country": "Brasil",
    "jobUrl": "https://minsait.gupy.io/job/abc123",
    "workplaceType": "hybrid",
    "disabilities": False,
    "skills": [],
}

# Recorte real de https://www.vagas.com.br/vagas-de-desenvolvedor-junior
VAGAS_HTML = """
<ul>
<li class="vaga odd ">
  <header class="clearfix">
    <div class="informacoes-header">
      <h2 class="cargo">
        <a class="link-detalhes-vaga" data-id-vaga="2824782"
           title="Desenvolvedor de Software Jr" id="v2824782"
           href="/vagas/v2824782/desenvolvedor-de-software-jr">
            <mark>Desenvolvedor</mark> de Software Jr
        </a>
      </h2>
      <span class="emprVaga"> HStern </span>
      <div class="nivelQtdVagas"><span class="nivelVaga">Júnior/Trainee</span></div>
    </div>
  </header>
  <div class="detalhes"><p>Descrição: <mark>Desenvolvedor</mark> Júnior de Software</p></div>
  <footer>
    <div class="vaga-local"><i class="bx bx-map"></i> Rio de Janeiro / RJ </div>
    <span class="data-publicacao"><i class="bx bx-time-five"></i>09/07/2026</span>
  </footer>
</li>
</ul>
"""


def _source(cls):
    return cls(session=None, settings=Settings())


def test_gupy_parse_mapeia_campos():
    job = _source(GupySource)._parse(GUPY_JOB, "desenvolvedor junior")
    assert job is not None
    assert job.source == "gupy"
    assert job.external_id == "11617525"
    assert job.title == "Desenvolvedor de Sistema Junior"
    assert job.company == "Minsait"
    assert job.url == "https://minsait.gupy.io/job/abc123"
    assert job.location == "São Paulo, São Paulo"
    assert job.workplace_type == "Híbrido"
    assert job.published_date == "2026-07-31"
    assert job.search_term == "desenvolvedor junior"


def test_gupy_parse_limpa_html_da_descricao():
    job = _source(GupySource)._parse(GUPY_JOB, "x")
    assert "<p>" not in job.description
    assert "Júnior" in job.description  # entidade &uacute; decodificada


def test_gupy_parse_ignora_registro_incompleto():
    assert _source(GupySource)._parse({"id": None, "name": ""}, "x") is None
    assert _source(GupySource)._parse({"id": 1}, "x") is None


def test_gupy_usa_country_quando_nao_ha_cidade():
    raw = dict(GUPY_JOB, city="", state="")
    assert _source(GupySource)._parse(raw, "x").location == "Brasil"


def test_vagas_parse_page():
    jobs = _source(VagasComSource)._parse_page(VAGAS_HTML, "desenvolvedor junior")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "vagas"
    assert job.external_id == "2824782"
    assert job.title == "Desenvolvedor de Software Jr"
    assert job.company == "HStern"
    assert job.url == "https://www.vagas.com.br/vagas/v2824782/desenvolvedor-de-software-jr"
    assert job.location == "Rio de Janeiro / RJ"
    assert job.published_date == "09/07/2026"
    # "Júnior/Trainee" (span.nivelVaga) e senioridade, nao modalidade de trabalho.
    assert job.workplace_type == "Não informado"


def test_vagas_parse_page_detecta_home_office():
    html = VAGAS_HTML.replace("Rio de Janeiro / RJ", "100% Home Office")
    job = _source(VagasComSource)._parse_page(html, "x")[0]
    assert job.workplace_type == "Remoto"
    assert job.location == "100% Home Office"


def test_vagas_parse_page_vazia():
    assert _source(VagasComSource)._parse_page("<html><body></body></html>", "x") == []


def test_slugify_term():
    assert slugify_term("desenvolvedor júnior") == "desenvolvedor-junior"
    assert slugify_term("Estágio  em TI") == "estagio-em-ti"



# Recorte real de GET https://trampos.co/api/v2/opportunities?tr=desenvolvedor&page=1
TRAMPOS_JSON = {
    "id": 773915,
    "name": "Desenvolvedor(a) .Net C#",
    "type_name": "Emprego",
    "type_slug": "emprego",
    "category_name": "Tecnologia da Informação",
    "category_slug": "ti",
    "home_office": None,
    "hybrid": True,
    "salary": "NÃO DIVULGADA",
    "published_at": "2026-08-02T12:00:07.000-03:00",
    "custom_company_name": None,
    "company": {
        "id": 725735,
        "name": "Artium Soluções",
        "slug": "artium-solucoes",
        "description": "Somos uma empresa de tecnologia da inovação.",
    },
    "email_share_url":
        "https://trampos.co/oportunidades/773915-desenvolvedor-a-net-c/share/email",
}


def test_trampos_parse_mapeia_campos():
    job = _source(TramposSource)._parse(TRAMPOS_JSON, "desenvolvedor")
    assert job is not None
    assert job.source == "trampos"
    assert job.external_id == "773915"
    assert job.title == "Desenvolvedor(a) .Net C#"
    assert job.company == "Artium Soluções"
    assert job.published_date == "2026-08-02"
    assert job.search_term == "desenvolvedor"


def test_trampos_url_sai_do_link_de_compartilhamento():
    # A API não devolve a URL da vaga; ela está dentro das de compartilhamento.
    job = _source(TramposSource)._parse(TRAMPOS_JSON, "x")
    assert job.url == "https://trampos.co/oportunidades/773915-desenvolvedor-a-net-c"


@pytest.mark.parametrize(
    "flags,esperado",
    [
        ({"home_office": True, "hybrid": False}, "Remoto"),
        ({"home_office": True, "hybrid": True}, "Remoto"),
        ({"home_office": None, "hybrid": True}, "Híbrido"),
        ({"home_office": False, "hybrid": False}, "Presencial"),
        ({}, "Presencial"),
    ],
)
def test_trampos_modalidade(flags, esperado):
    # `hybrid` vem sempre; `home_office` às vezes vem nulo.
    assert TramposSource._modalidade(flags) == esperado


def test_trampos_estagio_vem_do_tipo_nativo():
    raw = dict(TRAMPOS_JSON, type_slug="estagio", type_name="Estágio")
    assert _source(TramposSource)._parse(raw, "x").seniority == "Estágio"


def test_trampos_emprego_deixa_senioridade_para_o_regex():
    assert _source(TramposSource)._parse(TRAMPOS_JSON, "x").seniority == ""


def test_trampos_descricao_usa_a_categoria_nativa():
    job = _source(TramposSource)._parse(TRAMPOS_JSON, "x")
    assert "Tecnologia da Informação" in job.description


def test_trampos_descricao_ignora_o_texto_da_empresa():
    """company.description fala da EMPRESA -- usá-la classificaria errado."""
    job = _source(TramposSource)._parse(TRAMPOS_JSON, "x")
    assert "inovação" not in job.description


def test_trampos_salario_nao_divulgado_fica_de_fora():
    job = _source(TramposSource)._parse(TRAMPOS_JSON, "x")
    assert "Salário" not in job.description
    com_salario = _source(TramposSource)._parse(
        dict(TRAMPOS_JSON, salary="R$ 5.000"), "x"
    )
    assert "Salário: R$ 5.000." in com_salario.description


def test_trampos_ignora_registro_incompleto():
    src = _source(TramposSource)
    assert src._parse({"id": None, "name": "x"}, "t") is None
    assert src._parse({"id": 1, "name": ""}, "t") is None


def test_trampos_usa_custom_company_name_quando_existe():
    raw = dict(TRAMPOS_JSON, custom_company_name="Empresa Confidencial")
    assert _source(TramposSource)._parse(raw, "x").company == "Empresa Confidencial"


# Recorte real de
# GET .../jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=desenvolvedor+junior&geoId=106057199
LINKEDIN_HTML = """
<ul>
<li>
  <div class="base-card job-search-card"
       data-entity-urn="urn:li:jobPosting:4422123289">
    <a class="base-card__full-link"
       href="https://www.linkedin.com/jobs/view/desenvolvedor-junior-at-acme-4422123289?position=1&amp;pageNum=0">
      <span class="sr-only">Desenvolvedor Back-end Júnior</span>
    </a>
    <div class="base-search-card__info">
      <h3 class="base-search-card__title">Desenvolvedor Back-end Júnior</h3>
      <h4 class="base-search-card__subtitle">ACME Tecnologia</h4>
      <span class="job-search-card__location">São Paulo, São Paulo, Brazil</span>
      <time datetime="2026-08-01">1 dia atrás</time>
    </div>
  </div>
</li>
</ul>
"""


def test_linkedin_parse_mapeia_campos():
    jobs = _source(LinkedInSource)._parse_page(LINKEDIN_HTML, "desenvolvedor junior")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "linkedin"
    assert job.external_id == "4422123289"
    assert job.title == "Desenvolvedor Back-end Júnior"
    assert job.company == "ACME Tecnologia"
    assert job.location == "São Paulo, São Paulo, Brazil"
    assert job.published_date == "2026-08-01"
    assert job.search_term == "desenvolvedor junior"


def test_linkedin_url_perde_os_parametros_de_rastreio():
    job = _source(LinkedInSource)._parse_page(LINKEDIN_HTML, "x")[0]
    assert job.url == (
        "https://www.linkedin.com/jobs/view/desenvolvedor-junior-at-acme-4422123289"
    )
    assert "?" not in job.url


def test_linkedin_usa_geoid_do_brasil():
    """`location=Brasil` em português falha em silêncio e traz vagas dos EUA."""
    assert GEO_ID_BRASIL == "106057199"


@pytest.mark.parametrize(
    "local,esperado",
    [
        ("São Paulo, São Paulo, Brazil", "Não informado"),
        ("Brazil (Remote)", "Remoto"),
        ("São Paulo (Remoto)", "Remoto"),
        ("", "Não informado"),
    ],
)
def test_linkedin_modalidade_so_afirma_remoto(local, esperado):
    # O card não tem campo de modalidade: presencial e híbrido são
    # indistinguíveis, então não são chutados.
    assert LinkedInSource._modalidade(local) == esperado


def test_linkedin_ignora_card_sem_urn_ou_titulo():
    src = _source(LinkedInSource)
    assert src._parse_page('<div class="base-card"><h3>X</h3></div>', "x") == []
    assert src._parse_page(
        '<div class="base-card" data-entity-urn="urn:li:jobPosting:1"></div>', "x"
    ) == []


def test_linkedin_pagina_vazia():
    assert _source(LinkedInSource)._parse_page("<html></html>", "x") == []


def test_linkedin_sem_descricao_no_card():
    """A busca não traz descrição; a classificação se apoia no título."""
    assert _source(LinkedInSource)._parse_page(LINKEDIN_HTML, "x")[0].description == ""


# Recorte real de
# https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss
WWR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <item>
    <title>Collaboration.Ai: Senior AI Engineer - Agentic Systems</title>
    <region>Anywhere in the World</region>
    <country>United States of America</country>
    <skills>Node.js, PostgreSQL, Python, Kotlin, TypeScript</skills>
    <category>Back-End Programming</category>
    <type>Full-Time</type>
    <description>&lt;p&gt;&lt;strong&gt;Headquarters:&lt;/strong&gt; Minneapolis&lt;/p&gt;</description>
    <link>https://weworkremotely.com/remote-jobs/collaboration-ai-senior-ai-engineer</link>
    <pubDate>Wed, 22 Jul 2026 07:03:14 +0000</pubDate>
  </item>
  <item>
    <title>Business Web Solutions: Web Developer Intern</title>
    <region>Anywhere in the World</region>
    <skills>PHP, JavaScript</skills>
    <category>Back-End Programming</category>
    <type>Contract</type>
    <description>Vaga de estagio.</description>
    <link>https://weworkremotely.com/remote-jobs/bws-web-developer-intern</link>
    <pubDate>Mon, 03 Aug 2026 10:00:00 +0000</pubDate>
  </item>
</channel>
</rss>
"""


def test_wwr_parse_feed():
    jobs = _source(WeWorkRemotelySource)._parse_feed(WWR_RSS, "remote-back-end")
    assert len(jobs) == 2
    job = jobs[0]
    assert job.source == "wwr"
    assert job.external_id == "collaboration-ai-senior-ai-engineer"
    assert job.title == "Senior AI Engineer - Agentic Systems"
    assert job.company == "Collaboration.Ai"
    assert job.url.startswith("https://weworkremotely.com/remote-jobs/")
    assert job.location == "Anywhere in the World"
    assert job.published_date == "2026-07-22"


def test_wwr_separa_empresa_do_titulo():
    # O feed usa "Empresa: Cargo" no título.
    assert WeWorkRemotelySource._empresa_e_titulo("Stripe: Head of Paid Media") == (
        "Stripe", "Head of Paid Media"
    )
    assert WeWorkRemotelySource._empresa_e_titulo("Sem separador") == (
        "", "Sem separador"
    )


def test_wwr_toda_vaga_e_remota():
    """O board só publica remoto -- a modalidade é afirmada, não inferida."""
    jobs = _source(WeWorkRemotelySource)._parse_feed(WWR_RSS, "x")
    assert {j.workplace_type for j in jobs} == {"Remoto"}


def test_wwr_skills_nativas_entram_na_descricao():
    job = _source(WeWorkRemotelySource)._parse_feed(WWR_RSS, "x")[0]
    assert "Node.js" in job.description
    assert "Back-End Programming" in job.description
    # A descrição vem em HTML escapado; as tags não podem sobrar.
    assert "<strong>" not in job.description
    assert "Minneapolis" in job.description


def test_wwr_data_rfc822_vira_iso():
    assert WeWorkRemotelySource._data("Mon, 03 Aug 2026 10:00:00 +0000") == "2026-08-03"
    assert WeWorkRemotelySource._data("") == ""
    assert WeWorkRemotelySource._data("data invalida") == ""


def test_wwr_feed_vazio_ou_invalido():
    src = _source(WeWorkRemotelySource)
    assert src._parse_feed("<rss><channel></channel></rss>", "x") == []
    assert src._parse_feed("nao e xml", "x") == []


def test_wwr_ignora_item_sem_link_valido():
    xml = ("<rss><channel><item><title>ACME: Dev</title>"
           "<link>https://weworkremotely.com/outra-coisa</link></item></channel></rss>")
    assert _source(WeWorkRemotelySource)._parse_feed(xml, "x") == []


def test_wwr_categorias_sao_de_tecnologia():
    assert "remote-programming-jobs" in CATEGORIAS
    assert all(c.startswith("remote-") for c in CATEGORIAS)


