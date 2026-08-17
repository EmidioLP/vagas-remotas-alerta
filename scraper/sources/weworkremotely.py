"""Coletor do We Work Remotely (weworkremotely.com).

Board global de vagas 100% remotas. Publica feeds RSS abertos por categoria:

    GET https://weworkremotely.com/categories/<categoria>.rss

O RSS nao tem busca textual, entao esta fonte nao percorre os termos do
projeto -- ela varre as categorias de tecnologia, do mesmo jeito que o coletor
da ProgramaThor usa os filtros nativos daquele portal.

Duas caracteristicas uteis do feed:

  - **Toda vaga e remota por definicao.** O board so publica remoto, entao a
    modalidade e afirmada sem depender de heuristica.
  - **Ha um campo `<skills>`** com as tecnologias declaradas, que alimenta o
    classificador e o extrator do projeto.

Aviso sobre o volume: o board e dominado por vagas senior. Numa medicao real,
de 306 vagas em seis categorias, **apenas 3 passaram no filtro de nivel de
entrada**. A fonte entra pela cobertura global de remoto, nao pelo volume.
"""

from __future__ import annotations

import logging
import re
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from ..models import REMOTO, Job
from .base import JobSource

logger = logging.getLogger(__name__)

BASE_URL = "https://weworkremotely.com"

# Categorias de tecnologia. Design entra porque concentra as vagas de UX/UI,
# que o classificador do projeto reconhece.
CATEGORIAS = [
    "remote-programming-jobs",
    "remote-back-end-programming-jobs",
    "remote-front-end-programming-jobs",
    "remote-full-stack-programming-jobs",
    "remote-devops-sysadmin-jobs",
    "remote-design-jobs",
]

_SLUG_RE = re.compile(r"/remote-jobs/([^/?#]+)")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class WeWorkRemotelySource(JobSource):
    name = "wwr"
    label = "We Work Remotely"

    def fetch(self, terms: list[str]) -> list[Job]:
        """Ignora os termos: o RSS nao tem busca, so listagem por categoria."""
        if terms:
            logger.debug(
                "[%s] termos ignorados (o feed nao tem busca); varrendo %d categorias",
                self.name, len(CATEGORIAS),
            )
        return super().fetch(list(CATEGORIAS))

    def fetch_term(self, term: str) -> list[Job]:
        """`term` e o slug de uma categoria do board."""
        response = self.session.get(f"{BASE_URL}/categories/{term}.rss")
        if response is None:
            return []
        return self._parse_feed(response.text, term)

    def _parse_feed(self, xml: str, term: str) -> list[Job]:
        try:
            raiz = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            logger.warning("[%s] RSS invalido em %s: %s", self.name, term, exc)
            return []

        jobs: list[Job] = []
        for item in raiz.iter("item"):
            job = self._parse_item(item, term)
            if job is not None:
                jobs.append(job)
        return jobs

    def _parse_item(self, item, term: str) -> Job | None:
        link = self._texto(item.find("link"))
        bruto = self._texto(item.find("title"))
        if not link or not bruto:
            return None

        slug = _SLUG_RE.search(link)
        if slug is None:
            return None

        empresa, titulo = self._empresa_e_titulo(bruto)
        if not titulo:
            return None

        return Job(
            source=self.name,
            external_id=slug.group(1),
            title=titulo,
            company=empresa,
            url=link,
            description=self._descricao(item),
            location=self._texto(item.find("region")),
            # O board so publica vaga remota -- nao ha o que inferir.
            workplace_type=REMOTO,
            published_date=self._data(self._texto(item.find("pubDate"))),
            search_term=term,
        )

    @staticmethod
    def _empresa_e_titulo(bruto: str) -> tuple[str, str]:
        """O RSS usa "Empresa: Cargo" no titulo."""
        if ": " in bruto:
            empresa, _, titulo = bruto.partition(": ")
            return empresa.strip(), titulo.strip()
        return "", bruto.strip()

    @staticmethod
    def _data(bruto: str) -> str:
        """pubDate vem em RFC 822 ("Wed, 22 Jul 2026 07:03:14 +0000")."""
        if not bruto:
            return ""
        try:
            return parsedate_to_datetime(bruto).date().isoformat()
        except (TypeError, ValueError):
            return ""

    def _descricao(self, item) -> str:
        """Junta o que o feed declara com o texto da vaga, sem as tags HTML."""
        partes: list[str] = []
        skills = self._texto(item.find("skills"))
        if skills:
            partes.append(f"Tecnologias: {skills}.")
        categoria = self._texto(item.find("category"))
        if categoria:
            partes.append(f"Categoria: {categoria}.")
        tipo = self._texto(item.find("type"))
        if tipo:
            partes.append(f"Tipo: {tipo}.")

        corpo = self._texto(item.find("description"))
        if corpo:
            partes.append(_WS_RE.sub(" ", _TAG_RE.sub(" ", corpo)).strip())

        return " ".join(p for p in partes if p)

    @staticmethod
    def _texto(no) -> str:
        if no is None or no.text is None:
            return ""
        return _WS_RE.sub(" ", no.text).strip()
