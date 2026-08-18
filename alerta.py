"""Coleta vagas júnior remotas e avisa no Discord só as que ainda não mostrou.

    python alerta.py --dry-run     # mostra o que enviaria, sem enviar
    python alerta.py               # envia (precisa de DISCORD_WEBHOOK_URL)

O webhook vem da variável de ambiente `DISCORD_WEBHOOK_URL` e nunca é escrito
em arquivo do repositório. No GitHub Actions vem de um secret.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from scraper.config import PROJECT_ROOT, SEARCH_TERMS, Settings
from scraper.notificacao import (
    carregar_vistas,
    enviar,
    montar_mensagens,
    salvar_vistas,
    separar_novas,
)
from scraper.pipeline import coletar_vagas
from scraper.sources import AVAILABLE_SOURCES

ESTADO_PADRAO = PROJECT_ROOT / "state" / "vagas_vistas.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alerta",
        description="Avisa no Discord as vagas júnior remotas ainda não mostradas.",
    )
    parser.add_argument("--sources", nargs="+", default=list(AVAILABLE_SOURCES),
                        choices=AVAILABLE_SOURCES,
                        help="Portais a consultar (padrão: todos).")
    parser.add_argument("--terms", nargs="+", default=None,
                        help=f"Termos de busca (padrão: {len(SEARCH_TERMS)} termos).")
    parser.add_argument("--max-pages", type=int, default=5,
                        help="Máximo de páginas por termo, por portal.")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Segundos entre requisições (padrão: 2).")
    parser.add_argument("--estado", type=Path, default=ESTADO_PADRAO,
                        help=f"Arquivo de estado (padrão: {ESTADO_PADRAO}).")
    parser.add_argument("--titulo", default="Novas vagas júnior remotas",
                        help="Título do aviso no Discord.")
    parser.add_argument("--dias", type=int, default=60,
                        help="Idade máxima da vaga em dias (0 desliga).")
    parser.add_argument("--todas-modalidades", action="store_true",
                        help="Não filtrar por remoto (padrão é só remotas).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra o que seria enviado, sem enviar nem gravar.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    settings = Settings(
        search_terms=args.terms or list(SEARCH_TERMS),
        sources=args.sources,
        delay_seconds=args.delay,
        max_pages_per_term=args.max_pages,
        somente_remotas=not args.todas_modalidades,
        dias_max=args.dias,
    )

    jobs = coletar_vagas(settings)
    vistas = carregar_vistas(args.estado)
    novas = separar_novas(jobs, vistas)

    print()
    print(f"  Vagas encontradas .. {len(jobs)}")
    print(f"  Já avisadas ........ {len(vistas)}")
    print(f"  Novas .............. {len(novas)}")

    if not novas:
        print("\n  Nada novo desde a última execução; nenhum aviso enviado.")
        return 0

    for job in novas[:15]:
        print(f"    • [{job.source}] {job.title[:56]} — {job.company[:24]}")
    if len(novas) > 15:
        print(f"    ... e mais {len(novas) - 15}")

    if args.dry_run:
        print("\n  --dry-run: nada enviado, estado não gravado.")
        return 0

    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        # Sem webhook o estado NAO e gravado: marcar como avisada uma vaga que
        # ninguem viu faria ela sumir para sempre.
        print(
            "\n  DISCORD_WEBHOOK_URL não definida — nada enviado e estado "
            "preservado. Defina a variável (ou use --dry-run)."
        )
        return 1

    mensagens = montar_mensagens(novas, args.titulo)
    enviadas = enviar(webhook, mensagens)
    if enviadas < len(mensagens):
        print(f"\n  Falha ao enviar ({enviadas}/{len(mensagens)}); estado preservado.")
        return 1

    salvar_vistas(args.estado, vistas | {job.source_key for job in novas})
    print(f"\n  {enviadas} mensagem(ns) enviada(s); estado atualizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
