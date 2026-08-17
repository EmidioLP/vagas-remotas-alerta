"""Estado de vagas já avisadas e montagem das mensagens do Discord."""

from __future__ import annotations

import json

from scraper.models import Job
from scraper.notificacao import (
    LIMITE_POR_MENSAGEM,
    carregar_vistas,
    enviar,
    extrair_secao,
    montar_embed,
    montar_mensagens,
    salvar_vistas,
    separar_novas,
)


def _job(ext, titulo="Dev Júnior", fonte="gupy", data="2026-08-03", **kw):
    job = Job(source=fonte, external_id=ext, title=titulo,
              published_date=data, **kw)
    return job


def test_estado_ausente_comeca_vazio(tmp_path):
    assert carregar_vistas(tmp_path / "nao_existe.json") == set()


def test_estado_corrompido_nao_derruba(tmp_path):
    """Um JSON quebrado não pode impedir a execução -- só reavisa."""
    caminho = tmp_path / "estado.json"
    caminho.write_text("{ isso nao e json", encoding="utf-8")
    assert carregar_vistas(caminho) == set()


def test_salvar_e_carregar(tmp_path):
    caminho = tmp_path / "estado.json"
    salvar_vistas(caminho, {"gupy:1", "linkedin:2"})
    assert carregar_vistas(caminho) == {"gupy:1", "linkedin:2"}


def test_estado_gravado_e_ordenado(tmp_path):
    """Ordenado para o diff do git ficar legível entre execuções."""
    caminho = tmp_path / "estado.json"
    salvar_vistas(caminho, {"z:9", "a:1", "m:5"})
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["vistas"] == sorted(dados["vistas"])
    assert dados["total"] == 3
    assert "atualizado_em" in dados


def test_separar_novas_ignora_ja_vistas():
    jobs = [_job("1"), _job("2"), _job("3")]
    novas = separar_novas(jobs, {"gupy:1", "gupy:3"})
    assert [j.external_id for j in novas] == ["2"]


def test_separar_novas_sem_estado_devolve_tudo():
    jobs = [_job("1"), _job("2")]
    assert len(separar_novas(jobs, set())) == 2


def test_separar_novas_ordena_pela_mais_recente():
    jobs = [_job("1", data="2026-07-01"), _job("2", data="2026-08-03"),
            _job("3", data="2026-07-15")]
    assert [j.external_id for j in separar_novas(jobs, set())] == ["2", "3", "1"]


def test_mesma_id_em_fontes_diferentes_sao_vagas_distintas():
    jobs = [_job("1", fonte="gupy"), _job("1", fonte="linkedin")]
    assert len(separar_novas(jobs, {"gupy:1"})) == 1


def _campos(embed):
    return {c["name"]: c["value"] for c in embed["fields"]}


def test_embed_traz_todos_os_dados_da_vaga():
    job = _job("1", titulo="Dev Backend Jr", company="ACME",
               url="https://exemplo.test/1", area="Backend",
               location="Remoto", workplace_type="Remoto", seniority="Júnior")
    job.skills = ["Python", "SQL", "Docker"]
    embed = montar_embed(job)
    campos = _campos(embed)
    assert embed["title"] == "Dev Backend Jr"
    assert embed["url"] == "https://exemplo.test/1"
    assert campos["Empresa"] == "ACME"
    assert campos["Modalidade"] == "Remoto"
    assert campos["Nível"] == "Júnior"
    assert campos["Área"] == "Backend"
    assert campos["Publicada em"] == "2026-08-03"
    # Todas as tecnologias, não só as primeiras.
    assert campos["Tecnologias"] == "Python, SQL, Docker"
    assert embed["footer"]["text"] == "via gupy"


def test_embed_traz_requisitos_e_beneficios():
    job = _job("1", description=(
        "Sobre a vaga. Responsabilidades e atribuições Manter APIs em Python. "
        "Requisitos e qualificações Conhecimento em SQL e Git. "
        "Benefícios Vale refeição e plano de saúde."
    ))
    campos = _campos(montar_embed(job))
    assert "Manter APIs" in campos["Responsabilidades"]
    assert "SQL e Git" in campos["Requisitos"]
    assert "Vale refeição" in campos["Benefícios"]


def test_campo_vazio_nao_entra_no_embed():
    job = _job("1", company="", area="")
    nomes = {c["name"] for c in montar_embed(job)["fields"]}
    assert "Empresa" not in nomes
    assert "Área" not in nomes


def test_vaga_sem_url_nao_gera_link_quebrado():
    embed = montar_embed(_job("1", titulo="Dev Júnior", url=""))
    assert "url" not in embed
    assert embed["title"] == "Dev Júnior"


def test_sem_secoes_mostra_o_inicio_da_descricao():
    """O card do LinkedIn não traz descrição estruturada."""
    job = _job("1", description="Texto corrido sem seções nenhuma aqui.")
    embed = montar_embed(job)
    assert embed["description"].startswith("Texto corrido")


def test_campo_longo_e_cortado_no_limite_do_discord():
    job = _job("1", description="Requisitos e qualificações " + "palavra " * 400)
    campo = _campos(montar_embed(job))["Requisitos"]
    assert len(campo) <= 1000
    assert campo.endswith("…")


def test_extrair_secao_sem_a_secao_devolve_vazio():
    assert extrair_secao("Texto sem secoes.", "Requisitos") == ""
    assert extrair_secao("", "Requisitos") == ""
    assert extrair_secao("Requisitos e qualificações X", "Inexistente") == ""


def test_subtitulo_que_repete_a_palavra_nao_corta_a_secao():
    """Caso real da Gupy: 'Requisitos e qualificações' seguido de
    'Requisitos Técnicos' cortava a seção no terceiro caractere."""
    texto = (
        "Requisitos e qualificações 🎯 Requisitos Técnicos (O que você precisa) "
        "Fluência em JavaScript, React e Node.js."
    )
    extraido = extrair_secao(texto, "Requisitos")
    assert "JavaScript, React e Node.js" in extraido


def test_extrair_secao_para_no_proximo_titulo():
    texto = "Requisitos e qualificações Python e SQL. Benefícios Vale refeição."
    assert "Vale refeição" not in extrair_secao(texto, "Requisitos")
    assert "Python e SQL" in extrair_secao(texto, "Requisitos")


def test_muitas_vagas_viram_varias_mensagens():
    jobs = [_job(str(i)) for i in range(LIMITE_POR_MENSAGEM * 2 + 1)]
    mensagens = montar_mensagens(jobs, "Novas")
    assert len(mensagens) == 3
    assert "(1/3)" in mensagens[0]["content"]


def test_lote_unico_nao_ganha_contador():
    mensagens = montar_mensagens([_job("1")], "Novas")
    assert "/" not in mensagens[0]["content"]
    assert "Novas" in mensagens[0]["content"]


def test_cada_vaga_vira_um_embed_respeitando_o_limite():
    """O Discord aceita no máximo 10 embeds por mensagem."""
    jobs = [_job(str(i)) for i in range(LIMITE_POR_MENSAGEM * 2)]
    mensagens = montar_mensagens(jobs, "Novas")
    assert all(len(m["embeds"]) <= 10 for m in mensagens)
    assert sum(len(m["embeds"]) for m in mensagens) == len(jobs)


class _RespostaFalsa:
    def __init__(self, status): self.status_code = status; self.text = "erro"


class _SessaoFalsa:
    def __init__(self, status=204): self.status = status; self.chamadas = []
    def post(self, url, json=None, timeout=None):
        self.chamadas.append((url, json))
        return _RespostaFalsa(self.status)


def test_enviar_publica_cada_mensagem():
    sessao = _SessaoFalsa()
    total = enviar("https://webhook.test", montar_mensagens(
        [_job(str(i)) for i in range(LIMITE_POR_MENSAGEM + 1)], "Novas"), sessao)
    assert total == 2 and len(sessao.chamadas) == 2


def test_enviar_para_no_primeiro_erro():
    """Sem isso o estado marcaria como avisada uma vaga que não chegou."""
    sessao = _SessaoFalsa(status=429)
    total = enviar("https://webhook.test", montar_mensagens(
        [_job(str(i)) for i in range(LIMITE_POR_MENSAGEM + 1)], "Novas"), sessao)
    assert total == 0 and len(sessao.chamadas) == 1
