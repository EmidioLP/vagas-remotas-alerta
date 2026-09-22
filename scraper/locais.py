"""Locais onde vaga presencial serve, alem das remotas de qualquer lugar.

Um local pode ser um estado inteiro (o RN) ou uma cidade so (Fortaleza). Cada
portal quer a localizacao num formato proprio, e todos foram medidos contra a
API de verdade antes de virar codigo:

  - **Gupy**: `state` com o nome do estado por extenso (`state=RN` devolve
    zero) ou `city` para uma cidade -- `city=Fortaleza` trouxe 100 de 100 em
    Fortaleza, Ceara, enquanto `state=Ceara` traria Caucaia e Juazeiro junto.
  - **LinkedIn**: `geoId` numerico, obtido do typeahead do proprio portal.
    O nome do local em portugues nao filtra nada (ver o coletor). Atencao: o
    geoId de uma cidade cobre a regiao metropolitana -- o de Fortaleza trouxe
    vagas de Maracanau e Eusebio.
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
  - **Solides**: `locations` com a SIGLA da UF -- `RN` devolve 13 vagas,
    enquanto `Natal` e `Rio Grande do Norte` devolvem zero. Filtra de verdade
    (`locations=LocalQueNaoExisteXYZ` devolve zero), mas so sabe pedir o
    estado: para uma cidade, vem a UF inteira.
  - **InfoJobs**: caminho de URL por cidade, SEMPRE com a UF e com a virgula
    literal -- `/empregos-em-natal,-rn.aspx` devolve 2.130 vagas de Natal,
    enquanto `/empregos-em-natal.aspx` responde 200 e **redireciona para Sao
    Paulo**, igual a `/empregos-em-cidadequenaoexistexyz,-rn.aspx`. Cidade que
    ele nao reconhece nao da erro, da outro estado. E a consulta ainda e
    frouxa: nos 13 termos, `natal,-rn` trouxe 88 cards dos quais 83 nao eram
    de Natal. Por isso o coletor confere o desvio e, mesmo assim, nao passa
    `local_consultado` -- quem prova o local ali e o texto do card.
  - **Recrutei**: caminho `/vagas/em/<lugar>`, que aceita tanto a UF (`rn`,
    12 vagas, todas de Natal) quanto a cidade com a UF junto (`fortaleza-ce`,
    43 vagas). Filtra de verdade -- lugar inventado responde 404 --, mas a
    cidade traz a regiao metropolitana: dos 43 cards de Fortaleza, 12 eram de
    Eusebio e Maracanau. Dai `local_consultado` tambem ficar vazio ali.

Regra para qualquer local novo: so usar a consulta de um portal depois de
provar que um local inventado devolve nada. Vaga vinda de consulta por local
pode ser aceita pela consulta (ver `serve_presencialmente`), entao um filtro
frouxo no portal vira vaga de outro canto do pais no Discord.

Quando a consulta e mais larga que o local -- uma cidade pedida, a regiao
metropolitana devolvida --, o local desliga essa confianca
(`consulta_e_prova=False`) e so vale o texto. E o caso de Fortaleza, onde o
pedido foi so a capital.

O reconhecimento no texto e deliberadamente estreito. No RN: sigla, nome do
estado e as duas cidades que nao existem em outro estado -- "Parnamirim" tambem
e municipio de Pernambuco, e "Santa Cruz" existe em varios. Em Fortaleza o
nome sozinho nao basta: ha Fortaleza dos Valos (RS), Fortaleza de Minas (MG),
Fortaleza dos Nogueiras (MA) e Cruzeiro da Fortaleza (MG). Entao so conta
"Fortaleza" com o Ceara junto, que e como todos os portais medidos escrevem
("Fortaleza, Ceara", "Fortaleza / CE"). "Greater Fortaleza", do LinkedIn, NAO
conta: e o rotulo da regiao metropolitana, e nao prova que a vaga e na capital.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import REMOTO, Job, normalize


@dataclass(frozen=True)
class Local:
    """Um lugar onde vaga presencial serve, e como pedi-lo a cada portal."""

    slug: str
    nome: str
    uf: str
    # Como o local aparece no texto que o portal devolve.
    reconhecer: tuple[str, ...]
    # Vaga vinda de consulta por este local vale so por ter vindo dela? Falso
    # quando algum portal devolve mais que o local -- ai o texto tem que provar.
    consulta_e_prova: bool = True
    # Como pedir esse local a cada portal. Vazio = o portal nao entra.
    gupy_state: str = ""
    gupy_city: str = ""
    linkedin_geo_id: str = ""
    vagas_cidades: tuple[str, ...] = ()
    # A Solides quer a SIGLA da UF ("RN"); nome de cidade ou de estado por
    # extenso devolve zero. Como e por UF, uma cidade traz o estado inteiro.
    solides_uf: str = ""
    # O InfoJobs so honra a cidade com a UF junto e com a virgula:
    # `/empregos-em-natal.aspx` devolve Sao Paulo, `natal,-rn` devolve Natal.
    infojobs_cidades: tuple[str, ...] = ()
    # Caminho de `/vagas/em/...` no Recrutei: a UF sozinha no RN, que cobre
    # Natal e Mossoro de uma vez, e a cidade com a UF em Fortaleza. Lugar
    # inventado responde 404.
    recrutei_caminhos: tuple[str, ...] = ()

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
    solides_uf="RN",
    infojobs_cidades=("natal,-rn", "mossoro,-rn"),
    # A UF sozinha ja traz as duas cidades; `/vagas/em/natal-rn` seria um
    # subconjunto dela.
    recrutei_caminhos=("rn",),
)

FORTALEZA = Local(
    slug="fortaleza",
    nome="Fortaleza",
    uf="CE",
    # "fortaleza" sozinho casaria Fortaleza dos Valos (RS) e afins, e
    # "Greater Fortaleza" e a regiao metropolitana inteira.
    reconhecer=("fortaleza ce", "fortaleza ceara"),
    # O geoId do LinkedIn devolve Maracanau e Eusebio; o pedido e so a capital.
    consulta_e_prova=False,
    gupy_city="Fortaleza",
    linkedin_geo_id="103836099",
    vagas_cidades=("fortaleza-ce",),
    # A UF traz o Ceara inteiro, mais largo que a capital -- e por isso que
    # `consulta_e_prova=False` acima vale tambem para esta consulta.
    solides_uf="CE",
    infojobs_cidades=("fortaleza,-ce",),
    # 43 cards, dos quais 12 sao de Eusebio e Maracanau -- de novo a regiao
    # metropolitana, de novo so o texto vale.
    recrutei_caminhos=("fortaleza-ce",),
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
        if local.reconhece(job.location):
            return True
        if local.consulta_e_prova and job.local_consultado == local.slug:
            return True
    return False


def serve(job: Job, locais: list[Local]) -> bool:
    """Remota de qualquer lugar, ou presencial/hibrida onde da para ir.

    E o filtro de remotas do pipeline; os pre-filtros das fontes chamam esta
    mesma funcao para nao divergir dele.
    """
    return job.workplace_type == REMOTO or serve_presencialmente(job, locais)
