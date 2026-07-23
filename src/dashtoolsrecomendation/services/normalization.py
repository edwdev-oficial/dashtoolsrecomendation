from __future__ import annotations

import pandas as pd



KEY_COLUMN = "Descrição"
TLM_COLUMNS = ["Tipo", "Linha", "Modelo"]


def carregar_normalizacao() -> pd.DataFrame:
    # Importação tardia evita abrir dependências do Streamlit/Mongo em testes puros.
    from dashtoolsrecomendation.database.database import get_collection_normal_itens

    collection = get_collection_normal_itens()
    return pd.DataFrame(collection.find().to_list()).drop(columns=["_id"], errors="ignore")


def normalizar(
    df: pd.DataFrame,
    *,
    somente_tlm: bool = False,
) -> pd.DataFrame:
    source = df.drop(columns=TLM_COLUMNS, errors="ignore")
    mapping = carregar_normalizacao()

    selected_columns = [KEY_COLUMN, *TLM_COLUMNS] if somente_tlm else list(mapping.columns)
    missing = [column for column in selected_columns if column not in mapping.columns]
    if missing:
        raise KeyError(
            "Colunas ausentes na coleção de normalização: " + ", ".join(missing)
        )

    return pd.merge(
        source,
        mapping[selected_columns],
        on=KEY_COLUMN,
        how="left",
    )


def itens_nao_normalizados(df: pd.DataFrame) -> pd.DataFrame:
    missing = df[TLM_COLUMNS].isna().any(axis=1) | df[TLM_COLUMNS].eq("").any(axis=1)
    return df.loc[missing]
