from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from dashtoolsrecomendation.components import cards, dashboard_charts, dashboard_filters
from dashtoolsrecomendation.services import (
    dashboard_data,
    data_processing,
    get_data_ids,
    renewal_analysis,
    write_xls,
)
from dashtoolsrecomendation.utils import (
    formatters,
    download_xlsx,
    df_config
)


def prepare_df() -> pd.DataFrame:

    return dashboard_data.preparar_dashboard(
        st.session_state.df_pq,
        get_data_ids.get(),
    )


def _numero(valor: float, casas: int = 0) -> str:
    return formatters.br_num(float(valor), casas)


def _moeda(valor: float, casas: int = 0) -> str:
    return formatters.br_num(float(valor), casas, use_brl=True)


def _percentual(valor: float, casas: int = 1) -> str:
    return f"{_numero(valor * 100, casas)}%"


def _render_cards_resumo(resumo: dict[str, float]) -> None:
    dados = [
        (
            "PARQUE ATUAL",
            _numero(resumo["maquinas"]),
            "Máquinas consideradas após os filtros",
        ),
        (
            "PARQUE REPARADO",
            _percentual(resumo["percentual_reparadas"]),
            f'{_numero(resumo["maquinas_reparadas"])} máquinas com reparação',
        ),
        (
            "REPARAÇÕES",
            _numero(resumo["reparacoes"]),
            "Registradas pela Hilti no período",
        ),
        (
            "REPARAÇÕES/MÁQUINA",
            _numero(resumo["reparacoes_por_maquina_parque"], 2),
            "Denominador: todo o parque filtrado",
        ),
        (
            "CUSTO OBSERVADO",
            _moeda(resumo["custo"]),
            "Valor com o fator de impostos aplicado",
        ),
        (
            "CUSTO/MÁQUINA",
            _moeda(resumo["custo_por_maquina_parque"]),
            "Denominador: todo o parque filtrado",
        ),
    ]
    columns = st.columns(len(dados))
    for column, (label, value, subtitle) in zip(columns, dados):
        with column:
            cards.metric_card(label, value, subtitle)


def _render_small_cards(items: list[tuple[str, str, str]]) -> None:
    columns = st.columns(len(items))
    for column, (label, value, subtitle) in zip(columns, items):
        with column:
            cards.metric_card(label, value, subtitle)


def _analytical_table(base: pd.DataFrame, limit: int | None = None) -> pd.DataFrame:
    columns = [
        "Número de Série",
        "Modelo",
        "Grupo",
        "Idade atual",
        "Reparações no período",
        "Anos com reparação",
        "Custo com impostos",
        "Índice de prioridade",
        "Recomendação",
        "Motivo principal",
    ]
    result = base[[column for column in columns if column in base.columns]].copy()
    if limit is not None:
        result = result.head(limit)
    return result


def _render_ranking(base: pd.DataFrame, limit: int = 12) -> None:
    st.markdown("#### Máquinas com maior prioridade analítica")
    st.dataframe(
        _analytical_table(base, limit),
        hide_index=True,
        width="stretch",
        column_config={
            "Idade atual": st.column_config.NumberColumn(format="%.1f anos"),
            "Reparações no período": st.column_config.NumberColumn(format="%.0f"),
            "Anos com reparação": st.column_config.NumberColumn(format="%.0f"),
            "Custo com impostos": st.column_config.NumberColumn(format="R$ %.2f"),
            "Índice de prioridade": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
        },
    )
    df = _analytical_table(base, limit)
    texto = f'''
        registros localizados
    '''
    df_config.footer_df(
        _analytical_table(df, None),
        f'''
         registros localizados
        '''
    )
    download_xlsx.download(df=_analytical_table(base, None), key='ranking')


def _anos_disponiveis(df_ams: pd.DataFrame) -> list[int]:

    if df_ams.empty or "ano_reparo" not in df_ams.columns:
        return []
    anos = (
        pd.to_numeric(df_ams["ano_reparo"], errors="coerce")
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    return sorted(ano for ano in anos if ano >= renewal_analysis.ANALYSIS_START_YEAR)


def show() -> None:

    if "df_pq" not in st.session_state:
        st.warning("Carregue os arquivos do parque de máquinas e os relatórios AMS.")
        return
    if st.session_state.df_pq.empty:
        st.warning("Não existem dados para geração do dashboard.")
        return

    df_dashboard = prepare_df()
    df_ams = st.session_state.get("df_ams", pd.DataFrame())
    
    anos = _anos_disponiveis(df_ams)
    if not anos:
        st.warning(
            f"A base AMS não possui registros a partir de "
            f"{renewal_analysis.ANALYSIS_START_YEAR}. "
            "O dashboard precisa dessa janela para a análise de manutenção."
        )
        return

    st.sidebar.markdown("### Período observado")
    anos_selecionados = st.sidebar.multiselect(
        "Anos das reparações",
        options=anos,
        default=anos,
        key="filtro_anos_ams",
        help=(
            f"A análise começa em {renewal_analysis.ANALYSIS_START_YEAR} porque "
            "o histórico anterior não representa todas as manutenções "
            "realizadas pelo cliente."
        ),
    )
    if not anos_selecionados:
        st.info("Selecione ao menos um ano de reparação.")
        return

    with st.sidebar.expander("Parâmetros da análise", expanded=False):
        data_corte = st.date_input(
            "Data de corte da base",
            value=date.today(),
            key="data_corte_dashboard",
            help="Usada para calcular a idade atual e identificar ano parcial.",
        )
        fator_impostos = st.number_input(
            "Fator sobre o Net Price",
            min_value=1.0,
            max_value=3.0,
            value=renewal_analysis.DEFAULT_TAX_FACTOR,
            step=0.05,
            format="%.2f",
            help="O projeto atual utiliza Net Price × 1,40.",
        )
        projetar_ano_parcial = st.toggle(
            "Exibir projeção do ano parcial",
            value=False,
            help=(
                "A projeção anualiza o ritmo observado até a data de corte. "
                "É uma estimativa e não uma previsão de falhas."
            ),
        )

    df_com_periodo = data_processing.preparacoes_por_ano(
        df_dashboard,
        df_ams,
        anos_selecionados,
    )
    df_com_periodo["Quantidade de reparos"] = df_com_periodo["Reparos_no_período"]
    df_com_periodo["# Reparos"] = df_com_periodo["Reparos_no_período"]
    df_com_periodo["Custo de Reparos"] = df_com_periodo["Custo_no_período"]
    df_com_periodo["Pago pelo Cliente"] = df_com_periodo["Pago_no_período"]
    df_com_periodo["Economia"] = df_com_periodo["Economia_no_período"]
    df_com_periodo["reparada"] = (
        df_com_periodo["Reparos_no_período"]
        .gt(0)
        .map({True: "Sim", False: "Não"})
    )

    df_filtrado, _ = dashboard_filters.aplicar_filtros(df_com_periodo)
    if df_filtrado.empty:
        st.info("Nenhuma máquina foi encontrada para os filtros selecionados.")
        return

    base = renewal_analysis.preparar_base_maquinas(
        df_filtrado,
        df_ams,
        anos_selecionados,
        data_corte=data_corte,
        tax_factor=fator_impostos,
    )
    if base.empty:
        st.info("Não há números de série válidos no parque filtrado.")
        return

    resumo = renewal_analysis.resumo_executivo(base)
    _render_cards_resumo(resumo)

    ano_inicial = min(anos_selecionados)
    ano_final = max(anos_selecionados)
    parcial = ano_final == pd.Timestamp(data_corte).year
    complemento_periodo = f" até {formatters.date_br(data_corte)}" if parcial else ""
    st.markdown(
        f"""
        <div class="method-note">
            <strong>Escopo metodológico:</strong> reparações registradas pela Hilti de
            {ano_inicial} a {ano_final}{complemento_periodo}. O histórico anterior a
            {renewal_analysis.ANALYSIS_START_YEAR} não é tratado como histórico completo,
            pois, ou não existem manutenções anteriores ou eram realizadas na oficina do cliente. Os valores
            de custo usam fator <strong>{fator_impostos:.2f}</strong> sobre o Net Price para o cálculo aproximado de impostos.
            Esta base mede frequência e custo; disponibilidade, tempo parado e
            custo de oportunidade exigem datas de entrada/saída ou dados operacionais adicionais.
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_resumo, tab_modelos, tab_renovacao, tab_qualidade, tab_dados = st.tabs(
        [
            "Resumo executivo",
            "Modelos e custos",
            "Plano de renovação",
            "Qualidade dos dados",
            "Base filtrada",
        ]
    )

    with tab_resumo:

        idade_maxima = max(1, int(base["Idade atual"].max()))
        idade_corte = st.number_input(
            "Idade de corte para comparação",
            min_value=0,
            max_value=idade_maxima,
            value=min(5, idade_maxima),
            step=1,
            help=(
                "Compara frequência e custo por máquina, evitando usar apenas "
                "totais de faixas com tamanhos diferentes."
            ),
            key="idade_corte_resumo",
        )
        faixas = renewal_analysis.analise_faixas_idade(base, idade_corte)
        antigas = int(base["Idade atual"].gt(idade_corte).sum())
        pct_antigas = antigas / len(base) if len(base) else 0
        top_20 = min(20, len(base))
        _, cenario_top = renewal_analysis.cenario_renovacao(base, top_20)

        _render_small_cards(
            [
                (
                    f"ACIMA DE {idade_corte} ANOS",
                    _numero(antigas),
                    f"{_percentual(pct_antigas)} do parque filtrado",
                ),
                (
                    "TROCA PRIORITÁRIA",
                    _numero(resumo["troca_prioritaria"]),
                    "Classificação relativa ao conjunto filtrado",
                ),
                (
                    f"CUSTO CONCENTRADO NO TOP {top_20}",
                    _percentual(cenario_top["percentual_custo"]),
                    "Participação no custo observado, não economia projetada",
                ),
            ]
        )

        # Mantenha cada pilha de gráficos na mesma coluna. Se as linhas forem
        # criadas separadamente, a matriz (mais alta) define a altura de toda a
        # primeira linha e deixa um espaço vazio sob o gráfico de idade.
        left, right = st.columns([1.05, 1.2])
        with left:
            idade = (
                base.assign(Idade=base["Idade atual"].fillna(0).astype(int))
                .groupby("Idade")
                .size()
                .reset_index(name="Quantidade de máquinas")
                .rename(columns={"Idade": "idade_int (a)"})
            )
            st.plotly_chart(
                dashboard_charts.grafico_maquinas_por_idade(idade),
                width="stretch",
            )


            if st.session_state['config']['relacaoReparosIdade']:
                with st.container(key="container-graph-faixas"):
                    pass
                    idade_maxima = max(0, int(idade['idade_int (a)'].max()))
                    idade_maxima = max(0, 10)
                    idade_corte_key = "idade_corte_reparacoes"

                    if idade_corte_key not in st.session_state:
                        st.session_state[idade_corte_key] = min(5, idade_maxima)
                    else:
                        st.session_state[idade_corte_key] = min(
                            max(0, int(st.session_state[idade_corte_key])),
                            idade_maxima,
                        )

                    idade_corte = st.number_input(
                        "Idade de corte das máquinas",
                        min_value=0,
                        max_value=idade_maxima,
                        step=1,
                        key=idade_corte_key,
                        help=(
                            "Compara as reparações em máquinas com idade até o "
                            "limite selecionado e acima dele."
                        ),
                        width=260,
                    )

                    grafico_faixas, grafico_percentual = st.columns(2)

                    with grafico_faixas:
                        st.plotly_chart(
                            dashboard_charts.grafico_reparacoes_por_faixa_idade(faixas),
                            width="stretch",
                        )

                    with grafico_percentual:
                        st.plotly_chart(
                            dashboard_charts.grafico_percentual_reparacoes_por_faixa_idade(faixas),
                            width="stretch",
                        )

            st.plotly_chart(
                dashboard_charts.grafico_reparacoes_por_maquina_faixa(faixas),
                width="stretch",
            )

            with right:
                st.plotly_chart(
                    dashboard_charts.grafico_matriz_prioridade(base),
                    width="stretch",
                )

                if st.session_state['config']['relacaoReparosIdade']:

                    with st.container(key="container-graph-faixas-maquinas"):
                        # Compensa o espaço ocupado pelo seletor no container
                        # equivalente da coluna esquerda, mantendo os cards e
                        # os gráficos alinhados verticalmente.
                        st.space(68)

                        grafico_maquinas, grafico_percentual_maquinas = st.columns(2)

                        with grafico_maquinas:
                            st.plotly_chart(
                                dashboard_charts.grafico_maquinas_por_faixa_idade(
                                    faixas
                                ),
                                width="stretch",
                            )

                        with grafico_percentual_maquinas:
                            st.plotly_chart(
                                dashboard_charts.grafico_percentual_maquinas_por_faixa_idade(
                                    faixas
                                ),
                                width="stretch",
                            )

                st.plotly_chart(
                    dashboard_charts.grafico_custo_por_maquina_faixa(faixas),
                    width="stretch",
                )

        _render_ranking(base, None)

    with tab_modelos:
        series_filtradas = base["Número de Série"].tolist()
        annual = renewal_analysis.analise_anual(
            df_ams,
            anos_selecionados,
            series=series_filtradas,
            data_corte=data_corte,
            tax_factor=fator_impostos,
            projetar_ano_parcial=projetar_ano_parcial,
        )
        modelos = renewal_analysis.analise_modelos(base)
        composition = renewal_analysis.composicao_custo(base)

        if parcial:
            texto_parcial = (
                f"{ano_final} é um ano parcial até "
                f"{pd.Timestamp(data_corte).strftime('%d/%m/%Y')}."
            )
            if projetar_ano_parcial:
                texto_parcial += " A parcela bege representa projeção adicional."
            st.caption(texto_parcial)

        annual_repairs, annual_cost = st.columns(2)
        with annual_repairs:
            st.plotly_chart(
                dashboard_charts.grafico_evolucao_reparacoes(annual),
                width="stretch",
            )
        with annual_cost:
            st.plotly_chart(
                dashboard_charts.grafico_evolucao_custos(annual),
                width="stretch",
            )

        model_rate, model_cost = st.columns(2)
        with model_rate:
            st.plotly_chart(
                dashboard_charts.grafico_reparacoes_por_maquina_modelo(modelos),
                width="stretch",
            )
        with model_cost:
            st.plotly_chart(
                dashboard_charts.grafico_custo_por_maquina_modelo(modelos),
                width="stretch",
            )

        composition_col, recommendation_col = st.columns([1, 1.5])
        with composition_col:
            st.plotly_chart(
                dashboard_charts.grafico_composicao_custo_ams(composition),
                width="stretch",
            )
        with recommendation_col:
            st.plotly_chart(
                dashboard_charts.grafico_distribuicao_recomendacoes(base),
                width="stretch",
            )

        st.markdown("#### Impacto por modelo — denominador: máquinas do parque")
        modelos_view = modelos.copy()
        modelos_view["Percentual reparadas"] = (
            modelos_view["Percentual reparadas"] * 100
        )
        st.dataframe(
            modelos_view,
            hide_index=True,
            width="stretch",
            column_config={
                "Máquinas": st.column_config.NumberColumn(format="%.0f"),
                "Máquinas reparadas": st.column_config.NumberColumn(format="%.0f"),
                "Percentual reparadas": st.column_config.NumberColumn(format="%.1f%%"),
                "Reparações": st.column_config.NumberColumn(format="%.0f"),
                "Reparações por máquina": st.column_config.NumberColumn(format="%.2f"),
                "Custo": st.column_config.NumberColumn(format="R$ %.2f"),
                "Custo por máquina": st.column_config.NumberColumn(format="R$ %.2f"),
                "Idade média": st.column_config.NumberColumn(format="%.1f anos"),
            },
        )

    with tab_renovacao:
        max_machines = len(base)
        default_quantity = min(20, max_machines)
        quantidade = st.slider(
            "Quantidade de máquinas no cenário inicial",
            min_value=1,
            max_value=max_machines,
            value=default_quantity,
            help=(
                "Seleciona as máquinas com maior índice analítico. Os percentuais "
                "mostram concentração histórica no período, não redução garantida."
            ),
        )
        selected, scenario = renewal_analysis.cenario_renovacao(base, quantidade)
        pareto = renewal_analysis.dados_pareto(base)

        _render_small_cards(
            [
                (
                    "MÁQUINAS NO CENÁRIO",
                    _numero(scenario["maquinas"]),
                    "Maior prioridade no conjunto filtrado",
                ),
                (
                    "REPARAÇÕES CONCENTRADAS",
                    _percentual(scenario["percentual_reparacoes"]),
                    f'{_numero(scenario["reparacoes"])} reparações observadas',
                ),
                (
                    "CUSTO CONCENTRADO",
                    _percentual(scenario["percentual_custo"]),
                    _moeda(scenario["custo"]),
                ),
                (
                    "IDADE MÉDIA",
                    f'{_numero(scenario["idade_media"], 1)} anos',
                    "Máquinas selecionadas",
                ),
            ]
        )

        st.plotly_chart(
            dashboard_charts.grafico_pareto_custo_maquina(
                pareto,
                quantidade_selecionada=quantidade,
            ),
            width="stretch",
        )

        st.markdown("#### Máquinas sugeridas para avaliação comercial e técnica")
        st.dataframe(
            _analytical_table(selected),
            hide_index=True,
            width="stretch",
            column_config={
                "Idade atual": st.column_config.NumberColumn(format="%.1f anos"),
                "Reparações no período": st.column_config.NumberColumn(format="%.0f"),
                "Anos com reparação": st.column_config.NumberColumn(format="%.0f"),
                "Custo com impostos": st.column_config.NumberColumn(format="R$ %.2f"),
                "Índice de prioridade": st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
            },
        )

        texto = f'''
            registros localizados
        '''
        df_config.footer_df(
            _analytical_table(selected, None),
            f'''
            máquinas selecionadas para renovação
            que juntas somam {formatters.br_num(selected['Reparações no período'].sum(), 0)} reparações 
            com custo total de {formatters.br_num(selected['Custo com impostos'].sum(), 2)}
            '''
        )
        download_xlsx.download(df=_analytical_table(selected, None), key='renovacao')

        with st.expander("Como o índice de prioridade é calculado"):
            st.markdown(
                """
                O índice é relativo ao parque filtrado e combina quatro dimensões:
                **idade (25%)**, **frequência observada (30%)**, **custo observado
                (30%)** e **recorrência em anos diferentes (15%)**. Ele serve para
                ordenar a investigação comercial. Não é uma previsão de falha e não
                substitui avaliação de aplicação, produtividade ou condição física.
                """
            )

    with tab_qualidade:
        reconciliation, reconciliation_summary = renewal_analysis.reconciliar_fontes(
            df_com_periodo,
            df_ams,
            anos_selecionados,
        )
        _render_small_cards(
            [
                (
                    "PARQUE ATUAL",
                    _numero(reconciliation_summary["parque_atual"]),
                    "Registros presentes na fonte do parque",
                ),
                (
                    "PRESENTES NAS DUAS",
                    _numero(reconciliation_summary["presentes_duas"]),
                    "Conciliação por número de série",
                ),
                (
                    "SOMENTE NO PARQUE",
                    _numero(reconciliation_summary["somente_parque"]),
                    "Sem registro AMS na janela selecionada",
                ),
                (
                    "SOMENTE NO AMS",
                    _numero(reconciliation_summary["somente_ams"]),
                    "Possível diferença de atualização ou saída do parque",
                ),
            ]
        )
        st.caption(
            "Registros somente no parque não significam ausência de manutenção em toda "
            "a vida da máquina; significam apenas ausência no AMS dentro da janela selecionada."
        )
        status_options = reconciliation["Status de conciliação"].unique().tolist()
        selected_status = st.multiselect(
            "Status de conciliação",
            options=status_options,
            default=status_options,
        )
        reconciliation_view = reconciliation[
            reconciliation["Status de conciliação"].isin(selected_status)
        ]
        st.dataframe(reconciliation_view, hide_index=True, width="stretch")

    with tab_dados:
        display = base.copy()
        default_columns = [
            "Número de Série",
            "Razão Social",
            "Modelo",
            "Grupo",
            "Status da Ferramenta",
            "Data de compra",
            "Idade atual",
            "Reparações no período",
            "Custo com impostos",
            "Pago pelo cliente com impostos",
            "Valor absorvido com impostos",
            "Índice de prioridade",
            "Recomendação",
            "Motivo principal",
        ]
        default_columns = [column for column in default_columns if column in display]
        columns = sorted(display.columns)
        selected_columns = st.multiselect(
            "Exibir colunas",
            options=columns,
            default=default_columns,
            key="colunas_base_analitica",
        )
        if selected_columns:
            display = display[selected_columns]
        st.dataframe(display, hide_index=True, width="stretch")
        text = f'''
            registros localizados
        '''
        df_config.footer_df(display, text)

        export = write_xls.gerar_excel(base.copy())
        st.download_button(
            label="Baixar base analítica",
            data=export,
            file_name=(
                "analise_renovacao_"
                f"{pd.Timestamp.now().strftime('%Y_%m_%d_%H_%M_%S')}.xlsx"
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_base_analitica",
            type="primary",
        )
