from __future__ import annotations

import pandas as pd


AMS_GROUP_KEYS = [
    "Número de Série",
    "Modelo",
]

AMS_ORIGIN_ID_COLUMN = "Id origem AMS"
AMS_ORIGIN_NAME_COLUMN = "Razao Social origem AMS"


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


def _ams_asset_keys(df: pd.DataFrame) -> list[str]:
    keys = ["Número de Série"]
    if "Modelo" in df.columns:
        keys.append("Modelo")
    elif "Nome do Material" in df.columns:
        keys.append("Nome do Material")
    return keys


def _unique_non_empty(values: pd.Series) -> list[str]:
    result: list[str] = []
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def detectar_series_multiconta(df: pd.DataFrame) -> pd.DataFrame:
    """Return serial/model combinations linked to multiple AMS origin accounts."""
    if df.empty or "Número de Série" not in df.columns:
        return pd.DataFrame()

    id_column = (
        AMS_ORIGIN_ID_COLUMN
        if AMS_ORIGIN_ID_COLUMN in df.columns
        else "Id"
    )
    name_column = (
        AMS_ORIGIN_NAME_COLUMN
        if AMS_ORIGIN_NAME_COLUMN in df.columns
        else "Razao Social"
    )
    if id_column not in df.columns:
        return pd.DataFrame()

    audit = df.copy()
    audit["Número de Série"] = normalizar_numero_serie(audit["Número de Série"])
    audit = audit.dropna(subset=["Número de Série"])
    audit = audit[audit[id_column].notna()].copy()
    if audit.empty:
        return pd.DataFrame()

    if name_column not in audit.columns:
        audit[name_column] = ""

    audit["_conta_origem"] = [
        f"{account_id} - {account_name}" if account_name else account_id
        for account_id, account_name in zip(
            audit[id_column].astype("string").fillna("").str.strip(),
            audit[name_column].astype("string").fillna("").str.strip(),
        )
    ]

    group_keys = _ams_asset_keys(audit)
    aggregations: dict[str, tuple[str, object]] = {
        "qtd_ids": (id_column, "nunique"),
        "ids": (id_column, _unique_non_empty),
        "contas": ("_conta_origem", _unique_non_empty),
    }
    if "ano_reparo" in audit.columns:
        audit["ano_reparo"] = pd.to_numeric(
            audit["ano_reparo"], errors="coerce"
        ).astype("Int64")
        aggregations["primeiro_ano"] = ("ano_reparo", "min")
        aggregations["ultimo_ano"] = ("ano_reparo", "max")

    result = (
        audit.groupby(group_keys, as_index=False, dropna=False)
        .agg(**aggregations)
    )
    result = result[result["qtd_ids"] > 1].reset_index(drop=True)
    return result



def detectar_maquinas_duplicadas_parque(df: pd.DataFrame) -> pd.DataFrame:
    """Return current-fleet machine keys that appear more than once.

    The analytical unit is the machine, not machine-per-account. A duplicated
    current-fleet key is therefore a data-quality conflict and must be resolved
    before the Park x AMS merge.
    """
    if df.empty or "Número de série" not in df.columns:
        return pd.DataFrame()

    audit = df.copy()
    audit["Número de série"] = normalizar_numero_serie(audit["Número de série"])
    audit = audit.dropna(subset=["Número de série"])
    if audit.empty:
        return pd.DataFrame()

    group_keys = ["Número de série"]
    if "Modelo" in audit.columns:
        group_keys.append("Modelo")
    elif "Descrição" in audit.columns:
        group_keys.append("Descrição")

    if "Id" not in audit.columns:
        audit["Id"] = ""
    name_column = "Razao Social" if "Razao Social" in audit.columns else None
    if name_column is None:
        audit["_nome_conta_parque"] = ""
        name_column = "_nome_conta_parque"

    audit["_conta_parque"] = [
        f"{account_id} - {account_name}" if account_name else account_id
        for account_id, account_name in zip(
            audit["Id"].astype("string").fillna("").str.strip(),
            audit[name_column].astype("string").fillna("").str.strip(),
        )
    ]

    result = (
        audit.groupby(group_keys, as_index=False, dropna=False)
        .agg(
            qtd_registros=("Número de série", "size"),
            qtd_ids=("Id", "nunique"),
            ids=("Id", _unique_non_empty),
            contas=("_conta_parque", _unique_non_empty),
        )
    )
    return result[result["qtd_registros"] > 1].reset_index(drop=True)


def consolidar_conta_atual(
    df: pd.DataFrame,
    *,
    parque_id_column: str = "Id_x",
    parque_name_column: str = "Razao Social_x",
    ams_id_column: str = "Id_y",
    ams_name_column: str = "Razao Social_y",
) -> pd.DataFrame:
    """Assign exactly one current account to each merged machine row.

    Current Park is authoritative. AMS latest-account data is used only when a
    machine is absent from the current Park. Id and customer name always come
    from the same source row.
    """
    result = df.copy()

    def _column_or_empty(column: str) -> pd.Series:
        if column in result.columns:
            return result[column]
        return pd.Series(pd.NA, index=result.index, dtype="object")

    parque_id = _column_or_empty(parque_id_column)
    parque_name = _column_or_empty(parque_name_column)
    ams_id = _column_or_empty(ams_id_column)
    ams_name = _column_or_empty(ams_name_column)

    parque_presente = parque_id.astype("string").fillna("").str.strip().ne("")

    result["Id"] = ams_id
    result["Razão Social"] = ams_name
    result.loc[parque_presente, "Id"] = parque_id.loc[parque_presente]
    result.loc[parque_presente, "Razão Social"] = parque_name.loc[parque_presente]

    return result

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
    result[AMS_ORIGIN_ID_COLUMN] = result["Id"]
    result[AMS_ORIGIN_NAME_COLUMN] = result["Razao Social"]
    result = result.drop(columns=["Cliente"])
    mover_coluna(result, AMS_ORIGIN_NAME_COLUMN)
    mover_coluna(result, AMS_ORIGIN_ID_COLUMN)
    mover_coluna(result, "Razao Social")
    mover_coluna(result, "Id")
    result["Data de compra"] = (
        pd.Timestamp.today().normalize()
        - pd.to_timedelta(result["Idade em Anos"] * 365, unit="D")
    )
    mover_coluna(result, "Data de compra", result.columns.get_loc("Idade em Anos"))

    if "ano_reparo" not in result.columns:
        result["ano_reparo"] = pd.NA

    result["_ordem_ams"] = range(len(result))
    result = result.sort_values(
        ["ano_reparo", "_ordem_ams"],
        kind="stable",
        na_position="last",
    )

    group_keys = _ams_asset_keys(result)
    serial_valido = result["Número de Série"].astype("string").str.strip().ne("")
    if serial_valido.any():
        conta_atual = (
            result.loc[serial_valido]
            .groupby(group_keys, sort=False, dropna=False)[
                [AMS_ORIGIN_ID_COLUMN, AMS_ORIGIN_NAME_COLUMN]
            ]
            .transform(lambda values: values.iloc[-1])
        )
        result.loc[serial_valido, "Id"] = conta_atual[AMS_ORIGIN_ID_COLUMN]
        result.loc[serial_valido, "Razao Social"] = conta_atual[
            AMS_ORIGIN_NAME_COLUMN
        ]

    result = result.drop(columns=["_ordem_ams"])
    result["_presente_ams"] = True

    return result


def preparar_sap_group(df: pd.DataFrame, cust_names: list[str] = ['']) -> pd.DataFrame:
    first_line = df.iloc[0]
    new_names = {
        coluna: valor
        for coluna, valor in first_line.items()
        if pd.notna(valor) and valor != ""
    }
    df.rename(columns=new_names, inplace=True)
    df = df.iloc[1:].reset_index(drop=True)
    df = df[df["Customer(sv)"].isin(cust_names)].reset_index(drop=True)

    return df


def preparar_sap_split(df: pd.DataFrame, serial_numbers: list[str] = [''], tool_types: list[str] = ['']) -> pd.DataFrame:
    first_line = df.iloc[0]
    new_names = {
        coluna: valor
        for coluna, valor in first_line.items()
        if pd.notna(valor) and valor != ""
    }
    df.rename(columns=new_names, inplace=True)
    df = df.iloc[2:].reset_index(drop=True)

    df = df[
        (df["(n) Serial Number"].isin(serial_numbers))
        &
        (df["Tool Type"].isin(tool_types))
    ].reset_index(drop=True)

    return df


def agrupar_ams(df: pd.DataFrame) -> pd.DataFrame:
    group_keys = [
        column for column in AMS_GROUP_KEYS if column in df.columns
    ]
    aggregations = {
        "Id": "last",
        "Razao Social": "last",
        "Nome do Material": "first",
        "FM Frota": "last",
        "# Notif.": "sum",
        "# Reparos": "sum",
        "Custo de Reparos": "sum",
        "Pagado pelo Cliente": "sum",
        "Economia": "sum",
    }
    for column in ["Material", "Data de compra", "Tipo", "Linha"]:
        if column in df.columns and column not in group_keys:
            aggregations[column] = "last"

    result = (
        df.groupby(group_keys, as_index=False)
        .agg(aggregations)
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

    repair_keys = ["Número de Série"]
    if "Modelo" in pq.columns and "Modelo" in ams.columns:
        repair_keys.append("Modelo")

    reparos = (
        ams.dropna(subset=["Número de Série"])
        .groupby(repair_keys, as_index=False)
        .agg(
            Reparos_no_período=("# Reparos", "sum"),
            Custo_no_período=("Custo de Reparos", "sum"),
            Pago_no_período=("Pagado pelo Cliente", "sum"),
            Economia_no_período=("Economia", "sum"),
        )
    )

    resultado = pq.merge(
        reparos,
        on=repair_keys,
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
