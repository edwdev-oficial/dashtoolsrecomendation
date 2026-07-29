from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class PdfReportConfig:
    """Configuração visual e comercial do relatório de renovação.

    A configuração não contém DataFrames. Isso permite reutilizar o mesmo
    gerador em Streamlit, tarefas em lote, testes e futuras APIs.
    """

    cliente: str
    responsavel: str
    cargo_responsavel: str
    data_emissao: date
    data_inicio: date
    data_fim: date
    idade_corte: int
    fator_impostos: float
    quantidade_cenario: int
    incluir_base_completa: bool = True
    titulo: str = "Análise técnica e econômica para renovação do parque"
    subtitulo: str = (
        "Evidências de frequência de reparações,<br/>"
        "concentração de custos, exposição operacional e<br/>"
        "priorização das máquinas para substituição."
    )
    confidencial: bool = True
    logo_cliente: bytes | None = None
    logo_hilti_path: Path | None = None
    filtros: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.cliente.strip():
            raise ValueError("Informe o nome do cliente para gerar o relatório.")
        if self.idade_corte < 0:
            raise ValueError("A idade de corte não pode ser negativa.")
        if self.quantidade_cenario < 1:
            raise ValueError("O cenário deve conter ao menos uma máquina.")
        if self.fator_impostos <= 0:
            raise ValueError("O fator de impostos deve ser maior que zero.")
        if self.data_inicio > self.data_fim:
            raise ValueError("A data inicial não pode ser posterior à data final.")
