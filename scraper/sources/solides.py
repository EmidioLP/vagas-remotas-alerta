"""Coletor da Solides (ATS com portal publico de vagas).

Endpoint usado: o mesmo JSON que o front de https://vagas.solides.com.br
chama no browser, sem autenticacao:

    GET https://apigw.solides.com.br/jobs/v3/portal-vacancies

O envelope e aninhado: `data.data` traz a lista, e `data` tambem carrega
`count`, `currentPage` e `totalPages`.

Diferente das outras fontes, esta NAO usa os termos de busca do projeto: o
portal tem filtros nativos de area e de nivel, que entregam o mesmo recorte
com menos requisicao e sem depender de casar texto. O que cada filtro faz foi
medido contra a API ao vivo (21/09/2026), porque varios deles mentem:

  - `occupationAreas=tecnologia` recorta a area. E generoso: junto com vaga de
    TI vem "Vendedor Externo", "Assistente Administrativo" e "Gestor de
    Trafego Pago". Nao e problema -- quem descarta isso e o portao de
    relevancia do pipeline, que existe para exatamente isso.
  - `seniorities=junior` filtra de verdade: 1.103 vagas em 111 paginas, contra
    3.639 sem filtro.
  - `seniorities=estagio` devolve ZERO, e `estagiario`, `trainee` e `aprendiz`
    devolvem as mesmas 3.639 de `seniorities=ValorInventadoXYZ`. Ou seja, o
    parametro so entende `junior` e ignora o resto em silencio. Por isso
    estagio/trainee/aprendiz entram por `title=`.
  - `title=` filtra de verdade (`title=TermoQueNaoExisteXYZ` devolve zero) e
    casa por palavra inteira: `estagio` (113) NAO cobre `estagiario` (119).
    Por isso as duas variacoes sao filtros separados; a deduplicacao do
    pipeline junta o que se sobrepoe.
  - `size` e ignorado: a pagina e fixa em 10, pedindo 50 ou 100.

**O nivel declarado e aproveitado, e so no filtro `junior`.** Em 150 titulos
amostrados com `seniorities=junior`, 2 traziam marca de nivel alto -- e um
deles era "Analista Full Stack Junior / Pleno", titulo misto que este projeto
aceita de proposito. E o oposto do Quero Vagas Tech, que marca "Gerente de
Infraestrutura" como estagio e por isso tem o campo ignorado.

Nas buscas por `title=` o campo fica vazio e quem decide e o regex sobre o
titulo. Isso nao perde nada -- em 50 titulos de `title=estagiario` o regex
aceitou os 50 -- e protege do casamento frouxo do parametro.

`redirectLink` NAO serve como link: aponta para subdominios `*.solides.jobs`
que o portal desativou (5 de 5 amostrados deram falha de conexao). O link vai
para a pagina canonica do portal, `/vaga/{id}/{slug-do-titulo}`, medida em 200.

A listagem vem ordenada por data decrescente, e a coleta para quando a pagina
inteira ja passou de `dias_max`. Sem isso seriam 111 paginas no filtro mais
longo; com `dias_max=60` sao cerca de 48. A ordenacao foi conferida pagina a
pagina, e a cauda justifica o filtro de idade do projeto: a pagina 111 traz
vagas de 2022.
"""

from __future__ import annotations

import logging
import re

from ..datas import dias_desde
from ..locais import Local
from ..models import Job, normalize, normalize_workplace
from .base import JobSource

logger = logging.getLogger(__name__)

PORTAL_URL = "https://vagas.solides.com.br"
API_URL = "https://apigw.solides.com.br/jobs/v3/portal-vacancies"

# A pagina e fixa em 10: o parametro `size` e ignorado.
PAGE_SIZE = 10
# Teto de seguranca, usado quando o filtro de idade esta desligado
# (`--dias 0`). Hoje o filtro mais longo, `junior`, tem 111 paginas.
MAX_PAGINAS = 150

AREA_TECH = "tecnologia"

# Os filtros nativos que substituem os termos de busca do projeto. A chave e
# so um rotulo, para log e para `job.search_term`.
FILTROS: dict[str, dict[str, str]] = {
    "junior": {"seniorities": "junior"},
    # `seniorities` nao entende estes quatro; ver o docstring do modulo.
    "estagio": {"title": "estagio"},
    "estagiario": {"title": "estagiario"},
    "trainee": {"title": "trainee"},
    "aprendiz": {"title": "aprendiz"},
}

# So o filtro nativo de senioridade prova o nivel. Nos demais o titulo decide.
FILTRO_COM_NIVEL_CONFIAVEL = "junior"


def url_publica(identificador: str, titulo: str) -> str:
    """Pagina canonica da vaga no portal.

    `redirectLink` aponta para `{empresa}.solides.jobs`, subdominio que a
    Solides desativou -- vaga com esse link no card do Discord nao abre.
    """
    slug = re.sub(r"\s+", "-", normalize(titulo)).strip("-")
    if not identificador or not slug:
        return ""
    return f"{PORTAL_URL}/vaga/{identificador}/{slug}"


class SolidesSource(JobSource):
    name = "solides"
    label = "Solides (vagas.solides.com.br)"

    def fetch(self, terms: list[str]) -> list[Job]:
        """Troca os termos do projeto pelos filtros nativos do portal."""
        if terms:
            logger.debug("[%s] termos ignorados; usando os filtros nativos %s",
                         self.name, list(FILTROS))
        return super().fetch(list(FILTROS))

    def fetch_term(self, filtro: str) -> list[Job]:
        """Coleta um dos filtros nativos (`filtro` e chave de FILTROS)."""
        return self._paginar(FILTROS[filtro], filtro=filtro)

    def fetch_local(self, local: Local, terms: list[str]) -> list[Job]:
        """Vagas daquele local, pelo codigo da UF em `locations`.

        `locations` quer a sigla: `RN` devolve 13 vagas, enquanto `Natal` e
        `Rio Grande do Norte` devolvem zero. E filtra de verdade --
        `locations=LocalQueNaoExisteXYZ` devolve zero, que e a prova que este
        projeto exige antes de usar a consulta por local de um portal.

        Para Fortaleza a consulta e mais larga que o pedido (a UF traz o Ceara
        inteiro), mas isso ja esta tratado: o local tem `consulta_e_prova=False`
        e so o texto da vaga vale.
        """
        if not local.solides_uf:
            return []
        jobs: list[Job] = []
        for filtro, params in FILTROS.items():
            jobs.extend(self._paginar(
                {**params, "locations": local.solides_uf},
                filtro=filtro, local_slug=local.slug))
        return jobs

    def _paginar(self, params: dict, filtro: str,
                 local_slug: str = "") -> list[Job]:
        jobs: list[Job] = []
        vistos: set[str] = set()

        for pagina in range(1, MAX_PAGINAS + 1):
            payload = self.session.get_json(API_URL, params={
                "occupationAreas": AREA_TECH, **params, "page": pagina,
            })
            if not payload:
                break

            itens = ((payload.get("data") or {}).get("data")) or []
            if not itens:
                break  # pagina alem do fim: 200 com a lista vazia

            novas = 0
            for bruto in itens:
                job = self._parse(bruto, filtro, local_slug)
                if job is None or job.external_id in vistos:
                    continue
                vistos.add(job.external_id)
                jobs.append(job)
                novas += 1

            if novas == 0:
                break  # a API comecou a repetir; nao adianta seguir
            if self._pagina_velha(itens):
                break
            if len(itens) < PAGE_SIZE:
                break

        return jobs

    def _pagina_velha(self, itens: list[dict]) -> bool:
        """A pagina inteira ja passou do corte de idade?

        A listagem vem da mais nova para a mais velha, entao a ultima vaga da
        pagina e a mais velha dela: se nem essa serve, as proximas tambem nao.
        Vaga sem data NAO autoriza parar -- o projeto trata data ausente como
        "nao da para provar que e velha", e parar ali esconderia as seguintes.

        Usa a mesma `dias_desde` do filtro de idade do pipeline, nao uma copia:
        isto e economia de requisicao, nunca regra propria.
        """
        if self.settings.dias_max <= 0:
            return False
        idades = [dias_desde((i.get("createdAt") or "")[:10]) for i in itens]
        return all(idade is not None and idade > self.settings.dias_max
                   for idade in idades)

    def _parse(self, bruto: dict, filtro: str, local_slug: str) -> Job | None:
        identificador = bruto.get("id")
        titulo = (bruto.get("title") or "").strip()
        if identificador is None or not titulo:
            return None

        cidade = ((bruto.get("city") or {}).get("name") or "").strip()
        uf = ((bruto.get("state") or {}).get("code") or "").strip()
        local = ", ".join(parte for parte in (cidade, uf) if parte)

        # `jobType` e quem carrega a modalidade: a vaga marcada "remoto" veio
        # com `homeOffice` False, entao os dois campos sao consultados.
        modalidade = "remoto" if bruto.get("homeOffice") else bruto.get("jobType")

        return Job(
            source=self.name,
            external_id=str(identificador),
            title=titulo,
            company=bruto.get("companyName") or "",
            url=url_publica(str(identificador), titulo),
            description=bruto.get("description") or "",
            location=local,
            workplace_type=normalize_workplace(modalidade),
            published_date=(bruto.get("createdAt") or "")[:10],
            search_term=filtro,
            local_consultado=local_slug,
            # So o filtro nativo de senioridade prova o nivel; ver o docstring.
            seniority="Júnior" if filtro == FILTRO_COM_NIVEL_CONFIAVEL else "",
        )
