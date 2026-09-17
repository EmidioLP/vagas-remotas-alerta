"""Coletor do Mentora Dados, com recortes reais da resposta do admin-ajax (offline)."""

from __future__ import annotations

import pytest

from scraper.config import Settings
from scraper.locais import LOCAIS, serve_presencialmente
from scraper.models import HIBRIDO, NAO_INFORMADO, PRESENCIAL, REMOTO
from scraper.notificacao import montar_embed
from scraper.sources.mentoradados import (
    API_URL,
    VARIOS_ESTADOS,
    MentoraDadosSource,
)

# Recorte real de uma vaga livre (POST admin-ajax, action=mentora_get_vagas).
LIVRE = {
    "id": 11782,
    "titulo": "Engenheiro de Dados Júnior",
    "empresa": "Guidance",
    "cidade": "Minas Gerais (MG)",
    "salario": "A combinar",
    "nivel": ["Júnior"],
    "modelo": "Híbrido",
    "permalink": "https://mentoradados.com/vagas/engenheiro-de-dados-junior-22/",
    "hash": "a700e85468",
    "data": "16/09",
    "data_relativa": "há 19 horas",
    "area": ["Engenharia de Dados"],
    "skills": ["SQL", "Python", "dbt", "Git / GitHub", "Airflow", "Power BI"],
    "conteudo": '<div class="vaga-content"><p><strong>🎯 Vaga: Engenheiro de Dados Júnior</strong></p>'
                "<p>Requisitos: SQL e Python.</p><p>Benefícios: vale-refeição.</p></div>",
    "is_vip": False,
    "vip_motivo": "",
    "bloqueada": False,
    "link_aplicacao": "https://oportunidades.mindsight.com.br/guidance/65",
    "link_original": "https://lnkd.in/p/dn9gxfRm",
}

# Como chega uma vaga travada: vitrine sem conteúdo nem link.
TRAVADA = {**LIVRE, "id": 11800, "bloqueada": True, "is_vip": True, "vip_motivo": "hoje",
           "conteudo": "", "link_aplicacao": "", "link_original": ""}

TODOS_OS_ESTADOS = ("Acre (AC), Alagoas (AL), Amapá (AP), Amazonas (AM), Bahia (BA), "
                    "Ceará (CE), Distrito Federal (DF), Rio Grande do Norte (RN), São Paulo (SP)")


class _Sessao:
    def __init__(self, paginas):
        self.paginas = list(paginas)
        self.chamadas = []
        self.request_count = 0

    def post_json(self, url, data=None, **kwargs):
        self.chamadas.append((url, data))
        self.request_count += 1
        return self.paginas.pop(0) if self.paginas else None


def _pagina(vagas, total_paginas=1, pagina=1):
    return {"success": True, "data": {"vagas": vagas, "total_paginas": total_paginas,
                                      "total_vagas": len(vagas), "pagina_atual": pagina}}


def _fonte(sessao=None):
    return MentoraDadosSource(session=sessao or _Sessao([]), settings=Settings())


def test_parse_mapeia_os_campos():
    job = _fonte()._parse(LIVRE)
    assert job.source == "mentoradados"
    assert job.external_id == "11782"
    assert job.title == "Engenheiro de Dados Júnior"
    assert job.company == "Guidance"
    assert job.url == LIVRE["link_aplicacao"]
    assert job.location == "Minas Gerais (MG)"
    assert job.workplace_type == HIBRIDO
    assert job.seniority == "Júnior"
    assert "<p>" not in job.description


def test_data_sem_ano_vira_iso():
    assert _fonte()._parse(LIVRE).published_date.endswith("-09-16")


def test_skills_do_portal_sao_preservadas():
    assert _fonte()._parse(LIVRE).skills == LIVRE["skills"]


def test_descricao_serve_para_classificar_mas_nao_vai_para_o_card():
    """Os termos do site proíbem reproduzir o conteúdo produzido por eles."""
    job = _fonte()._parse(LIVRE)
    assert job.reproduzir_descricao is False
    assert job.description, "continua disponível para o classificador"

    embed = montar_embed(job)
    nomes = {c["name"] for c in embed["fields"]}
    assert not nomes & {"Requisitos", "Responsabilidades", "Benefícios"}
    assert "description" not in embed
    assert "Tecnologias" in nomes
    assert embed["url"] == LIVRE["link_aplicacao"]


def test_a_mesma_vaga_com_a_marca_invertida_leva_o_texto_no_card():
    """A marca é por vaga: as outras fontes não perdem a descrição. Este texto
    não tem seções no formato reconhecido, então entra pelo início dele."""
    job = _fonte()._parse(LIVRE)
    job.reproduzir_descricao = True
    embed = montar_embed(job)
    assert "Engenheiro de Dados" in embed.get("description", "")


def test_fetch_descarta_vaga_travada_no_paywall():
    """A travada chega sem conteúdo nem link. Descartada, ela não vai para o
    estado e entra numa execução seguinte, quando abrir à meia-noite."""
    jobs = _fonte(_Sessao([_pagina([LIVRE, TRAVADA])])).fetch([])
    assert [j.external_id for j in jobs] == ["11782"]


def test_fetch_pede_so_a_acao_de_leitura_com_o_filtro_de_nivel():
    """O endpoint tem ações que alteram dados (votar, rastrear); só a de leitura é usada."""
    sessao = _Sessao([_pagina([LIVRE])])
    _fonte(sessao).fetch(["desenvolvedor junior"])
    url, dados = sessao.chamadas[0]
    assert url == API_URL
    assert dados["action"] == "mentora_get_vagas"
    assert dados["level[]"] == ["Júnior", "Estágio"]


def test_fetch_percorre_as_paginas_e_para_na_ultima():
    sessao = _Sessao([_pagina([LIVRE], total_paginas=2, pagina=1),
                      _pagina([{**LIVRE, "id": 2}], total_paginas=2, pagina=2),
                      _pagina([{**LIVRE, "id": 3}])])
    jobs = _fonte(sessao).fetch([])
    assert len(jobs) == 2
    assert len(sessao.chamadas) == 2


@pytest.mark.parametrize("resposta", [None, {"success": False, "data": "erro"}])
def test_resposta_ruim_encerra_sem_estourar(resposta):
    assert _fonte(_Sessao([resposta])).fetch([]) == []


@pytest.mark.parametrize("candidatura", [
    "#",                                        # seis vagas medidas assim
    "http://daniele.pires@decisionbr.com.br",   # e-mail com http:// colado na frente
    "http://dados@c1porcento.com",
    "",
    None,
])
def test_link_que_nao_serve_cai_na_pagina_da_vaga(candidatura):
    job = _fonte()._parse({**LIVRE, "link_aplicacao": candidatura})
    assert job.url == LIVRE["permalink"]


def test_link_de_reserva_passa_na_validacao_do_discord():
    """Fecha o ciclo: sem isso o e-mail disfarçado chegava no card sem link."""
    from scraper.notificacao import url_valida
    job = _fonte()._parse({**LIVRE, "link_aplicacao": "http://dados@c1porcento.com"})
    assert url_valida(job.url)


def test_lista_de_estados_nao_prova_rn():
    job = _fonte()._parse({**LIVRE, "cidade": TODOS_OS_ESTADOS, "modelo": "Presencial"})
    assert job.location == VARIOS_ESTADOS
    assert not serve_presencialmente(job, list(LOCAIS.values()))


def test_estado_unico_do_rn_continua_valendo():
    job = _fonte()._parse({**LIVRE, "cidade": "Rio Grande do Norte (RN)", "modelo": "Presencial"})
    assert serve_presencialmente(job, [LOCAIS["rn"]])


def test_ceara_sem_cidade_nao_prova_fortaleza():
    """O pedido é a capital; "Ceará (CE)" não diz qual cidade."""
    job = _fonte()._parse({**LIVRE, "cidade": "Ceará (CE)", "modelo": "Presencial"})
    assert not serve_presencialmente(job, [LOCAIS["fortaleza"]])


@pytest.mark.parametrize("modelo,esperado", [
    ("Remoto", REMOTO), ("Híbrido", HIBRIDO), ("Presencial", PRESENCIAL),
    ("", NAO_INFORMADO), (None, NAO_INFORMADO),
])
def test_de_para_de_modelo(modelo, esperado):
    assert _fonte()._parse({**LIVRE, "modelo": modelo}).workplace_type == esperado


@pytest.mark.parametrize("nivel,esperado", [
    (["Júnior"], "Júnior"),
    (["Estágio"], "Estágio"),
    (["Pleno", "Júnior"], "Júnior"),
    (["Pleno"], ""),          # vazio: a decisão cai no título
    ([], ""),
    (None, ""),
])
def test_nivel_declarado(nivel, esperado):
    assert _fonte()._parse({**LIVRE, "nivel": nivel}).seniority == esperado


def test_vaga_sem_id_ou_titulo_e_ignorada():
    assert _fonte()._parse({**LIVRE, "id": None}) is None
    assert _fonte()._parse({**LIVRE, "titulo": "  "}) is None
