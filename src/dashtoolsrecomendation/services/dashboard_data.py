from __future__ import annotations

import numpy as np
import pandas as pd


DROP_COLUMNS = [
    "Tipo de Contrato",
    "Ferramenta de empréstimo permitida",
    "Cobertura de roubo",
    "Número do Equipamento",
]


def idade_anos_completos(
    data_compra: pd.Timestamp,
    hoje: pd.Timestamp | None = None,
) -> int | float:
    if pd.isna(data_compra):
        return np.nan

    referencia = (hoje or pd.Timestamp.today()).normalize()
    idade = referencia.year - data_compra.year

    if (referencia.month, referencia.day) < (data_compra.month, data_compra.day):
        idade -= 1

    return idade


def preparar_dashboard(
    df_pq: pd.DataFrame,
    df_data_ids: pd.DataFrame,
    hoje: pd.Timestamp | None = None,
) -> pd.DataFrame:
    df = df_pq.copy()
    df = df.drop(columns=DROP_COLUMNS, errors="ignore")
    df = df.fillna("").replace({"None": "", "nan": "", "NaN": ""})
    df = pd.merge(df, df_data_ids, on="Id", how="left")

    for column in ["cliente", "UF"]:
        if column in df.columns:
            values = df.pop(column)
            df.insert(0, column, values)

    defaults = {
        "Data de compra": pd.NaT,
        "Último Reparo": "",
        "Quantidade de reparos": 0,
        "# Reparos": 0,
        "# Notif.": 0,
        "Garantia": "",
        "Grupo": "Não informado",
    }
    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default

    df["Data de compra"] = pd.to_datetime(df["Data de compra"], errors="coerce")
    df["idade_int (a)"] = (
        df["Data de compra"]
        .apply(idade_anos_completos, hoje=hoje)
        .fillna(0)
        .astype(int)
    )

    for column in ["Quantidade de reparos", "# Reparos", "# Notif."]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    df["reparada"] = np.where(
        (
            df["Último Reparo"].notna()
            & df["Último Reparo"].astype(str).str.strip().ne("")
        )
        | df["Quantidade de reparos"].gt(0)
        | df["# Reparos"].gt(0),
        "Sim",
        "Não",
    )
    df["Garantia"] = np.where(
        df["Garantia"].astype("string").str.lower().eq("dentro")
        | df["Grupo"].astype("string").str.lower().eq("frota"),
        "Sim",
        "Não",
    )
    df["Reparo Rejeitado"] = np.where(
        df["# Notif."].gt(0) & df["# Notif."].gt(df["# Reparos"]),
        "Sim",
        "Não",
    )

    for marker in ["_presente_parque", "_presente_ams"]:
        if marker not in df.columns:
            df[marker] = marker == "_presente_parque"
        df[marker] = df[marker].fillna(False).astype(bool)

    df["Status de conciliação"] = np.select(
        [
            df["_presente_parque"] & df["_presente_ams"],
            df["_presente_parque"],
            df["_presente_ams"],
        ],
        [
            "Presente nas duas fontes",
            "Somente no parque atual",
            "Somente no AMS",
        ],
        default="Origem não identificada",
    )

    return df.reset_index(drop=True)


def dados_graficos(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    modelos = df["Modelo"].value_counts().rename_axis("modelo").reset_index(name="qtd")

    grupos = df.assign(
        Grupo_Grafico=df["Grupo"].str.lower().map(
            {"comprado": "Compradas", "frota": "Frota"}
        )
    ).dropna(subset=["Grupo_Grafico"])

    grupo_rosca = (
        grupos.groupby("Grupo_Grafico")
        .size()
        .reset_index(name="Quantidade")
    )
    grupo_barras = (
        grupos.groupby("Grupo_Grafico")
        .agg(
            Ferramentas=("Grupo", "size"),
            Reparações=("Quantidade de reparos", "sum"),
        )
        .reset_index()
        .melt(
            id_vars="Grupo_Grafico",
            value_vars=["Ferramentas", "Reparações"],
            var_name="Indicador",
            value_name="Quantidade",
        )
    )
    reparacoes_idade = (
        df.groupby("idade_int (a)", as_index=False)["Quantidade de reparos"].sum()
    )
    maquinas_idade = (
        df.groupby("idade_int (a)")
        .size()
        .reset_index(name="Quantidade de máquinas")
    )

    return {
        "modelos": modelos,
        "grupo_rosca": grupo_rosca,
        "grupo_barras": grupo_barras,
        "reparacoes_idade": reparacoes_idade,
        "maquinas_idade": maquinas_idade,
    }


def dados_faixas_idade(
    df: pd.DataFrame,
    idade_corte: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    idade_maxima = max(0, int(df["idade_int (a)"].max()))
    faixas = [f"0 a {idade_corte}", f"{idade_corte + 1} a {idade_maxima}"]
    ate_corte = df["idade_int (a)"].le(idade_corte)

    reparacoes = pd.DataFrame(
        {
            "Faixa etária": faixas,
            "Quantidade de reparos": [
                df.loc[ate_corte, "Quantidade de reparos"].sum(),
                df.loc[~ate_corte, "Quantidade de reparos"].sum(),
            ],
        }
    )
    maquinas = pd.DataFrame(
        {
            "Faixa etária": faixas,
            "Quantidade de máquinas": [int(ate_corte.sum()), int((~ate_corte).sum())],
        }
    )
    return reparacoes, maquinas

AMS_NUMERIC_COLUMNS = [
    "# Reparos",
    "Custo de Reparos",
    "Pagado pelo Cliente",
    "Economia",
    "Idade em Anos",
]


def preparar_dashboard_ams(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza os campos usados pelos indicadores do relatório AMS."""
    result = df.copy()

    defaults = {
        "ano_reparo": pd.NA,
        "Modelo": "Não identificado",
        "Número de Série": "",
        "# Reparos": 0,
        "Custo de Reparos": 0,
        "Pagado pelo Cliente": 0,
        "Economia": 0,
        "Idade em Anos": 0,
    }
    for column, default in defaults.items():
        if column not in result.columns:
            result[column] = default

    result["ano_reparo"] = pd.to_numeric(
        result["ano_reparo"], errors="coerce"
    ).astype("Int64")
    for column in AMS_NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)

    result["Modelo"] = (
        result["Modelo"]
        .astype("string")
        .str.strip()
        .replace({"": "Não identificado", "nan": "Não identificado"})
        .fillna("Não identificado")
    )
    result["Número de Série"] = (
        result["Número de Série"].astype("string").str.strip().fillna("")
    )
    return result


def dados_graficos_ams(df: pd.DataFrame) -> dict[str, pd.DataFrame | dict[str, float]]:
    ams = preparar_dashboard_ams(df)

    por_ano = (
        ams.dropna(subset=["ano_reparo"])
        .groupby("ano_reparo", as_index=False)
        .agg(
            Reparações=("# Reparos", "sum"),
            Custo=("Custo de Reparos", "sum"),
            Pago=("Pagado pelo Cliente", "sum"),
            Economia=("Economia", "sum"),
        )
        .sort_values("ano_reparo")
    )

    serial_valido = ams["Número de Série"].ne("")
    maquinas_por_modelo = (
        ams.loc[serial_valido]
        .groupby("Modelo")["Número de Série"]
        .nunique()
    )
    linhas_por_modelo = ams.groupby("Modelo").size()

    por_modelo = (
        ams.groupby("Modelo", as_index=False)
        .agg(
            Reparações=("# Reparos", "sum"),
            Custo=("Custo de Reparos", "sum"),
            Pago=("Pagado pelo Cliente", "sum"),
            Economia=("Economia", "sum"),
            Idade_média=("Idade em Anos", "mean"),
        )
        .set_index("Modelo")
    )
    por_modelo["Máquinas"] = maquinas_por_modelo.reindex(
        por_modelo.index
    ).fillna(linhas_por_modelo).astype(int)
    denominador = por_modelo["Máquinas"].replace(0, np.nan)
    por_modelo["Reparações por máquina"] = (
        por_modelo["Reparações"] / denominador
    ).fillna(0)
    por_modelo["Custo por máquina"] = (
        por_modelo["Custo"] / denominador
    ).fillna(0)
    por_modelo = por_modelo.reset_index().sort_values(
        ["Reparações por máquina", "Custo por máquina"], ascending=False
    )

    composicao_custo = pd.DataFrame(
        {
            "Componente": ["Pago pelo cliente", "Valor absorvido"],
            "Valor": [
                ams["Pagado pelo Cliente"].sum(),
                ams["Economia"].sum(),
            ],
        }
    )
    maquinas = int(ams.loc[serial_valido, "Número de Série"].nunique())
    if maquinas == 0:
        maquinas = len(ams)

    totais = {
        "maquinas": maquinas,
        "reparacoes": float(ams["# Reparos"].sum()),
        "custo": float(ams["Custo de Reparos"].sum()),
        "pago": float(ams["Pagado pelo Cliente"].sum()),
        "economia": float(ams["Economia"].sum()),
    }
    totais["reparacoes_por_maquina"] = (
        totais["reparacoes"] / maquinas if maquinas else 0
    )
    totais["custo_por_maquina"] = totais["custo"] / maquinas if maquinas else 0

    return {
        "base": ams,
        "por_ano": por_ano,
        "por_modelo": por_modelo,
        "composicao_custo": composicao_custo,
        "totais": totais,
    }
