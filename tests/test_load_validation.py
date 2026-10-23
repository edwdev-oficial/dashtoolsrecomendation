import pandas as pd

from dashtoolsrecomendation.services import load_validation


def _parque(account_id: str, name: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Id": [account_id],
            "Razao Social": [name],
            "Número de série": ["100"],
        }
    )


def _ams(year: int, accounts: list[tuple[str, str]]) -> pd.DataFrame:
    customers = ", ".join(
        f"{account_id} - {name}" for account_id, name in accounts[:-1]
    )
    if len(accounts) > 1:
        customers += f" ou {accounts[-1][0]} - {accounts[-1][1]}"
    elif accounts:
        customers = f"{accounts[0][0]} - {accounts[0][1]}"

    return pd.DataFrame(
        {
            "Cliente": [
                f"{accounts[0][0]} - {accounts[0][1]}",
                "Total",
                None,
                f"Filtros aplicados:\nCustomers é {customers}\nA é {year}",
            ],
            "Número de Série": [100, None, None, None],
            "ano_reparo": [year, year, year, year],
        }
    )


def test_normalizar_id_conta_remove_zeros_a_esquerda():
    assert load_validation.normalizar_id_conta("0020618571") == "20618571"
    assert load_validation.normalizar_id_conta(30405191) == "30405191"


def test_extrair_metadados_filtro_ams_le_clientes_e_ano():
    frame = _ams(
        2026,
        [
            ("20618571", "TRIADE AMERICANA COMERCIO DE"),
            ("30405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA"),
        ],
    )

    metadata = load_validation.extrair_metadados_filtro_ams(frame)

    assert metadata["metadata_encontrada"] is True
    assert metadata["ano_filtro"] == 2026
    assert set(metadata["contas"]) == {"20618571", "30405191"}


def test_validar_carga_detecta_conta_do_parque_ausente_no_ams():
    parque = [
        _parque("0020618571", "TRIADE AMERICANA COMERCIO DE"),
        _parque("0030405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA"),
    ]
    ams = _ams(
        2026,
        [("30405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA")],
    )

    result = load_validation.validar_carga(
        parque,
        [("ams_report_2026.xlsx", ams)],
    )

    assert result["bloqueante"] is True
    assert result["status"] == "error"
    assert result["contas_ausentes_ams"] == [
        {"id": "20618571", "nome": "TRIADE AMERICANA COMERCIO DE"}
    ]


def test_validar_carga_detecta_filtros_diferentes_entre_anos():
    parque = [
        _parque("0020618571", "TRIADE AMERICANA COMERCIO DE"),
        _parque("0030405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA"),
    ]
    ams_2025 = _ams(
        2025,
        [
            ("20618571", "TRIADE AMERICANA COMERCIO DE"),
            ("30405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA"),
        ],
    )
    ams_2026 = _ams(
        2026,
        [("30405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA")],
    )

    result = load_validation.validar_carga(
        parque,
        [
            ("ams_report_2025.xlsx", ams_2025),
            ("ams_report_2026.xlsx", ams_2026),
        ],
    )

    assert result["bloqueante"] is True
    assert result["filtros_consistentes"] is False
    assert any("mesma seleção de contas" in message for message in result["errors"])


def test_validar_carga_avisa_conta_extra_sem_bloquear():
    parque = [_parque("0030405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA")]
    ams = _ams(
        2026,
        [
            ("30405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA"),
            ("20618564", "TRIADE PAULINIA ALUGUEL DE"),
        ],
    )

    result = load_validation.validar_carga(
        parque,
        [("ams_report_2026.xlsx", ams)],
    )

    assert result["bloqueante"] is False
    assert result["status"] == "warning"
    assert result["contas_extras_ams"] == [
        {"id": "20618564", "nome": "TRIADE PAULINIA ALUGUEL DE"}
    ]


def test_validar_carga_sem_rodape_de_filtro_e_aviso_nao_bloqueante():
    parque = [_parque("0030405191", "VT4 AGUAS DE LINDOIA ALUGUEL LTDA")]
    ams = pd.DataFrame(
        {
            "Cliente": ["30405191 - VT4 AGUAS DE LINDOIA ALUGUEL LTDA"],
            "Número de Série": [100],
            "ano_reparo": [2026],
        }
    )

    result = load_validation.validar_carga(
        parque,
        [("ams_report_2026.xlsx", ams)],
    )

    assert result["bloqueante"] is False
    assert result["status"] == "warning"
    assert result["arquivos_sem_metadados"] == ["ams_report_2026.xlsx"]
