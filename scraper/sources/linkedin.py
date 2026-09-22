"""Coletor do LinkedIn Jobs pela API de convidado (sem login).

    GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
        ?keywords=<termo>&geoId=106057199&start=<n>

E o endpoint que o proprio site chama para carregar mais resultados na busca
publica. Devolve um fragmento HTML com 10 cards por chamada, e responde 200 ate
com o User-Agent do projeto -- nao exige navegador nem sessao.

**A localizacao precisa ser o geoId.** Passar `location=Brasil` (em portugues)
falha em silencio: a API responde 200 e devolve vagas dos Estados Unidos
("Brooklyn, NY", "San Francisco Bay Area"). `location=Brazil` em ingles filtra
quase tudo, mas o geoId e o unico que acertou 10 de 10 nos testes.

O card da busca **nao traz a descricao da vaga**, e a modalidade (presencial,
hibrido, remoto) quase sempre so aparece escrita nela -- sem ela, a vaga fica
"nao informado" e o filtro de remotas a descarta. Por isso, depois da busca, o
coletor pede a pagina de detalhe de cada candidata:

    GET https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/<id>

So das vagas que o pipeline nao descartaria pelo que o card ja diz (nivel de
entrada e idade, com as mesmas funcoes do pipeline), uma vez por id, no maximo
`Settings.linkedin_max_detalhes` por coleta, e parando depois de
`FALHAS_SEGUIDAS_MAX` falhas seguidas (sinal de bloqueio). A falha no detalhe
nao derruba nada: a vaga segue sem descricao, como antes.

**O `robots.txt` do LinkedIn proibe `/jobs-guest/`** (e `Disallow: /` para
qualquer robo), tanto a busca quanto o detalhe. Buscar o detalhe foi decisao
consciente do mantenedor, a mesma do projeto irmao (vagas-tech-junior, ADR
0010), e e a excecao registrada no CLAUDE.md. Os termos do LinkedIn proibem
copiar o conteudo, entao a descricao classifica a vaga mas nao vai para o
Discord (`reproduzir_descricao=False`).

Esta e a fonte com maior chance de passar a bloquear no futuro. Se isso
acontecer, `PoliteSession.get` devolve None, o coletor devolve o que tiver e a
coleta das outras fontes segue normalmente.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..classifier import default_classifier
from ..datas import filtrar_recentes
from ..locais import Local, serve
from ..modalidade import completar_modalidade
from ..models import NAO_INFORMADO, REMOTO, Job, normalize
from ..seniority import filter_entry_level
from .base import JobSource

logger = logging.getLogger(__name__)

API_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)

# geoId do Brasil no LinkedIn. Ver o docstring: o nome do pais em portugues
# nao filtra nada e traz vagas dos EUA sem qualquer aviso.
GEO_ID_BRASIL = "106057199"

DETALHE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"

RESULTADOS_POR_PAGINA = 10

# Falhas seguidas no detalhe que indicam bloqueio: dali em diante, para de pedir.
FALHAS_SEGUIDAS_MAX = 3

_ID_RE = re.compile(r"(\d+)$")
_WS_RE = re.compile(r"\s+")


class LinkedInSource(JobSource):
    name = "linkedin"
    label = "LinkedIn Jobs"

    def fetch(self, terms: list[str]) -> list[Job]:
        """Busca todos os termos e depois completa a descricao das candidatas."""
        jobs = super().fetch(terms)
        self._completar_descricoes(jobs)
        return jobs

    def _candidatas(self, jobs: list[Job]) -> list[Job]:
        """Corta o que o pipeline cortaria, para nao pedir detalhe em vao.

        O portao de tecnologia fica de fora: ele le a descricao, que ainda nao
        veio, e cortaria vaga que passaria com ela.
        """
        jobs = filter_entry_level(jobs)
        if self.settings.dias_max > 0:
            jobs = filtrar_recentes(jobs, self.settings.dias_max)
        # So titulo e local nesta altura: "Dev Jr (Remoto)" ja nao precisa do
        # detalhe para passar no filtro.
        completar_modalidade(jobs)
        return sorted(jobs, key=self._prioridade)

    def _prioridade(self, job: Job) -> tuple[bool, bool]:
        """Onde o detalhe muda mais o resultado vem antes do teto cortar.

        Numa coleta real, 475 candidatas para um teto de 100. Primeiro as de
        titulo de tecnologia que o filtro de remotas descartaria: ali a
        descricao decide se a vaga chega ao Discord. Depois as que ja passam
        (ganham area e tecnologias). Por ultimo as de titulo sem sinal de
        tecnologia, que so a descricao poderia salvar no portao.
        """
        titulo_tech = default_classifier().is_tech(job.title)
        return (not titulo_tech, serve(job, self.locais))

    def _completar_descricoes(self, jobs: list[Job]) -> None:
        # A mesma vaga volta em varios termos e locais: um detalhe por id.
        por_id: dict[str, list[Job]] = {}
        for job in jobs:
            por_id.setdefault(job.external_id, []).append(job)

        ids = [j.external_id for j in self._candidatas([g[0] for g in por_id.values()])]
        teto = max(self.settings.linkedin_max_detalhes, 0)
        if len(ids) > teto:
            logger.info("[linkedin] %d candidatas, detalhe so das %d primeiras",
                        len(ids), teto)
        ids = ids[:teto]

        obtidas = falhas = seguidas = 0
        for external_id in ids:
            descricao = self._buscar_descricao(external_id)
            if descricao is None:
                falhas += 1
                seguidas += 1
                if seguidas >= FALHAS_SEGUIDAS_MAX:
                    logger.warning("[linkedin] %d falhas seguidas no detalhe; "
                                   "parando (possivel bloqueio)", seguidas)
                    break
                continue
            seguidas = 0
            obtidas += 1
            for job in por_id[external_id]:
                job.description = descricao
        logger.info("[linkedin] detalhe: %d descricoes obtidas, %d falhas, de %d pedidas",
                    obtidas, falhas, len(ids))

    def _buscar_descricao(self, external_id: str) -> str | None:
        """Descricao da pagina de detalhe; None se a requisicao ou o parse falhar."""
        response = self.session.get(DETALHE_URL.format(id=external_id))
        if response is None:
            return None
        return self._parse_descricao(response.text)

    @staticmethod
    def _parse_descricao(html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        corpo = soup.select_one("div.show-more-less-html__markup")
        if corpo is None:
            return None
        texto = _WS_RE.sub(" ", corpo.get_text(" ", strip=True)).strip()
        return texto or None

    def fetch_term(self, term: str) -> list[Job]:
        return self._paginar(keywords=term, geo_id=GEO_ID_BRASIL, term=term)

    def fetch_local(self, local: Local, terms: list[str]) -> list[Job]:
        """Os mesmos termos, trocando o geoId do Brasil pelo do local."""
        if not local.linkedin_geo_id:
            return []
        jobs: list[Job] = []
        for term in terms:
            jobs.extend(self._paginar(keywords=term,
                                      geo_id=local.linkedin_geo_id,
                                      term=term, local_slug=local.slug))
        return jobs

    def _paginar(self, keywords: str, geo_id: str, term: str = "",
                 local_slug: str = "") -> list[Job]:
        jobs: list[Job] = []
        seen: set[str] = set()

        for page in range(self.settings.max_pages_per_term):
            response = self.session.get(
                API_URL,
                params={
                    "keywords": keywords,
                    "geoId": geo_id,
                    "start": page * RESULTADOS_POR_PAGINA,
                },
            )
            if response is None:
                break

            batch = self._parse_page(response.text, term, local_slug)
            if not batch:
                break

            novos = 0
            for job in batch:
                if job.external_id in seen:
                    continue
                seen.add(job.external_id)
                jobs.append(job)
                novos += 1

            if novos == 0:
                break  # a API comecou a repetir resultados

        return jobs

    def _parse_page(self, html: str, term: str,
                    local_slug: str = "") -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[Job] = []
        for card in soup.select("div.base-card"):
            job = self._parse_card(card, term, local_slug)
            if job is not None:
                jobs.append(job)
        return jobs

    def _parse_card(self, card, term: str,
                    local_slug: str = "") -> Job | None:
        urn = card.get("data-entity-urn") or ""
        match = _ID_RE.search(urn)
        title = self._text(card.select_one("h3.base-search-card__title"))
        if match is None or not title:
            return None

        link = card.select_one("a.base-card__full-link")
        url = (link.get("href") or "").split("?")[0] if link else ""

        momento = card.select_one("time")
        publicada = (momento.get("datetime") or "") if momento else ""

        location = self._text(card.select_one("span.job-search-card__location"))

        return Job(
            source=self.name,
            external_id=match.group(1),
            title=title,
            company=self._text(card.select_one("h4.base-search-card__subtitle")),
            url=url,
            description="",  # o card nao traz; `fetch` completa pelo detalhe
            location=location,
            workplace_type=self._modalidade(location),
            published_date=publicada[:10],
            search_term=term,
            local_consultado=local_slug,
            # Os termos do LinkedIn proibem copiar o conteudo; ver o modulo.
            reproduzir_descricao=False,
        )

    @staticmethod
    def _modalidade(location: str) -> str:
        """So afirma remoto quando o proprio texto do local diz isso.

        O card nao tem campo de modalidade; presencial e hibrido sao
        indistinguiveis aqui, entao ficam como nao informado em vez de chute.
        O pipeline tenta de novo pelo texto da descricao (`scraper/modalidade.py`).
        """
        texto = normalize(location)
        if "remoto" in texto or "remote" in texto:
            return REMOTO
        return NAO_INFORMADO

    @staticmethod
    def _text(node) -> str:
        if node is None:
            return ""
        return _WS_RE.sub(" ", node.get_text(" ", strip=True)).strip()
