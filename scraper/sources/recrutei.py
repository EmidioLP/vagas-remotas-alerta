"""Coletor do Recrutei Empregos (empregos.recrutei.com.br).

Agregador das vagas publicadas pelas consultorias de R&S que usam a plataforma
Recrutei. As listagens sao renderizadas no servidor -- os cards ja vem no HTML,
como no Vagas.com e no InfoJobs --, entao `requests` + BeautifulSoup bastam, e o
User-Agent do projeto passa sem 403 (medido em 22/09/2026, de IP residencial;
ainda NAO foi medido a partir do runner do GitHub Actions, que e IP de
datacenter -- foi assim que a ProgramaThor caiu).

**Esta fonte nao tem busca por termo, e o `robots.txt` e quem decide isso.** O
formulario do portal e `GET /busca?keyword=<termo>&city=<cidade>`, e o
`robots.txt` bloqueia exatamente essa forma:

    Disallow: /api/  /recrutest/  /candidato/  /empresa/  /r/knowledge/
    Disallow: /*?*keyword=*
    Disallow: /*?*q=*

O que sobra -- e e o suficiente -- sao as listagens por caminho, que nao sao
bloqueadas, assim como `?page=`, `?model=`, `?setor=` e `?state=`. Por isso
`fetch_term` devolve `[]` e o `fetch` daqui e reescrito, como no Quero Vagas
Tech, no lugar de fingir uma busca textual que o portal proibe.

Tres superficies, todas medidas em 22/09/2026:

  - **Remotas**: `/vagas-de-trabalho-remoto-home-office` -- 134 vagas em 12
    paginas de 12, TODAS com o selo "Remoto". E o `model=remote` do filtro
    lateral, em caminho limpo. Como o funil so quer remotas (fora RN e
    Fortaleza), varrer o acervo inteiro por categoria seria desperdicio: so
    `/vagas/tecnologia` tem 44 paginas, e a taxonomia do portal e barulhenta
    ("Atendente - area da saude" aparece em tecnologia).
  - **Estado**: `/vagas/em/rn` -- 12 vagas, todas de Natal; `?page=2` devolve
    zero card. A UF cobre Natal e Mossoro de uma vez.
  - **Cidade**: `/vagas/em/fortaleza-ce` -- 43 vagas em 4 paginas.

**A consulta por local filtra de verdade, mas `local_consultado` fica vazio
assim mesmo.** Lugar inventado da 404 (`/vagas/em/cidade-inventada-xy`), que e a
prova que o projeto exige -- diferente do Trampos, cujo `lc` muda o resultado
sem filtrar, e do InfoJobs, que desvia para Sao Paulo. O que impede confiar na
consulta e outra coisa: `fortaleza-ce` traz a regiao metropolitana. Dos 43
cards, 12 nao eram de Fortaleza (7 de Eusebio, 5 de Maracanau). Quem prova o
local aqui e o texto do card, que sempre traz "Cidade, UF, Brasil".

**A descricao e buscada vaga a vaga, porque o card nao tem nenhuma.** O card
mostra titulo, empresa, local, salario, data e selos -- e so. Isso derruba o
portao tech: "ENGENHEIRO DE IA JR" e reprovado por `is_tech` com o titulo
sozinho e aprovado com a descricao (Backend, score 8.0, casando "python",
"postgresql", "backend", "apis"). A pagina de cada vaga traz um `JobPosting` em
JSON-LD com `description`, `datePosted` (ISO com hora, mais exato que o "ha 1
mes" do card), `skills` e `jobLocation`. Entao vale o padrao da GeekHunter e do
Quero Vagas Tech: pre-filtrar pelo que a listagem ja informa e so entao abrir a
pagina das que sobraram -- 6 das 189 na medicao de hoje. O pre-filtro chama as
MESMAS funcoes do pipeline, nunca copias.

**A descricao pode ir para o Discord.** Os termos de uso
(`https://api.recrutei.com.br/files/termos.pdf`, 3 paginas, 10 clausulas, em
host cujo `robots.txt` libera tudo) sao dirigidos ao candidato: tratam de
cadastro, bloqueio, e-mails e foro. Nao ha clausula proibindo crawler, acesso
automatizado nem reproducao de conteudo -- a clausula 7 so reserva as marcas e a
propriedade intelectual da Recrutei. E a descricao sai do JSON-LD, marcacao que
o portal publica justamente para ser sindicada. Por isso `reproduzir_descricao`
fica no padrao `True`, ao contrario do InfoJobs e do Mentora Dados.

Armadilhas, todas medidas e tratadas abaixo:

  - **"Presencial ou Remoto" nao e remoto.** O portal distingue quatro
    modalidades no filtro lateral (`model=remote`, `presential`,
    `presential-remote`, `hybrid`) e deixa `presential-remote` de fora da
    propria listagem de home office. `normalize_workplace` leria o selo como
    REMOTO, porque procura "remoto" dentro da string -- dai o de-para explicito
    em `MODALIDADES`.
  - Pagina alem do fim responde 200 com zero card (`?page=99`), e nao repete a
    primeira -- por isso a parada por pagina vazia e confiavel.
  - O link do card vem com query de rastreio (`?has_bot=1`,
    `?utm_source=recrutei-empregos-premium`), que e descartada: o id da vaga
    esta no caminho, e a pagina responde 200 sem a query.
  - O portal nao declara nivel nenhum no card, entao `job.seniority` fica vazio
    e quem decide e o regex de `seniority.py`.
"""

from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from ..datas import filtrar_recentes, normalizar_data
from ..locais import resolver, serve_presencialmente
from ..models import (
    HIBRIDO,
    NAO_INFORMADO,
    PRESENCIAL,
    REMOTO,
    Job,
    normalize,
    strip_html,
)
from ..seniority import filter_entry_level
from .base import JobSource

logger = logging.getLogger(__name__)

PORTAL_URL = "https://empregos.recrutei.com.br"
LISTAGEM_REMOTA = f"{PORTAL_URL}/vagas-de-trabalho-remoto-home-office"

# 12 cards por pagina, medido nas 12 paginas de remotas e nas 4 de Fortaleza.
PAGE_SIZE = 12
# Teto de seguranca: as remotas cabem em 12 paginas hoje.
MAX_PAGINAS = 30

# O portal separa "Remoto" de "Presencial ou Remoto" no proprio filtro lateral
# e deixa o segundo fora da listagem de home office -- ele nao considera aquilo
# remoto, e nem o projeto. `normalize_workplace` leria o selo como REMOTO, so
# por achar "remoto" na string, entao aqui o de-para e explicito.
MODALIDADES = {
    "remoto": REMOTO,
    "presencial": PRESENCIAL,
    "hibrido": HIBRIDO,
    "presencial ou remoto": HIBRIDO,
}

# `/vaga/<empresa>/<id>-<slug>`: o id da vaga e o numero antes do primeiro
# hifen do ultimo segmento.
_ID_NO_CAMINHO = re.compile(r"/vaga/[^/]+/(\d+)-")
_WS_RE = re.compile(r"\s+")


def _texto(node) -> str:
    if node is None:
        return ""
    return _WS_RE.sub(" ", node.get_text(" ", strip=True)).strip()


class RecruteiSource(JobSource):
    name = "recrutei"
    label = "Recrutei Empregos"

    def fetch(self, terms: list[str]) -> list[Job]:
        """Ignora os termos: o `robots.txt` fecha a busca por palavra-chave."""
        if terms:
            logger.debug("[%s] termos ignorados; o robots.txt bloqueia "
                         "/busca?keyword=", self.name)

        listadas = self._superficie(LISTAGEM_REMOTA, "remotas")
        for local in self.locais:
            for caminho in local.recrutei_caminhos:
                listadas.extend(self._superficie(
                    f"{PORTAL_URL}/vagas/em/{caminho}", f"local:{local.slug}"))

        # Uma remota sediada em Natal aparece nas duas listagens; sem isto a
        # pagina dela seria aberta duas vezes.
        unicas = self._sem_repetidas(listadas)
        candidatas = self._pre_filtrar(unicas)

        for job in candidatas:
            try:
                self._preencher_detalhe(job)
            except Exception as exc:  # uma vaga nao derruba a coleta
                message = f"{self.name}/{job.external_id}: {exc}"
                logger.warning("Erro buscando descricao de %s", message)
                self.stats.errors.append(message)

        logger.info("[%s] %d listadas -> %d candidatas -> %d com descricao",
                    self.name, len(unicas), len(candidatas),
                    sum(1 for j in candidatas if j.description))
        self.stats.raw_jobs = len(candidatas)
        self.stats.requests_made = self.session.request_count
        return candidatas

    def fetch_term(self, term: str) -> list[Job]:
        """Nao usado: o `robots.txt` bloqueia `/busca?keyword=`."""
        return []

    def _superficie(self, base: str, rotulo: str) -> list[Job]:
        """Uma listagem inteira, com a falha dela isolada das outras."""
        try:
            jobs = self._listar(base)
        except Exception as exc:  # o mesmo isolamento que `JobSource.fetch` da
            message = f"{self.name}/{rotulo}: {exc}"
            logger.warning("Erro coletando %s", message)
            self.stats.errors.append(message)
            return []
        logger.info("[%s] %s -> %d vagas", self.name, rotulo, len(jobs))
        return jobs

    def _listar(self, base: str) -> list[Job]:
        jobs: list[Job] = []
        vistos: set[str] = set()

        for pagina in range(1, MAX_PAGINAS + 1):
            url = base if pagina == 1 else f"{base}?page={pagina}"
            resposta = self.session.get(url)
            if resposta is None:
                break

            batch = self._parse_page(resposta.text)
            novas = 0
            for job in batch:
                if job.external_id in vistos:
                    continue
                vistos.add(job.external_id)
                jobs.append(job)
                novas += 1

            if novas == 0:
                break  # pagina vazia (`?page=99`) ou repetida
            if len(batch) < PAGE_SIZE:
                break  # ultima pagina

        return jobs

    def _parse_page(self, html: str) -> list[Job]:
        sopa = BeautifulSoup(html, "html.parser")
        cards = sopa.select("div.list-grid-item")
        return [job for job in (self._parse(c) for c in cards) if job is not None]

    def _parse(self, card) -> Job | None:
        link = card.select_one("a.job-title")
        titulo = _texto(link)
        href = (link.get("href") or "") if link else ""
        # A query e so rastreio (`?has_bot=1`, `?utm_source=...`); o id esta no
        # caminho, e a pagina responde 200 sem ela.
        endereco = href.split("?")[0]
        achado = _ID_NO_CAMINHO.search(endereco)
        if not titulo or not achado:
            return None

        return Job(
            source=self.name,
            external_id=achado.group(1),
            title=titulo,
            company=self._campo(card, "mdi-bank"),
            url=endereco,
            location=self._campo(card, "mdi-map-marker"),
            workplace_type=self._modalidade(card),
            published_date=normalizar_data(self._campo(card, "mdi-clock-outline")),
        )

    @staticmethod
    def _campo(card, icone: str) -> str:
        """Empresa, local e data sao `<p>` irmaos, distinguidos pelo icone."""
        for paragrafo in card.select("div.grid-list-desc p"):
            if paragrafo.select_one(f"i.{icone}"):
                return _texto(paragrafo)
        return ""

    @staticmethod
    def _modalidade(card) -> str:
        """O primeiro selo que e modalidade; os outros sao regime e PCD.

        Medido nas 134 remotas: cada card traz um selo de regime ("CLT",
        "Pessoa Juridica", "Cooperado", "CLT ou PJ", "Estagio") antes do selo
        de modalidade, e 5 deles vieram so com a modalidade.
        """
        for selo in card.select("span.badge"):
            modalidade = MODALIDADES.get(normalize(_texto(selo)))
            if modalidade:
                return modalidade
        return NAO_INFORMADO

    @staticmethod
    def _sem_repetidas(jobs: list[Job]) -> list[Job]:
        vistos: set[str] = set()
        unicas: list[Job] = []
        for job in jobs:
            if job.external_id in vistos:
                continue
            vistos.add(job.external_id)
            unicas.append(job)
        return unicas

    def _pre_filtrar(self, jobs: list[Job]) -> list[Job]:
        """Corta o que o pipeline cortaria, para nao abrir pagina em vao.

        So usa o que a listagem ja informou. As funcoes sao as do pipeline de
        proposito: se a regra mudar la, muda aqui junto.
        """
        jobs = filter_entry_level(jobs)

        if self.settings.dias_max > 0:
            jobs = filtrar_recentes(jobs, self.settings.dias_max)

        if self.settings.somente_remotas:
            locais = resolver(self.settings.locais_presenciais)
            jobs = [j for j in jobs
                    if j.workplace_type == REMOTO
                    or serve_presencialmente(j, locais)]

        return jobs

    def _preencher_detalhe(self, job: Job) -> None:
        """Descricao e data exata, do `JobPosting` em JSON-LD da pagina."""
        resposta = self.session.get(job.url)
        if resposta is None:
            return

        dados = self._job_posting(resposta.text)
        if dados is None:
            logger.debug("[%s] %s sem JobPosting na pagina", self.name, job.url)
            return

        job.description = strip_html(dados.get("description") or "")
        # O card data em texto relativo ("ha 1 mes"); aqui vem a data exata.
        publicada = normalizar_data((dados.get("datePosted") or "")[:10])
        if publicada:
            job.published_date = publicada

    @staticmethod
    def _job_posting(html: str) -> dict | None:
        """A pagina tambem traz um `BreadcrumbList` no mesmo formato."""
        sopa = BeautifulSoup(html, "html.parser")
        for script in sopa.select('script[type="application/ld+json"]'):
            try:
                dados = json.loads(script.string or "")
            except (ValueError, TypeError):
                continue
            if isinstance(dados, dict) and dados.get("@type") == "JobPosting":
                return dados
        return None
