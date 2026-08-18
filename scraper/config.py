"""Configuracao central do projeto.

Tudo que voce provavelmente vai querer ajustar (termos de busca, delays, caminhos)
esta neste arquivo ou nos YAMLs em `scraper/rules/`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = Path(__file__).resolve().parent / "rules"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

USER_AGENT = (
    "vagas-remotas-alerta/1.0 (busca pessoal de vagas) python-requests"
)

# Termos usados na busca. Cada termo vira uma consulta separada em cada portal.
SEARCH_TERMS: list[str] = [
    "desenvolvedor junior",
    "desenvolvedor jr",
    "programador junior",
    "analista de sistemas junior",
    "estagio desenvolvimento",
    "estagio ti",
    "estagio tecnologia",
    "trainee tecnologia",
    "engenheiro de dados junior",
    "analista de dados junior",
    "qa junior",
    "devops junior",
    "suporte tecnico junior",
]


@dataclass
class Settings:
    """Parametros de execucao. Sobrescritos pela CLI em `main.py`."""

    search_terms: list[str] = field(default_factory=lambda: list(SEARCH_TERMS))
    # A ProgramaThor ficou de fora: responde 403 a partir de IP de datacenter,
    # e este projeto roda no GitHub Actions.
    sources: list[str] = field(
        default_factory=lambda: ["gupy", "vagas", "trampos", "linkedin", "wwr"]
    )
    output_dir: Path = DEFAULT_OUTPUT_DIR

    # Educacao com o servidor
    delay_seconds: float = 1.5
    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 1.5
    user_agent: str = USER_AGENT

    # Limites de coleta
    page_size: int = 100  # a API da Gupy rejeita limit > 100 (HTTP 400)
    max_pages_per_term: int = 5

    # Filtros
    only_junior: bool = True
    # Mantem so as vagas que o portal AFIRMA ser remotas. Vagas sem modalidade
    # informada sao descartadas: "nao informado" nao e prova de remoto.
    somente_remotas: bool = True
    # Portal nao tira anuncio velho do ar: a coleta trouxe vaga de 2022.
    # 0 desliga o filtro.
    dias_max: int = 60

    def ensure_output_dir(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir
