"""Aviso no Discord das vagas que ainda nao foram mostradas.

O estado de "ja avisada" fica num JSON versionado (`state/vagas_vistas.json`),
que o proprio workflow commita de volta ao repositorio. Sem isso, cada execucao
do GitHub Actions comecaria do zero -- o runner e descartado ao terminar -- e
reavisaria as mesmas vagas todo dia.

A chave usada e o par (fonte, id no portal), a mesma identidade que a
deduplicacao ja trata como definitiva.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .models import Job

logger = logging.getLogger(__name__)

# Limites do Discord: 10 embeds por mensagem, 1024 caracteres por campo e
# 6000 caracteres somando TODOS os embeds da mesma mensagem. O ultimo e o
# facil de esquecer: dez vagas com requisitos e beneficios passam dele com
# folga, e o Discord recusa a mensagem inteira com HTTP 400.
LIMITE_POR_MENSAGEM = 10
LIMITE_CAMPO = 1000
LIMITE_DESCRICAO = 3800
ORCAMENTO_MENSAGEM = 5800

# Titulos de secao que os portais usam dentro da descricao. A Gupy e a mais
# consistente ("Responsabilidades e atribuicoes", "Requisitos e qualificacoes",
# "Informacoes adicionais"); os demais variam, e por isso a lista e generosa.
#
# O texto chega com o HTML removido, entao as secoes ficam coladas uma na
# outra ("...do usuario. Requisitos e qualificacoesEnsino superior..."). A
# busca e por titulo, e o conteudo vai dali ate o proximo titulo conhecido.
SECOES = {
    "Requisitos": [
        r"requisitos e qualifica\w*", r"pr[ée]-?requisitos", r"requisitos",
        r"qualifica\w+ necess\w+", r"o que esperamos", r"o que voc[êe] precisa",
        r"requirements",
    ],
    "Benefícios": [
        r"benef[íi]cios", r"o que oferecemos", r"o que voc[êe] recebe",
        r"nossos benef[íi]cios", r"pacote de benef[íi]cios", r"benefits",
        r"informa\w+ adicionais",
    ],
    "Responsabilidades": [
        r"responsabilidades e atribui\w*", r"responsabilidades",
        r"atribui\w+", r"suas atividades", r"o que voc[êe] vai fazer",
    ],
}

def _fronteira(secao: str) -> re.Pattern:
    """Titulos que encerram a secao: os das OUTRAS secoes, nunca os dela.

    A secao costuma repetir a propria palavra em subtitulos -- depois de
    "Requisitos e qualificacoes" vem "Requisitos Tecnicos". Tratar isso como
    fronteira cortava a secao no terceiro caractere.
    """
    outros = [p for nome, padroes in SECOES.items() if nome != secao
              for p in padroes]
    return re.compile("|".join(outros), re.IGNORECASE)


def extrair_secao(descricao: str, secao: str) -> str:
    """Trecho da descricao sob um dos titulos daquela secao.

    Devolve string vazia quando o portal nao publica a secao -- e o caso do
    LinkedIn, cujo card de busca nao traz descricao nenhuma.
    """
    if not descricao or secao not in SECOES:
        return ""

    fronteira = _fronteira(secao)
    for padrao in SECOES[secao]:
        inicio = re.search(padrao, descricao, re.IGNORECASE)
        if inicio is None:
            continue

        resto = descricao[inicio.end():]
        proximo = fronteira.search(resto)
        trecho = resto[: proximo.start()] if proximo else resto
        trecho = re.sub(r"\s+", " ", trecho).strip(" :;.-–—")
        if len(trecho) > 15:  # trechos minusculos sao ruido de titulo repetido
            return trecho
    return ""


def carregar_vistas(caminho: Path) -> set[str]:
    """Chaves ja avisadas. Arquivo ausente ou corrompido = comeca do zero."""
    if not caminho.exists():
        return set()
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Estado ilegivel em %s (%s); tratando como vazio", caminho, exc)
        return set()
    return set(dados.get("vistas") or [])


def salvar_vistas(caminho: Path, vistas: set[str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conteudo = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(vistas),
        # Ordenado para o diff do git ficar legivel entre execucoes.
        "vistas": sorted(vistas),
    }
    caminho.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def separar_novas(jobs: list[Job], vistas: set[str]) -> list[Job]:
    """Vagas ainda nao avisadas, da mais recente para a mais antiga."""
    novas = [job for job in jobs if job.source_key not in vistas]
    return sorted(novas, key=lambda j: (j.published_date or "", j.title), reverse=True)


def _campo(nome: str, valor: str, inline: bool = False) -> dict | None:
    """Campo do embed, cortado no limite do Discord. None quando vazio."""
    valor = (valor or "").strip()
    if not valor:
        return None
    if len(valor) > LIMITE_CAMPO:
        valor = valor[: LIMITE_CAMPO - 1].rsplit(" ", 1)[0] + "…"
    return {"name": nome, "value": valor, "inline": inline}


def montar_embed(job: Job) -> dict:
    """Um embed por vaga, com tudo que o portal informou sobre ela."""
    campos = [
        _campo("Empresa", job.company, inline=True),
        _campo("Modalidade", job.workplace_type, inline=True),
        _campo("Nível", job.seniority, inline=True),
        _campo("Área", job.area, inline=True),
        _campo("Local", job.location, inline=True),
        _campo("Publicada em", job.published_date, inline=True),
        # Todas as tecnologias, nao so as primeiras.
        _campo("Tecnologias", ", ".join(job.skills)),
        _campo("Requisitos", extrair_secao(job.description, "Requisitos")),
        _campo("Responsabilidades", extrair_secao(job.description, "Responsabilidades")),
        _campo("Benefícios", extrair_secao(job.description, "Benefícios")),
    ]

    embed: dict = {
        "title": job.title[:250],
        "color": 0x2A78D6,
        "fields": [c for c in campos if c],
        "footer": {"text": f"via {job.source}"},
    }
    if job.url:
        embed["url"] = job.url

    # Se o portal nao publica secoes (LinkedIn), mostra o inicio da descricao
    # para a mensagem nao ficar so com metadados.
    tem_secao = any(c and c["name"] in ("Requisitos", "Responsabilidades", "Benefícios")
                    for c in campos)
    if not tem_secao and job.description:
        embed["description"] = job.description[:LIMITE_DESCRICAO]

    return embed


def _tamanho_embed(embed: dict) -> int:
    """Caracteres que o Discord soma no orcamento da mensagem."""
    total = len(embed.get("title", "")) + len(embed.get("description", ""))
    total += len(embed.get("footer", {}).get("text", ""))
    for campo in embed.get("fields", []):
        total += len(campo["name"]) + len(campo["value"])
    return total


def montar_mensagens(novas: list[Job], titulo: str) -> list[dict]:
    """Payloads do webhook, fatiados pelos dois limites do Discord.

    Fatiar so pela contagem de embeds nao basta: uma vaga com requisitos,
    responsabilidades e beneficios passa de 3000 caracteres sozinha, entao
    o lote de dez estoura o teto de 6000 e a mensagem inteira volta 400.
    Aqui o lote fecha no que vier primeiro -- dez embeds ou o orcamento.
    """
    lotes: list[list[dict]] = []
    atual: list[dict] = []
    tamanho = 0

    for job in novas:
        embed = montar_embed(job)
        custo = _tamanho_embed(embed)
        # `atual and` garante que um embed sozinho maior que o orcamento vá
        # numa mensagem propria, em vez de travar o laco ou sumir do aviso.
        if atual and (len(atual) >= LIMITE_POR_MENSAGEM
                      or tamanho + custo > ORCAMENTO_MENSAGEM):
            lotes.append(atual)
            atual, tamanho = [], 0
        atual.append(embed)
        tamanho += custo

    if atual:
        lotes.append(atual)

    mensagens = []
    for indice, lote in enumerate(lotes, start=1):
        cabecalho = titulo if len(lotes) == 1 else f"{titulo} ({indice}/{len(lotes)})"
        mensagens.append({
            "content": f"**{cabecalho}** — {len(lote)} vaga(s)",
            "embeds": lote,
        })
    return mensagens


def enviar(webhook: str, mensagens: list[dict], session=None) -> int:
    """Publica no webhook. Devolve quantas mensagens sairam."""
    import requests

    enviador = session or requests
    enviadas = 0
    for payload in mensagens:
        resposta = enviador.post(webhook, json=payload, timeout=30)
        if resposta.status_code >= 400:
            logger.error(
                "Discord recusou a mensagem (HTTP %s): %s",
                resposta.status_code, resposta.text[:200],
            )
            break
        enviadas += 1
    return enviadas
