from __future__ import annotations

import pandas as pd


AMS_GROUP_KEYS = [
    # "Id",
    "Material",
    "Número de Série",
    "Data de compra",
    # "ano_reparo"
]


def converter_datas(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        # result[column] = pd.to_datetime(result[column], errors="coerce")
        result[column] = pd.to_datetime(
            result[column],
            format="mixed",
            dayfirst=True,
            errors="coerce",
        )
    return result


def converter_numeros(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        result[column] = pd.to_numeric(
            result[column].replace("-", 0), errors="coerce"
        ).fillna(0)
    return result


def mover_coluna(
    df: pd.DataFrame,
    column: str,
    position: int = 0,
) -> pd.DataFrame:
    if column not in df.columns:
        return df
    values = df.pop(column)
    df.insert(position, column, values)
    return df


def preparar_parque(
    frames: list[pd.DataFrame],
    date_columns: list[str],
    output_columns: list[str],
) -> pd.DataFrame:
    df = pd.concat(frames)
    df["Número de série"] = df["Número de série"].astype("string").fillna("")
    defaults = {
        "Data de Início do Contrato": "",
        "Data de Término do Contrato": "",
        "Mensalidade": 0,
    }
    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default

    df = converter_datas(df, date_columns)
    df = converter_numeros(df, ["Mensalidade", "Custo de Reparo"])
    df = df.fillna("").reindex(columns=df.columns.union(output_columns))
    return df[output_columns].fillna("")


def preparar_ams(df: pd.DataFrame) -> pd.DataFrame:
    cliente = df["Cliente"].astype("string")
    result = df[
        cliente.notna()
        & cliente.ne("Total")
        & ~cliente.str.startswith("Filtro", na=False)
    ].copy()
    result["Número de Série"] = (
        pd.to_numeric(result["Número de Série"], errors="coerce")
        .astype("Int64")
        .astype("string")
        .fillna("")
    )
    result["# Notif."] = pd.to_numeric(result["# Notif."], errors="coerce")
    result[["Id", "Razao Social"]] = result["Cliente"].str.split(
        " - ", n=1, expand=True
    )
    result = result.drop(columns=["Cliente"])
    mover_coluna(result, "Razao Social")
    mover_coluna(result, "Id")
    result["Data de compra"] = (
        pd.Timestamp.today().normalize()
        - pd.to_timedelta(result["Idade em Anos"] * 365, unit="D")
    )
    mover_coluna(result, "Data de compra", result.columns.get_loc("Idade em Anos"))

    if "ano_reparo" not in result.columns:
        result["ano_reparo"] = pd.NA

    result = result.sort_values(["ano_reparo"], na_position="last")
    result["Id"] = (
        result
        .groupby("Número de Série")["Id"]
        .transform("last")
    )
    result["_presente_ams"] = True

    return result


def preparar_sap_group(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df[
        ()
    ]]
    return df


def agrupar_ams(df: pd.DataFrame) -> pd.DataFrame:
    result = (
        df.groupby(AMS_GROUP_KEYS, as_index=False)
        .agg(
            {
                "Id": "last",
                "Razao Social": "first",
                "Nome do Material": "first",
                "FM Frota": "last",
                "# Notif.": "sum",
                "# Reparos": "sum",
                "Custo de Reparos": "sum",
                "Pagado pelo Cliente": "sum",
                "Economia": "sum",
            }
        )
    )
    result["_presente_ams"] = True
    return result


def normalizar_numero_serie(serie: pd.Series) -> pd.Series:
    resultado = (
        serie.astype("string")
        .str.strip()
        .str.replace(r"^(\d+)\.0+$", r"\1", regex=True)
    )

    return resultado.replace(
        {
            "": pd.NA,
            "nan": pd.NA,
            "None": pd.NA,
            "<NA>": pd.NA,
        }
    )


def preparacoes_por_ano(
    df_pq: pd.DataFrame,
    df_ams: pd.DataFrame,
    anos: list[int],
) -> pd.DataFrame:
    pq = df_pq.copy()
    ams = df_ams.copy()

    pq["Número de Série"] = normalizar_numero_serie(
        pq["Número de Série"]
    )
    ams["Número de Série"] = normalizar_numero_serie(
        ams["Número de Série"]
    )

    ams["ano_reparo"] = pd.to_numeric(
        ams["ano_reparo"],
        errors="coerce",
    ).astype("Int64")

    ams = ams[ams["ano_reparo"].isin(anos)]

    reparos = (
        ams.dropna(subset=["Número de Série"])
        .groupby("Número de Série", as_index=False)
        .agg(
            Reparos_no_período=("# Reparos", "sum"),
            Custo_no_período=("Custo de Reparos", "sum"),
            Pago_no_período=("Pagado pelo Cliente", "sum"),
            Economia_no_período=("Economia", "sum"),
        )
    )

    resultado = pq.merge(
        reparos,
        on="Número de Série",
        how="left",
        validate="many_to_one",
        indicator="Situação_AMS",
    )

    resultado["Encontrado_no_AMS"] = resultado[
        "Situação_AMS"
    ].eq("both")

    colunas_reparo = [
        "Reparos_no_período",
        "Custo_no_período",
        "Pago_no_período",
        "Economia_no_período",
    ]

    resultado[colunas_reparo] = resultado[colunas_reparo].fillna(0)

    return resultado
