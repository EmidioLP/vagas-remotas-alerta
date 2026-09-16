"""Locais onde vaga presencial serve, alem das remotas de qualquer lugar.

Um local pode ser um estado inteiro (o RN) ou uma cidade so (Fortaleza). Cada
portal quer a localizacao num formato proprio, e todos foram medidos contra a
API de verdade antes de virar codigo:

  - **Gupy**: `state` com o nome do estado por extenso (`state=RN` devolve
    zero) ou `city` para uma cidade -- `city=Fortaleza` trouxe 100 de 100 em
    Fortaleza, Ceara, enquanto `state=Ceara` traria Caucaia e Juazeiro junto.
  - **LinkedIn**: `geoId` numerico, obtido do typeahead do proprio portal.
    O nome do local em portugues nao filtra nada (ver o coletor).
  - **Vagas.com**: caminho de URL por cidade, SEMPRE com a UF --
    `/vagas-em-fortaleza-ce` trouxe 11 de 11 em Fortaleza; sem o `-ce`, vieram
    Sao Paulo, Recife e "Brasil" misturados. Combinar termo e cidade
    (`/vagas-de-ti-em-natal-rn`) devolve pagina vazia.
  - **Trampos**: fica de fora, e isto corrige um erro. O parametro `lc` MUDA o
    resultado mas nao filtra pelo local pedido: `lc=Natal`, `lc=Fortaleza` e
    `lc=CidadeQueNaoExisteXYZ` devolvem exatamente a mesma vaga. Ele chegou a
    ser usado para o RN porque "7 vagas viram 2" parecia filtro -- e como a
    listagem nao traz cidade, a vaga era aceita so por ter vindo da consulta.
  - **We Work Remotely**: fica de fora. O feed e de vagas remotas globais.

Regra para qualquer local novo: so usar a consulta de um portal depois de
provar que um local inventado devolve nada. Vaga vinda de consulta por local e
aceita pela consulta (ver `serve_presencialmente`), entao um filtro frouxo no
portal vira vaga de outro canto do pais no Discord.

O reconhecimento no texto e deliberadamente estreito. No RN: sigla, nome do
estado e as duas cidades que nao existem em outro estado -- "Parnamirim" tambem
e municipio de Pernambuco, e "Santa Cruz" existe em varios. Em Fortaleza o
nome sozinho nao basta: ha Fortaleza dos Valos (RS), Fortaleza de Minas (MG),
Fortaleza dos Nogueiras (MA) e Cruzeiro da Fortaleza (MG). Entao so conta
"Fortaleza" com o Ceara junto, que e como todos os portais medidos escrevem
("Fortaleza, Ceara", "Fortaleza / CE") -- mais "Greater Fortaleza", do LinkedIn.
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
    gupy_city: str = ""
    linkedin_geo_id: str = ""
    vagas_cidades: tuple[str, ...] = ()

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
)

FORTALEZA = Local(
    slug="fortaleza",
    nome="Fortaleza",
    uf="CE",
    # "fortaleza" sozinho casaria Fortaleza dos Valos (RS) e afins.
    reconhecer=("fortaleza ce", "fortaleza ceara", "greater fortaleza"),
    gupy_city="Fortaleza",
    linkedin_geo_id="103836099",
    vagas_cidades=("fortaleza-ce",),
)

LOCAIS: dict[str, Local] = {
    RIO_GRANDE_DO_NORTE.slug: RIO_GRANDE_DO_NORTE,
    FORTALEZA.slug: FORTALEZA,
}


def resolver(slugs: list[str]) -> list[Local]:
    """Converte os slugs da configuracao nos locais correspondentes."""
    return [LOCAIS[s] for s in slugs if s in LOCAIS]


def serve_presencialmente(job: Job, locais: list[Local]) -> bool:
    """A vaga e num lugar aonde da para ir, seja qual for a modalidade.

    Duas provas valem: o portal escreveu o local na vaga, ou a vaga veio de
    uma consulta feita ao portal por aquele local (`local_consultado`).

    A segunda so e prova porque cada consulta por local foi medida precisa --
    e e exatamente por isso que o Trampos saiu delas: o `lc` dele nao filtra,
    e a vaga passava por aqui sem estar no local.
    """
    for local in locais:
        if job.local_consultado == local.slug or local.reconhece(job.location):
            return True
    return False
