"""Coletor do Mentora Dados (mentoradados.com), portal so de vagas de dados.

Site em WordPress. A listagem chega pelo admin-ajax, que o robots.txt libera
explicitamente (`Allow: /wp-admin/admin-ajax.php`):

    POST /wp-admin/admin-ajax.php
         action=mentora_get_vagas  paged=<n>  level[]=Junior  level[]=Estagio

Sem login e sem nonce. O filtro de nivel funciona no servidor: Junior + Estagio
sao ~600 vagas em 12 paginas de 50, em vez de 3.300 em 66. O mesmo endpoint
tem outras acoes -- `mentora_votar_vaga`, `mentora_track_action` -- que ALTERAM
dados do site; este coletor so chama a de leitura.

**O paywall e respeitado.** Parte das vagas e travada para assinante, e o
servidor esconde de verdade: a travada chega sem `conteudo` e sem link de
candidatura, so com a vitrine. Ela e descartada aqui. As de acesso antecipado
(`vip_motivo="hoje"`) abrem para todos a meia-noite e entram numa execucao
seguinte -- descartar em vez de guardar e o que permite isso, porque vaga
descartada nao vai para o estado de "ja avisada".

**A descricao nao vai para o Discord.** Os termos do site proibem reproduzir o
conteudo produzido por eles, e as descricoes vem reescritas no formato do
portal. Ela serve so para classificar a vaga (`reproduzir_descricao=False`);
o card leva titulo, empresa, local, modelo, data, as skills que o portal lista
e o link.

**O nivel declarado e aproveitado**, ao contrario do Quero Vagas Tech. Medido
em 599 vagas livres marcadas Junior/Estagio: nenhuma tinha cargo de nivel alto
no titulo, e as 11 sem marca de nivel eram "Analista de Dados I", bolsas e
residencias.

Particularidades medidas, todas tratadas abaixo:
  - a data vem como "16/09", sem ano (ver `normalizar_data`);
  - o local e quase sempre so o estado ("Ceara (CE)"), entao esta fonte nao
    prova vaga em Fortaleza -- a capital exige a cidade escrita;
  - algumas vagas listam os 27 estados numa string so, que casaria com o RN;
  - seis links de candidatura vieram como "#".
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit

from ..datas import normalizar_data
from ..models import HIBRIDO, NAO_INFORMADO, PRESENCIAL, REMOTO, Job
from .base import JobSource

logger = logging.getLogger(__name__)

API_URL = "https://mentoradados.com/wp-admin/admin-ajax.php"

# Rotulos do filtro do portal, que por acaso sao os mesmos do seniority.yml.
NIVEIS = ("Júnior", "Estágio")

# Teto de seguranca. Hoje Junior + Estagio cabem em 12 paginas.
MAX_PAGINAS = 30

MODALIDADES = {"Remoto": REMOTO, "Híbrido": HIBRIDO, "Presencial": PRESENCIAL}

VARIOS_ESTADOS = "Vários estados"
_UF_RE = re.compile(r"\([A-Z]{2}\)")


class MentoraDadosSource(JobSource):
    name = "mentoradados"
    label = "Mentora Dados"

    def fetch(self, terms: list[str]) -> list[Job]:
        """Ignora os termos: o filtro que importa aqui e o de nivel, no servidor."""
        jobs: list[Job] = []
        travadas = 0

        for pagina in range(1, MAX_PAGINAS + 1):
            payload = self.session.post_json(API_URL, data={
                "action": "mentora_get_vagas",
                "paged": pagina,
                "search": "",
                "level[]": list(NIVEIS),
            })
            if not payload or not payload.get("success"):
                break

            dados = payload.get("data") or {}
            vagas = dados.get("vagas") or []
            if not vagas:
                break

            for bruta in vagas:
                if bruta.get("bloqueada"):
                    travadas += 1
                    continue
                job = self._parse(bruta)
                if job is not None:
                    jobs.append(job)

            total = dados.get("total_paginas")
            if isinstance(total, int) and pagina >= total:
                break

        logger.info("[%s] %d vagas livres; %d travadas no paywall, ignoradas",
                    self.name, len(jobs), travadas)
        self.stats.raw_jobs = len(jobs)
        self.stats.requests_made = self.session.request_count
        return jobs

    def fetch_term(self, term: str) -> list[Job]:
        """Nao usado: a coleta filtra por nivel no servidor, nao por termo."""
        return []

    def _parse(self, bruta: dict) -> Job | None:
        identificador = bruta.get("id")
        titulo = (bruta.get("titulo") or "").strip()
        if not identificador or not titulo:
            return None

        return Job(
            source=self.name,
            external_id=str(identificador),
            title=titulo,
            company=bruta.get("empresa") or "",
            url=self._link(bruta),
            description=bruta.get("conteudo") or "",
            location=self._local(bruta.get("cidade") or ""),
            workplace_type=MODALIDADES.get(bruta.get("modelo"), NAO_INFORMADO),
            published_date=normalizar_data(bruta.get("data") or ""),
            seniority=self._nivel(bruta.get("nivel")),
            skills=[s.strip() for s in (bruta.get("skills") or [])
                    if isinstance(s, str) and s.strip()],
            reproduzir_descricao=False,
        )

    @staticmethod
    def _nivel(niveis) -> str:
        """Primeiro nivel de entrada que o portal declarou; vazio cai no titulo."""
        for nivel in niveis or []:
            if nivel in NIVEIS:
                return nivel
        return ""

    @staticmethod
    def _local(cidade: str) -> str:
        """Lista de estados nao prova local nenhum.

        Algumas vagas trazem os 27 estados numa string so ("Acre (AC), Alagoas
        (AL), ..., Rio Grande do Norte (RN), ..."). Mantida como veio, ela
        casaria com o reconhecedor do RN e a vaga entraria como "do RN".
        """
        if len(_UF_RE.findall(cidade)) > 1:
            return VARIOS_ESTADOS
        return cidade.strip()

    @staticmethod
    def _link(bruta: dict) -> str:
        """Link de candidatura, ou a pagina da vaga no portal quando ele nao serve.

        Dois casos medidos em que nao serve: "#", e e-mail de candidatura que o
        portal transforma em URL colando `http://` na frente
        ("http://dados@c1porcento.com"). O segundo tem esquema http, mas o `@`
        vira credencial no endereco e o Discord recusa o link -- o card chegaria
        sem ele. A pagina da vaga no portal mostra o e-mail.
        """
        candidatura = (bruta.get("link_aplicacao") or "").strip()
        partes = urlsplit(candidatura)
        if (partes.scheme in ("http", "https") and partes.netloc
                and "@" not in partes.netloc):
            return candidatura
        return bruta.get("permalink") or ""
