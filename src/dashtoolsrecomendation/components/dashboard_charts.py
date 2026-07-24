from __future__ import annotations

import pandas as pd
import plotly.express as px
from plotly.graph_objs import Figure


RED = "#D2051E"
BEIGE = "#D7CEBD"
TAUPE = "#887F6E"
WINE = "#671C3E"
TEXT = "#ffffff"
MUTED_TEXT = "#d6d6e7"

RECOMMENDATION_COLORS = {
    "Troca prioritária": RED,
    "Planejar renovação": WINE,
    "Monitorar": TAUPE,
    "Manter": BEIGE,
}


def configurar_layout(fig: Figure, altura: int = 330) -> Figure:
    fig.update_layout(
        height=altura,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, size=12),
        title=dict(font=dict(color=TEXT, size=16)),
        legend=dict(
            font=dict(color=MUTED_TEXT, size=12),
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=20, r=20, t=45, b=20),
    )
    fig.update_xaxes(
        showgrid=False,
        color=MUTED_TEXT,
        title_font=dict(color=MUTED_TEXT),
        tickfont=dict(color=MUTED_TEXT),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        color=MUTED_TEXT,
        title_font=dict(color=MUTED_TEXT),
        tickfont=dict(color=MUTED_TEXT),
    )
    return fig


def grafico_barra_horizontal(df: pd.DataFrame) -> Figure:
    fig = px.bar(
        df.sort_values("qtd", ascending=True),
        x="qtd", y="modelo", orientation="h", text="qtd",
        title="Quantidades por Modelo", color_discrete_sequence=[RED],
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    return configurar_layout(fig, altura=360)


def grafico_rosca_grupo(df: pd.DataFrame) -> Figure:
    fig = px.pie(
        df, names="Grupo_Grafico", values="Quantidade", hole=0.62,
        title="Quantidade por Grupo", color="Grupo_Grafico",
        color_discrete_map={"Compradas": RED, "Frota": BEIGE},
    )
    fig.update_traces(
        textinfo="percent+label", textposition="outside", automargin=True,
        textfont=dict(color=TEXT, size=14),
    )
    return configurar_layout(fig, altura=360)


def grafico_grupo_bar(df: pd.DataFrame) -> Figure:
    fig = px.bar(
        df, x="Grupo_Grafico", y="Quantidade", color="Indicador",
        barmode="group", text="Quantidade", title="Ferramentas x reparações",
        labels={"Grupo_Grafico": "", "Indicador": ""},
        color_discrete_map={"Ferramentas": RED, "Reparações": BEIGE},
    )
    fig.update_traces(
        textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y}<extra></extra>",
    )
    return configurar_layout(fig, altura=360)


def grafico_reparacoes_por_idade(df: pd.DataFrame) -> Figure:
    fig = px.bar(
        df.sort_values("idade_int (a)"), x="idade_int (a)",
        y="Quantidade de reparos", text="Quantidade de reparos",
        title="Reparações por idade",
        labels={"idade_int (a)": "Idade (anos)", "Quantidade de reparos": "Reparações"},
        color_discrete_sequence=[RED],
    )
    fig.update_traces(
        texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False,
        hovertemplate="<b>Idade: %{x} anos</b><br>Reparações: %{y:,.0f}<extra></extra>",
    )
    return configurar_layout(fig, altura=360)


def grafico_maquinas_por_idade(df: pd.DataFrame) -> Figure:
    fig = px.bar(
        df.sort_values("idade_int (a)"),
        x="idade_int (a)",
        y="Quantidade de máquinas",
        text="Quantidade de máquinas",
        title="Máquinas por idade",
        labels={
            "idade_int (a)": "Idade (anos)",
            "Quantidade de máquinas": "Máquinas",
        },
        color_discrete_sequence=[RED],
    )
    fig.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>Idade: %{x} anos</b><br>"
            "Máquinas: %{y:,.0f}<extra></extra>"
        ),
    )
    # A matriz exibida ao lado usa 430 px. Manter a mesma altura nos dois
    # gráficos superiores alinha o início dos cards da linha seguinte.
    return configurar_layout(fig, altura=430)


def _grafico_faixa_barra(
    df: pd.DataFrame,
    value_column: str,
    title: str,
    axis_title: str,
) -> Figure:
    fig = px.bar(
        df, x="Faixa etária", y=value_column, text=value_column,
        title=title, color="Faixa etária",
        labels={"Faixa etária": "", value_column: axis_title},
        color_discrete_sequence=[RED, BEIGE],
    )
    fig.update_traces(
        texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False,
        hovertemplate=f"<b>%{{x}} anos</b><br>{axis_title}: %{{y:,.0f}}<extra></extra>",
    )
    configurar_layout(fig, altura=360)
    fig.update_layout(showlegend=False)
    return fig


def _grafico_faixa_rosca(
    df: pd.DataFrame,
    value_column: str,
    title: str,
    label: str,
) -> Figure:
    fig = px.pie(
        df, names="Faixa etária", values=value_column, hole=0.62,
        title=title, color="Faixa etária", color_discrete_sequence=[RED, BEIGE],
    )
    fig.update_traces(
        textinfo="percent+label", textposition="outside", automargin=True,
        textfont=dict(color=TEXT, size=14),
        hovertemplate=(
            f"<b>%{{label}} anos</b><br>{label}: %{{value:,.0f}}"
            "<br>Percentual: %{percent}<extra></extra>"
        ),
    )
    configurar_layout(fig, altura=360)
    fig.update_layout(showlegend=False)
    return fig


def grafico_reparacoes_por_faixa_idade(df: pd.DataFrame) -> Figure:
    # return _grafico_faixa_barra(
    #     df, "Quantidade de reparos", "Reparações por faixa de idade", "Reparações"
    # )
    return _grafico_faixa_barra(
        df, "Reparações", "Reparações por faixa de idade", "Reparações"
    )


def grafico_percentual_reparacoes_por_faixa_idade(df: pd.DataFrame) -> Figure:
    return _grafico_faixa_rosca(
        df, "Reparações", "Percentual de reparações por faixa", "Reparações"
    )


def grafico_maquinas_por_faixa_idade(df: pd.DataFrame) -> Figure:
    return _grafico_faixa_barra(
        df, "Máquinas", "Máquinas por faixa de idade", "Máquinas"
    )


def grafico_percentual_maquinas_por_faixa_idade(df: pd.DataFrame) -> Figure:
    return _grafico_faixa_rosca(
        df, "Máquinas", "Percentual de máquinas por faixa", "Máquinas"
    )


def grafico_reparacoes_ams_por_ano(df: pd.DataFrame) -> Figure:
    fig = px.bar(
        df,
        x="ano_reparo",
        y="Reparações",
        text="Reparações",
        title="Reparações por ano",
        labels={"ano_reparo": "Ano", "Reparações": "Reparações"},
        color_discrete_sequence=[RED],
    )
    fig.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>Reparações: %{y:,.0f}<extra></extra>",
    )
    fig.update_xaxes(dtick=1)
    return configurar_layout(fig, altura=360)


def grafico_custos_ams_por_ano(df: pd.DataFrame) -> Figure:
    fig = px.line(
        df,
        x="ano_reparo",
        y="Custo",
        markers=True,
        title="Custo de reparações por ano",
        labels={"ano_reparo": "Ano", "Custo": "Custo de reparações"},
        color_discrete_sequence=[BEIGE],
    )
    fig.update_traces(
        line=dict(width=4),
        marker=dict(size=9),
        hovertemplate="<b>%{x}</b><br>Custo: R$ %{y:,.2f}<extra></extra>",
    )
    fig.update_xaxes(dtick=1)
    fig.update_yaxes(tickprefix="R$ ", separatethousands=True)
    return configurar_layout(fig, altura=360)


def _grafico_modelo_horizontal(
    df: pd.DataFrame,
    value_column: str,
    title: str,
    axis_title: str,
    currency: bool = False,
) -> Figure:
    data = df.nlargest(10, value_column).sort_values(value_column)
    fig = px.bar(
        data,
        x=value_column,
        y="Modelo",
        orientation="h",
        text=value_column,
        title=title,
        labels={"Modelo": "", value_column: axis_title},
        color_discrete_sequence=[RED],
    )
    texttemplate = "R$ %{text:,.0f}" if currency else "%{text:.2f}"
    fig.update_traces(
        texttemplate=texttemplate,
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            f"<b>%{{y}}</b><br>{axis_title}: "
            + ("R$ %{x:,.2f}" if currency else "%{x:.2f}")
            + "<extra></extra>"
        ),
    )
    if currency:
        fig.update_xaxes(tickprefix="R$ ", separatethousands=True)
    return configurar_layout(fig, altura=360)


def grafico_reparacoes_por_maquina_modelo(df: pd.DataFrame) -> Figure:
    return _grafico_modelo_horizontal(
        df,
        "Reparações por máquina",
        "Taxa de reparação por modelo",
        "Reparações por máquina",
    )


def grafico_custo_por_maquina_modelo(df: pd.DataFrame) -> Figure:
    return _grafico_modelo_horizontal(
        df,
        "Custo por máquina",
        "Custo por máquina e modelo",
        "Custo por máquina",
        currency=True,
    )


def grafico_idade_media_modelo(df: pd.DataFrame) -> Figure:
    return _grafico_modelo_horizontal(
        df,
        "Idade_média",
        "Idade média por modelo",
        "Idade média (anos)",
    )


def grafico_composicao_custo_ams(df: pd.DataFrame) -> Figure:
    fig = px.pie(
        df,
        names="Componente",
        values="Valor",
        hole=0.62,
        title="Composição do custo de reparações",
        color="Componente",
        color_discrete_map={
            "Pago pelo cliente": RED,
            "Valor absorvido": BEIGE,
        },
    )
    fig.update_traces(
        textinfo="percent+label",
        textposition="outside",
        automargin=True,
        textfont=dict(color=TEXT, size=13),
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    )
    configurar_layout(fig, altura=360)
    fig.update_layout(showlegend=False)
    return fig


def grafico_reparacoes_por_maquina_faixa(df: pd.DataFrame) -> Figure:
    fig = px.bar(
        df,
        x="Faixa etária",
        y="Reparações por máquina",
        text="Reparações por máquina",
        title="Frequência observada por faixa etária",
        labels={
            "Faixa etária": "Idade atual (anos)",
            "Reparações por máquina": "Reparações por máquina",
        },
        color="Faixa etária",
        color_discrete_sequence=[RED, BEIGE],
    )
    fig.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x} anos</b><br>Reparações por máquina: %{y:.2f}"
            "<extra></extra>"
        ),
    )
    configurar_layout(fig, altura=360)
    fig.update_layout(showlegend=False)
    return fig


def grafico_reparacoes_por_maquina_faixa2(df: pd.DataFrame) -> Figure:
    fig = px.bar(
        df,
        x="Faixa etária",
        y="Reparações por máquina",
        text="Reparações por máquina",
        title="Frequência observada por faixa etária2",
        labels={
            "Faixa etária": "Idade atual (anos)",
            "Reparações por máquina": "Reparações por máquina",
        },
        color="Faixa etária",
        color_discrete_sequence=[RED, BEIGE],
    )
    fig.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x} anos</b><br>Reparações por máquina: %{y:.2f}"
            "<extra></extra>"
        ),
    )
    configurar_layout(fig, altura=360)
    fig.update_layout(showlegend=False)
    return fig


def grafico_custo_por_maquina_faixa(df: pd.DataFrame) -> Figure:
    fig = px.bar(
        df,
        x="Faixa etária",
        y="Custo por máquina",
        text="Custo por máquina",
        title="Custo observado por máquina e faixa etária",
        labels={
            "Faixa etária": "Idade atual (anos)",
            "Custo por máquina": "Custo por máquina",
        },
        color="Faixa etária",
        color_discrete_sequence=[RED, BEIGE],
    )
    fig.update_traces(
        texttemplate="R$ %{text:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x} anos</b><br>Custo por máquina: R$ %{y:,.2f}"
            "<extra></extra>"
        ),
    )
    fig.update_yaxes(tickprefix="R$ ", separatethousands=True)
    configurar_layout(fig, altura=360)
    fig.update_layout(showlegend=False)
    return fig


def grafico_matriz_prioridade(df: pd.DataFrame) -> Figure:
    size_column = "Custo com impostos"
    work = df.copy()
    # Plotly exige tamanho estritamente positivo; preserva custo zero no hover.
    work["Tamanho"] = work[size_column].clip(lower=1)
    fig = px.scatter(
        work,
        x="Idade atual",
        y="Reparações no período",
        size="Tamanho",
        color="Recomendação",
        color_discrete_map=RECOMMENDATION_COLORS,
        hover_name="Número de Série",
        hover_data={
            "Modelo": True,
            "Custo com impostos": ":,.2f",
            "Índice de prioridade": ":.1f",
            "Motivo principal": True,
            "Tamanho": False,
        },
        title="Matriz de prioridade de renovação",
        labels={
            "Idade atual": "Idade atual (anos)",
            "Reparações no período": "Reparações registradas no período",
            "Recomendação": "Recomendação",
        },
        size_max=42,
    )
    fig.update_traces(
        marker=dict(line=dict(width=1, color="rgba(255,255,255,0.45)")),
    )
    fig.update_layout(legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"))
    return configurar_layout(fig, altura=430)


def grafico_pareto_custo_maquina(df: pd.DataFrame, quantidade_selecionada: int = 0) -> Figure:
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    work = df.copy()
    colors = [RED if position <= quantidade_selecionada else BEIGE for position in work["Posição"]]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=work["Posição"],
            y=work["Custo com impostos"],
            name="Custo por máquina",
            marker_color=colors,
            customdata=work[["Número de Série", "Modelo"]],
            hovertemplate=(
                "<b>Posição %{x}</b><br>Série: %{customdata[0]}"
                "<br>Modelo: %{customdata[1]}<br>Custo: R$ %{y:,.2f}<extra></extra>"
            ),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=work["Posição"],
            y=work["Percentual acumulado"] * 100,
            name="Percentual acumulado",
            mode="lines",
            line=dict(color="#ffffff", width=3),
            hovertemplate="Posição %{x}<br>Acumulado: %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.update_layout(title="Pareto do custo por máquina")
    fig.update_xaxes(title_text="Máquinas ordenadas pelo custo")
    fig.update_yaxes(title_text="Custo observado", tickprefix="R$ ", secondary_y=False)
    fig.update_yaxes(
        title_text="Percentual acumulado",
        ticksuffix="%",
        range=[0, 105],
        secondary_y=True,
    )
    return configurar_layout(fig, altura=430)


def grafico_evolucao_reparacoes(df: pd.DataFrame) -> Figure:
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_bar(
        x=df["Ano"],
        y=df["Reparações realizadas"],
        name="Realizado",
        marker_color=RED,
        text=df["Reparações realizadas"],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Realizado: %{y:,.0f}<extra></extra>",
    )
    adicional = (df["Reparações projetadas"] - df["Reparações realizadas"]).clip(lower=0)
    if adicional.gt(0).any():
        fig.add_bar(
            x=df["Ano"],
            y=adicional,
            name="Projeção adicional",
            marker_color=BEIGE,
            hovertemplate="<b>%{x}</b><br>Projeção adicional: %{y:,.1f}<extra></extra>",
        )
    fig.update_layout(barmode="stack", title="Reparações por ano")
    fig.update_xaxes(dtick=1, title=None)   
    fig.update_yaxes(title="Reparações")
    return configurar_layout(fig, altura=360)


def grafico_evolucao_custos(df: pd.DataFrame) -> Figure:
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_bar(
        x=df["Ano"],
        y=df["Custo realizado"],
        name="Realizado",
        marker_color=TAUPE,
        hovertemplate="<b>%{x}</b><br>Realizado: R$ %{y:,.2f}<extra></extra>",
    )
    adicional = (df["Custo projetado"] - df["Custo realizado"]).clip(lower=0)
    if adicional.gt(0).any():
        fig.add_bar(
            x=df["Ano"],
            y=adicional,
            name="Projeção adicional",
            marker_color=BEIGE,
            hovertemplate="<b>%{x}</b><br>Projeção adicional: R$ %{y:,.2f}<extra></extra>",
        )
    fig.update_layout(barmode="stack", title="Custo de reparações por ano")
    fig.update_xaxes(dtick=1, title=None)
    fig.update_yaxes(title="Custo", tickprefix="R$ ", separatethousands=True)
    return configurar_layout(fig, altura=360)


def grafico_distribuicao_recomendacoes(df: pd.DataFrame) -> Figure:
    order = ["Troca prioritária", "Planejar renovação", "Monitorar", "Manter"]
    counts = (
        df["Recomendação"]
        .value_counts()
        .reindex(order, fill_value=0)
        .rename_axis("Recomendação")
        .reset_index(name="Máquinas")
    )
    fig = px.bar(
        counts,
        x="Recomendação",
        y="Máquinas",
        text="Máquinas",
        color="Recomendação",
        color_discrete_map=RECOMMENDATION_COLORS,
        title="Distribuição da recomendação analítica",
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title="")
    return configurar_layout(fig, altura=360)
