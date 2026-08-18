"""Locais onde vaga presencial serve, alem das remotas de qualquer lugar.

Cada portal quer a localizacao num formato proprio, e todos foram medidos
contra a API de verdade antes de virar codigo:

  - **Gupy**: `state` com o nome do estado por extenso. `state=RN` devolve
    zero; `state=Rio Grande do Norte` devolve as 403 vagas do estado.
  - **LinkedIn**: `geoId` numerico, obtido do typeahead do proprio portal.
    O nome do local em portugues nao filtra nada (ver o coletor).
  - **Vagas.com**: caminho de URL por cidade -- `/vagas-em-natal-rn`.
    Combinar termo e cidade (`/vagas-de-ti-em-natal-rn`) devolve pagina vazia.
  - **Trampos**: `lc`, texto livre. A listagem nao traz a cidade da vaga, entao
    aqui a confianca e na consulta, nao na resposta (ver `local_consultado`).
  - **We Work Remotely**: fica de fora. O feed e de vagas remotas globais --
    nao ha vaga presencial em Natal num feed de "remote jobs".

O reconhecimento no texto e deliberadamente estreito: sigla do estado, nome do
estado e as duas cidades que nao existem em outro estado brasileiro. Cidade
homonima ficou de fora de proposito -- "Santa Cruz" existe em varios estados e
"Parnamirim" tambem e municipio de Pernambuco, entao aceitar por esses nomes
traria vaga de outro canto do pais. As demais cidades do RN entram assim mesmo,
porque os portais escrevem o estado junto ("Mossoro, Rio Grande do Norte",
"Parnamirim / RN").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Job, normalize


@dataclass(frozen=True)
class Local:
    """Um lugar onde vaga presencial serve, e como pedi-lo a cada portal."""

    slug: str
    nome: str
    uf: str
    # Como o local aparece no texto que o portal devolve.
    reconhecer: tuple[str, ...]
    # Como pedir esse local a cada portal. Vazio = o portal nao entra.
    gupy_state: str = ""
    linkedin_geo_id: str = ""
    vagas_cidades: tuple[str, ...] = ()
    trampos_lc: str = ""

    def reconhece(self, texto: str) -> bool:
        """O texto de localizacao do portal aponta para este local?"""
        alvo = normalize(texto)
        if not alvo:
            return False
        return any(re.search(rf"\b{re.escape(termo)}\b", alvo)
                   for termo in self.reconhecer)


RIO_GRANDE_DO_NORTE = Local(
    slug="rn",
    nome="Rio Grande do Norte",
    uf="RN",
    reconhecer=("rn", "rio grande do norte", "natal", "mossoro"),
    gupy_state="Rio Grande do Norte",
    linkedin_geo_id="104863467",
    vagas_cidades=("natal-rn", "mossoro-rn"),
    trampos_lc="Rio Grande do Norte",
)

LOCAIS: dict[str, Local] = {RIO_GRANDE_DO_NORTE.slug: RIO_GRANDE_DO_NORTE}


def resolver(slugs: list[str]) -> list[Local]:
    """Converte os slugs da configuracao nos locais correspondentes."""
    return [LOCAIS[s] for s in slugs if s in LOCAIS]


def serve_presencialmente(job: Job, locais: list[Local]) -> bool:
    """A vaga e num lugar aonde da para ir, seja qual for a modalidade.

    Duas provas valem: o portal escreveu o local na vaga, ou a vaga veio de
    uma consulta feita ao portal por aquele local (`local_consultado`). A
    segunda existe porque o Trampos nao publica a cidade na listagem -- sem
    ela, tudo que veio da consulta por RN seria descartado logo em seguida.
    """
    for local in locais:
        if job.local_consultado == local.slug or local.reconhece(job.location):
            return True
    return False
