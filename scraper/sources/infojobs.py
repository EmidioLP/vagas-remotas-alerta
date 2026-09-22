"""Coletor do InfoJobs Brasil (infojobs.com.br).

A listagem de busca e renderizada no servidor -- os cards ja vem no HTML, como
no Vagas.com. `requests` + BeautifulSoup bastam, e o User-Agent do projeto
passa sem 403 (medido em 22/09/2026, de IP residencial -- ainda NAO foi medido
a partir do runner do GitHub Actions, que e IP de datacenter; foi assim que a
ProgramaThor caiu, entao a primeira execucao no workflow precisa ser conferida).

O `robots.txt` nao proibe nenhum caminho de busca nem as paginas de vaga; o que
ele bloqueia e `/App_WebServices`, `/*.ashx$`, `/candidate`, `/company`,
`/detailvacancy.aspx` e `/Concursos` -- nada disso e usado aqui. Nao ha
`Crawl-delay` nem `Sitemap:` declarado (`/sitemap.xml` responde 404), entao a
descoberta e por busca paginada, e nao por sitemap como na GeekHunter.

**A descricao nao vai para o Discord.** Os termos do portal, em
`/legal/aviso-legal-para-candidatos__15727.aspx`, proibem tanto o proprio
crawler ("copias mediante tecnologias de buscador tipo 'Robot/Crawler' (...)
estao expressamente proibidas") quanto reproduzir o conteudo ("e proibido a
reproducao, distribuicao, transmissao, adaptacao ou modificacao (...) do
conteudo do Portal"). A escolha do projeto foi coletar so o que o card ja
mostra e nunca republicar o texto: `reproduzir_descricao=False`, como no
Mentora Dados. O resumo do card ainda classifica a vaga; o aviso leva titulo,
empresa, local, modalidade, data e link. Nenhuma requisicao por vaga e feita --
a pagina de detalhe nao e aberta, o que tambem deixa a coleta inteira em ~53
requisicoes.

Duas superficies de busca, as duas medidas em 22/09/2026:

  - **Remotas**: `/vagas-de-emprego-<termo>-trabalho-home-office.aspx`. E a
    unica listagem de modalidade que o proprio site marca `rel="follow"`; as de
    presencial e hibrido so existem como `?idw=1` e `?idw=3`, com `rel=nofollow`.
    Filtra de verdade: "python" devolve 70 vagas contra 233 na listagem geral.
    Nos 13 termos do projeto deu 74 cards na pagina 1, e so "estagio
    desenvolvimento" encheu a pagina de 20.
  - **Por cidade**: `/vagas-de-emprego-<termo>-em-<cidade>,-<uf>.aspx`.

**A consulta por cidade NAO prova o local, e por isso `local_consultado` fica
vazio aqui.** O portal completa a pagina com vaga de qualquer canto quando a
cidade tem pouco resultado: nos 13 termos, `natal,-rn` devolveu 88 cards dos
quais 83 nao eram de Natal (110 "Todo Brasil" e 28 "Sao Paulo - SP" no total
das tres cidades), e `devops junior em natal,-rn` devolveu uma unica vaga, de
"Todo Brasil". O portal conta essas vagas como resultado ("1 Vaga de Emprego de
devops junior em Natal - RN" no cabecalho) e nao as marca de nenhum jeito --
`data-typesimilar` vem vazio tanto nelas quanto nos acertos. Quem prova o local
e o texto do card, que sempre traz cidade e UF ("Natal - RN", "Fortaleza - CE")
e casa com o reconhecedor de `locais.py`. Confiar na consulta aqui repetiria o
erro do Trampos.

Armadilhas, todas medidas e tratadas abaixo:

  - **Cidade errada nao da 404, da Sao Paulo.** `/empregos-em-natal.aspx` (sem a
    UF) e `/empregos-em-cidadequenaoexistexyz,-rn.aspx` respondem 200 e
    redirecionam para `/empregos-em-sao-paulo.aspx`. So `cidade,-uf` e honrado.
    Dai o `_sem_desvio`: e ele que transforma local invalido em zero vaga, que
    e a prova que o projeto exige antes de usar consulta por local.
  - **`page=N` nao funciona na pagina HTML.** `?page=2`, `?pagina=2`, `?p=2` e
    mais oito variantes devolvem 200 com a mesma primeira vaga. A paginacao real
    e o fragmento abaixo, que devolve a mesma marcacao de card num envelope
    JSON -- por isso o parser e um so.
  - O parametro de palavra-chave de `/empregos.aspx` e `palabra` (espanhol,
    heranca do InfoJobs ES); `palavra` e ignorado e cai no default de Sao Paulo.
    Nao usamos nenhum dos dois: a forma em slug e a canonica do site.
  - Nao existe nivel "Junior" no filtro `im` do portal (so `1=Estagiario`,
    `5=Trainee`, `6=Analista`...), entao `job.seniority` fica vazio e quem
    decide e o regex de `seniority.py`.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from ..datas import normalizar_data
from ..locais import Local
from ..models import NAO_INFORMADO, Job, normalize, normalize_workplace
from .base import JobSource

logger = logging.getLogger(__name__)

PORTAL_URL = "https://www.infojobs.com.br"
# Paginacao: recebe a URL da listagem com `?page=N` e devolve
# {"eof": bool, "listFragmentHTML": "<div class='js_vacanciesGridFragment'>..."}.
FRAGMENTO_URL = f"{PORTAL_URL}/mf-publicarea/VacancyList/GetVacancyListFragment"
# ROWSPERPAGE do bundle de listagem do portal; confirmado no fragmento, que
# devolveu exatamente 20 cards.
PAGE_SIZE = 20

_WS_RE = re.compile(r"\s+")
# O campo escondido do card vem "2026/09/21 12:44:00"; `normalizar_data` le ISO
# com hifen, entao so a barra precisa virar hifen.
_DATA_COM_BARRA = re.compile(r"^\d{4}/\d{2}/\d{2}$")


def slugify_term(term: str) -> str:
    """'desenvolvedor junior' -> 'desenvolvedor-junior' (formato da URL do site)."""
    return re.sub(r"\s+", "-", normalize(term)).strip("-")


def _texto(node) -> str:
    if node is None:
        return ""
    return _WS_RE.sub(" ", node.get_text(" ", strip=True)).strip()


class InfoJobsSource(JobSource):
    name = "infojobs"
    label = "InfoJobs"

    def fetch_term(self, term: str) -> list[Job]:
        """So a listagem de home office: e o que o funil quer, e custa menos."""
        return self._paginar(
            f"{PORTAL_URL}/vagas-de-emprego-{slugify_term(term)}"
            f"-trabalho-home-office.aspx",
            term=term,
        )

    def fetch_local(self, local: Local, terms: list[str]) -> list[Job]:
        """Listagem da cidade, com os mesmos termos da busca nacional.

        Nao passa `local_slug`: aqui a consulta nao e prova de local (ver o
        docstring do modulo). Quem aceita a vaga e o texto do card.
        """
        jobs: list[Job] = []
        for cidade in local.infojobs_cidades:
            for term in terms:
                jobs.extend(self._paginar(
                    f"{PORTAL_URL}/vagas-de-emprego-{slugify_term(term)}"
                    f"-em-{cidade}.aspx",
                    term=term,
                ))
        return jobs

    def _paginar(self, url: str, term: str) -> list[Job]:
        jobs: list[Job] = []
        vistos: set[str] = set()

        for pagina in range(1, self.settings.max_pages_per_term + 1):
            recebido = self._pagina(url, pagina)
            if recebido is None:
                break
            html, fim = recebido

            batch = self._parse_page(html, term)
            novas = 0
            for job in batch:
                if job.external_id in vistos:
                    continue
                vistos.add(job.external_id)
                jobs.append(job)
                novas += 1

            if novas == 0:
                break  # pagina repetida ou vazia
            if fim:
                break  # o portal avisou que acabou (`eof`)
            if len(batch) < PAGE_SIZE:
                break  # ultima pagina

        return jobs

    def _pagina(self, url: str, pagina: int) -> tuple[str, bool] | None:
        """Devolve (html, acabou) da pagina pedida, ou None quando nao da.

        A pagina 1 e a propria URL, porque so nela da para ver se o portal
        honrou a consulta ou desviou para Sao Paulo. Da 2 em diante o `page`
        so funciona pelo fragmento.
        """
        if pagina == 1:
            resposta = self.session.get(url)
            if resposta is None:
                return None
            if not self._sem_desvio(url, resposta.url):
                logger.info("[%s] %s desviou para %s; consulta descartada",
                            self.name, url, resposta.url)
                return None
            return resposta.text, False

        payload = self.session.get_json(FRAGMENTO_URL,
                                        params={"url": f"{url}?page={pagina}"})
        if not isinstance(payload, dict):
            return None
        return payload.get("listFragmentHTML") or "", bool(payload.get("eof"))

    @staticmethod
    def _sem_desvio(pedida: str, final: str) -> bool:
        """O portal respondeu a consulta pedida, e nao outra?

        Cidade que ele nao reconhece nao vira 404: vira 200 com Sao Paulo.
        Medido com `/empregos-em-natal.aspx` (sem a UF) e com
        `/empregos-em-cidadequenaoexistexyz,-rn.aspx`, que caem os dois em
        `/empregos-em-sao-paulo.aspx`. Aceitar a resposta assim mesmo poria
        vaga de outro estado no aviso.
        """
        return (unquote(urlsplit(final).path).lower()
                == unquote(urlsplit(pedida).path).lower())

    def _parse_page(self, html: str, term: str) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[Job] = []
        # So os cards do grid de resultados. O rodape tem "Cargos Similares",
        # que sao links de busca, e nao vagas.
        for card in soup.select("div.js_vacanciesGridFragment div.js_cardLink"):
            job = self._parse(card, term)
            if job is not None:
                jobs.append(job)
        return jobs

    def _parse(self, card, term: str) -> Job | None:
        identificador = card.get("data-id")
        titulo = _texto(card.select_one("h2.js_vacancyTitle"))
        if not identificador or not titulo:
            return None

        href = card.get("data-href") or ""
        return Job(
            source=self.name,
            external_id=str(identificador),
            title=titulo,
            company=self._empresa(card),
            url=f"{PORTAL_URL}{href}" if href.startswith("/") else href,
            description=_texto(card.select_one(
                "div.text-medium:not(.d-inline-flex):not(.small)")),
            location=self._local(card),
            workplace_type=self._modalidade(card),
            published_date=self._data(card),
            search_term=term,
            # Os termos do portal proibem reproduzir o conteudo; ver o modulo.
            reproduzir_descricao=False,
        )

    @staticmethod
    def _empresa(card) -> str:
        """Nome da empresa, que nem sempre e um link.

        Tres formas medidas: link para a pagina da empresa
        (`/empresa-grupo-easy__-57056.aspx`), link para a pagina propria dela
        no portal (`/printi`), e texto solto "Empresa confidencial", sem `<a>`
        nenhum. Por isso quem e lido e o bloco, e nao o link -- pegar so o `<a>`
        deixava a vaga confidencial sem empresa. O nome vem quebrado por um
        `<span>` por causa do selo de verificacao, e `get_text` junta.
        """
        return _texto(card.select_one("div.d-flex.align-items-baseline "
                                      "div.text-body"))

    @staticmethod
    def _local(card) -> str:
        """Cidade e UF, sem o "a N Km de voce" que o card carrega escondido.

        O trecho da distancia e um `<span hidden>` irmao do texto, e o portal
        so o preenche com a geolocalizacao do navegador. `get_text` traria
        ", 0 Km de voce" junto e sujaria o reconhecedor de local, entao aqui
        so os filhos de texto diretos entram.
        """
        no = card.select_one("div.mb-8:not(.d-inline-flex)")
        if no is None:
            return ""
        return _WS_RE.sub(
            " ", "".join(no.find_all(string=True, recursive=False))).strip()

    @staticmethod
    def _modalidade(card) -> str:
        """Modalidade declarada no card, na tira de atributos da vaga.

        O InfoJobs escreve "Home office", "Presencial" ou "Hibrido" ao lado do
        salario, do tempo de experiencia e da escolaridade. Diferente do
        Vagas.com, aqui o card distingue as tres, entao a hibrida e afirmada em
        vez de virar "nao informado". Medido em 269 cards das consultas por
        cidade: 191 "Home office", 62 "Presencial" e 16 "Hibrido".

        Os outros atributos da tira nao casam com nenhuma modalidade ("A
        combinar", "Entre 1 e 3 anos", "Ensino Superior"), entao o primeiro que
        `normalize_workplace` reconhece e o certo.
        """
        for atributo in card.select("div.d-inline-flex.mb-8 > div"):
            modalidade = normalize_workplace(_texto(atributo))
            if modalidade != NAO_INFORMADO:
                return modalidade
        return NAO_INFORMADO

    @staticmethod
    def _data(card) -> str:
        """Data de publicacao, do campo escondido do card.

        O `data-value` de `div.js_date` traz "2026/09/21 12:44:00", exato. O
        texto visivel e pior -- "17 set" nao tem ano, e `normalizar_data` nao
        reconhece mes por extenso --, mas cobre "Hoje" e "Ontem" quando o campo
        escondido falta. Sem os dois, fica "" e a vaga sobrevive ao filtro de
        idade, que e a direcao deliberada do projeto.
        """
        escondido = card.select_one("div.js_date")
        bruto = ((escondido.get("data-value") or "") if escondido else "")[:10]
        if _DATA_COM_BARRA.match(bruto):
            return normalizar_data(bruto.replace("/", "-"))
        return normalizar_data(_texto(card.select_one("div.text-medium.small")))
