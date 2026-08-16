import pandas as pd
import streamlit as st
from dataclasses import dataclass
import numpy as np
from typing import Any, cast

from dashtoolsrecomendation import auth

from dashtoolsrecomendation.utils import (
    download_xlsx,
    df_config,
    formatters,
)


def _percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if numeric.empty or numeric.nunique(dropna=False) <= 1:
        return pd.Series(0.0, index=series.index)
    return numeric.rank(method="average", pct=True).fillna(0)



def show():
    
    if not auth.has_role("adm"):
        st.error(
            "Você não tem permissão para acessar esta página.",
            icon=":material/block:",
        )
        st.stop()

    with st.container(border=True):
        st.subheader(":material/folder: Área de testes")
        st.subheader("Aqui você pode testar funcionalidades e ver resultados de cálculos.", divider='red')


    # ========================================================
    # region ESTUDO DO CÁLCULO DO ÍNDICE DE PRIORIDADE
    # ========================================================
    def estudo_calculo_indice():
    # def _percentile_score(series: pd.Series) -> pd.Series:
        # numeric = pd.to_numeric(series, errors="coerce").fillna(0)
        # if numeric.empty or numeric.nunique(dropna=False) <= 1:
        #     return pd.Series(0.0, index=series.index)
        # return numeric.rank(method="average", pct=True).fillna(0)
        columns = list(st.session_state.base.columns)
        columns.sort(key=str.lower)

        st.write(columns)


        df = st.session_state.base[[
            "Modelo",
            "Número de Série",
            "Data de compra",
            "Idade atual",
            "Reparações no período",
            "Anos observados",
            "Reparações por ano observado",
            "Anos com reparação",
            "Recorrência",
            "Custo líquido",
            "Custo com impostos",
        ]]

        result = df.copy()

        result["Percentil idade"] = _percentile_score(
            result["Idade atual"]
        )

        result["Percentil frequência"] = _percentile_score(
            result["Reparações por ano observado"]
        )

        result["Percentil custo"] = _percentile_score(
            result["Custo com impostos"]
        )

        result["Percentil recorrência"] = _percentile_score(
            result["Recorrência"]
        )

        # result = result[result['Número de Série'] == '116879']

        st.dataframe(result)
        download_xlsx.download(result, 'bar', 'calculo_percentils')

        serie_idade = result["Idade atual"].to_frame()

        st.write(serie_idade)
        download_xlsx.download(serie_idade, 'foo', 'serie_idades')
    # endregion
    # ========================================================

    # ========================================================
    # region ESTUDO DAS BASES
    # ========================================================
    def estudo_das_bases():

        # ========================================================
        # region FUNÇÕES UTILITÁRIAS
        # ========================================================
        def compare_dfs(df1, df2, key1, key2):
                    merged_df = pd.merge(df1, df2, left_on=key1, right_on=key2, how='outer', indicator=True)
                    merged_df = merged_df[merged_df['_merge'] == 'left_only']
                    return merged_df        
        # endregion
        # ========================================================

        # ========================================================
        # region SIDEBAR
        # ========================================================
        file_base_filtrada = st.sidebar.file_uploader(
            "Carregar base filtrada",
            type=["xlsx"],
            key="file_base_filtrada",
        )
        ocult_roubados = st.sidebar.toggle("Ocultar máquinas roubadas", value=True)
        apenas_ferramentas = st.sidebar.toggle("Mostrar apenas ferramentas", value=True)
        reparadas = st.sidebar.toggle("Mostrar apenas máquinas reparadas", value=True)
        serie = st.sidebar.text_input("Número de série")
        # endregion
        # ========================================================

        # ========================================================
        # region DFs
        # ========================================================
        df_pq = st.session_state.get('df_pq')
        df_ams = st.session_state.get('df_ams')
        df_sap_group = st.session_state.get('df_sap_group')
        df_sap_split = st.session_state.get('df_sap_split')        
        # endregion
        # ========================================================

        # ========================================================
        # region BASE FILTRADA
        # ========================================================
        if file_base_filtrada is not None:
            st.subheader("Base filtrada", divider='red')
            df_base_filtrada = pd.read_excel(file_base_filtrada)
            df_base_filtrada['Número de série'] = df_base_filtrada['Número de série'].astype(str).str.strip()
            df_base_filtrada['Modelo-Serie'] = df_base_filtrada['Modelo'] + ' - ' + df_base_filtrada['Número de série']
            # df_base_filtrada['Modelo-Série'] = df_base_filtrada['Modelo'] + ' - ' + df_base_filtrada['Número de série']
            if reparadas:
                df_base_filtrada = df_base_filtrada[df_base_filtrada['Reparos_no_período'] > 0]
            if apenas_ferramentas:
                df_base_filtrada = df_base_filtrada[df_base_filtrada['Tipo'] == 'Ferramenta']
            if serie:
                df_base_filtrada = df_base_filtrada[df_base_filtrada['Número de série'] == serie]
            st.session_state['df_base_filtrada'] = df_base_filtrada
            st.dataframe(df_base_filtrada)
            custo_reparo_total = df_base_filtrada['Custo_no_período'].sum()
            pago_cliente_total = df_base_filtrada['Pago_no_período'].sum()
            economia_total = df_base_filtrada['Economia_no_período'].sum()
            text = f'''
                maquinas - 
                Custo de reparo total: R$ {formatters.br_num(custo_reparo_total, 2,  True)}  
                pago pelo : R$ {formatters.br_num(pago_cliente_total, 2,  True)} 
                absorvido: R$ {formatters.br_num(economia_total, 2,  True)}
            '''  
            df_config.footer_df(df_base_filtrada, text)
        # endregion
        # ========================================================

        # ========================================================
        # region REPORT PQ
        # ========================================================
        if df_pq is not None:
            st.subheader('Report PQ', divider='red')
            df_pq['Modelo-Serie'] = df_pq['Modelo'] + ' - ' + df_pq['Número de série']
            if ocult_roubados:
                df_pq = df_pq[df_pq['Status da Ferramenta'] != 'Roubado']
            if apenas_ferramentas:
                df_pq = df_pq[df_pq['Tipo'] == 'Ferramenta']
            if reparadas:
                df_pq = df_pq[df_pq['Quantidade de reparos'] > 0]
            if serie:
                df_pq = df_pq[df_pq['Número de Série'] == serie]
            st.dataframe(df_pq)
            total_custo_pq = formatters.br_num(df_pq['Custo de Reparo'].sum(), 2,  True)
            df_config.footer_df(df_pq, f"máquinas - Custo cliente: R$ {total_custo_pq}")
            # qtd_series_pq = len(list(df_pq['Número de Série'].unique()))
            # st.write(f"Quantidade de séries distintas: {qtd_series_pq}")
            # df_repetidos = df_pq[df_pq.duplicated(subset=['Número de Série'], keep=False)]
            # st.dataframe(df_repetidos)
            # df_unicos = df_pq[['Descrição','Número de Série']].drop_duplicates()
            # st.write(len(df_unicos))
        # endregion
        # ========================================================

        # ========================================================
        # region REPORT AMS
        # ========================================================
        if df_ams is not None:
            st.subheader('Report AMS', divider='red')
            df_ams['Modelo-Serie'] = df_ams['Modelo'] + ' - ' + df_ams['Número de Série']
            if serie:
                df_ams = df_ams[df_ams['Número de Série'] == serie]
            st.dataframe(df_ams)
            qtd_maquinas_ams = len(df_ams[['Modelo-Serie']].drop_duplicates())
            total_custo_ams = formatters.br_num(df_ams['Custo de Reparos'].sum(), 2,  True)
            total_custo_cliente_ams = formatters.br_num(df_ams['Pagado pelo Cliente'].sum(), 2,  True)
            total_custo_absorvido_ams = formatters.br_num(df_ams['Economia'].sum(), 2,  True)
            df_config.footer_df(df_ams, f"registros - {qtd_maquinas_ams} máquinas - Custo de Reparos: R$ {total_custo_ams} - Custo cliente: R$ {total_custo_cliente_ams} - Custo absorvido: R$ {total_custo_absorvido_ams} ")
        # endregion
        # ========================================================

        # ========================================================
        # region REPORT GROUP SAP
        # ========================================================
        if df_sap_group is not None:
            st.subheader('Report Group SAP', divider='red')
            if reparadas:
                df_sap_group = df_sap_group[df_sap_group['Total number of repairs'] > 0]
            if serie:
                df_sap_group = df_sap_group[df_sap_group['Serial Number'] == serie]
            df_sap_group['Modelo-Serie'] = df_sap_group['Modelo'] + ' - ' + df_sap_group['Serial Number']        
            st.dataframe(df_sap_group)
            # qtd_maquinas_sap_group = len(df_sap_group[['Modelo', 'Serial Number']].drop_duplicates())
            qtd_maquinas_sap_group = len(df_sap_group[['Modelo-Serie']].drop_duplicates())
            total_custo_cliente_sap_group = formatters.br_num(df_sap_group['Total billed amount'].sum(), 2,  True)
            df_config.footer_df(df_sap_group, f"registros - {qtd_maquinas_sap_group} máquinas - Custo cliente: R$ {total_custo_cliente_sap_group}")
        # endregion
        # ========================================================

        # ========================================================
        # region REPORT SPLIT SAP
        # ========================================================
        if df_sap_split is not None:
            st.subheader('Report Split SAP', divider='red')
            if serie:
                df_sap_split = df_sap_split[df_sap_split['(n) Serial Number'] == serie]
            df_sap_split['Notif. Completion Date'] = pd.to_datetime(
                df_sap_split['Notif. Completion Date'],
                format='%d.%m.%Y',
                errors='coerce'
            )
            df_sap_split['Modelo-Serie'] = df_sap_split['Modelo'] + ' - ' + df_sap_split['(n) Serial Number']
            st.dataframe(df_sap_split)
            qtd_maquinas_sap_split = len(df_sap_split[['Tool Type','Modelo', '(n) Serial Number']].drop_duplicates())
            total_custo_sap_split = formatters.br_num(df_sap_split['Covered by Customer'].sum() + df_sap_split['Covered by Hilti'].sum(), 2, True)
            total_custo_cliente_sap_split = formatters.br_num(df_sap_split['Covered by Customer'].sum(), 2,  True)
            total_custo_absorvido_sap_split = formatters.br_num(df_sap_split['Covered by Hilti'].sum(), 2,  True)
            df_config.footer_df(df_sap_split, f"registros - {qtd_maquinas_sap_split} máquinas - Custo de reparos {total_custo_sap_split} - Custo cliente: R$ {total_custo_cliente_sap_split} - Custo absorvido: R$ {total_custo_absorvido_sap_split}")
        # endregion
        # ========================================================
        

        
        if df_sap_group is not None and df_sap_split is not None:
            st.subheader('Máquinas do SAP Group que não estão no SAP Split', divider='red')
            df_sap_gruoup_not_in_split = compare_dfs(df_sap_group, df_sap_split, 'Modelo-Serie', 'Modelo-Serie')
            st.dataframe(df_sap_gruoup_not_in_split)
            df_sap_gruoup_not_in_split = df_sap_group[
                ~df_sap_group['Modelo-Serie'].isin(df_sap_split['Modelo-Serie'])
            ].reset_index(drop=True)
            st.dataframe(df_sap_gruoup_not_in_split)

        if file_base_filtrada is not None:
            st.subheader('Máquinas da Base Filtrada que não estão no SAP Split', divider='red')
            df_base_filtrada_not_in_split = compare_dfs(df_base_filtrada, df_sap_split, 'Modelo-Serie', 'Modelo-Serie')
            st.dataframe(df_base_filtrada_not_in_split)

            st.subheader('Máquinas do PQ que não estão na Base Filtrada', divider='red')
            # st.write('Modelo-Serie' in df_pq.columns)
            df_pq_not_in_filtrada = compare_dfs(df_pq, df_base_filtrada, 'Modelo-Serie', 'Modelo-Serie')
            st.dataframe(df_pq_not_in_filtrada)

        st.subheader('Máquinas do PQ que não estão no SAP Split', divider='red')
        df_pq_not_in_split = compare_dfs(df_pq, df_sap_split, 'Modelo-Serie', 'Modelo-Serie')
        st.dataframe(df_pq_not_in_split)

        # 49417
    # endregion
    # ========================================================
    # estudo_das_bases()

    # ========================================================
    # region PERCENTIL SCORE
    # ========================================================
    def indice_recomendacao_motivo():

        @dataclass(frozen=True)
        class RenewalWeights:
            """Pesos do índice relativo de prioridade de renovação."""

            idade: float = 0.25
            frequencia: float = 0.30
            custo: float = 0.30
            recorrencia: float = 0.15

            def validate(self) -> None:
                total = self.idade + self.frequencia + self.custo + self.recorrencia
                if not np.isclose(total, 1.0):
                    raise ValueError("Os pesos do índice de prioridade devem somar 1,0.")        

        weights = RenewalWeights()

        def _as_float(value: object) -> float:
            return float(cast(Any, value))        

        def _is_frota_ativa(row: pd.Series) -> bool:
            grupo = str(row.get("Grupo", "")).strip().casefold()
            status = str(row.get("Status da Ferramenta", "")).strip().casefold()
            return grupo == "frota" and status == "ativo"        

        def _classificar_prioridade(row: pd.Series) -> str:
            if _is_frota_ativa(row):
                return "Manter"

            reparos = _as_float(row["Reparações no período"])
            score = _as_float(row["Índice de prioridade"])
            idade = _as_float(row["Idade atual"])

            if reparos <= 0:
                return "Monitorar" if idade >= 8 else "Manter"
            if score >= 70 and reparos >= 2:
                return "Troca prioritária"
            if score >= 50:
                return "Planejar renovação"
            if score >= 30 or reparos >= 2:
                return "Monitorar"
            return "Manter" 

        def _motivo_principal(row: pd.Series) -> str:
            if _is_frota_ativa(row):
                return "Gestão de Frotas"

            alta_freq = row["Percentil frequência"] >= 0.75
            alto_custo = row["Percentil custo"] >= 0.75
            idade_alta = row["Idade atual"] >= 8
            recorrente = row["Recorrência"] >= 0.67

            if alta_freq and alto_custo:
                return "Alta frequência e alto custo"
            if recorrente:
                return "Reparações recorrentes"
            if alto_custo:
                return "Alto custo no período"
            if alta_freq:
                return "Alta frequência no período"
            if idade_alta:
                return "Idade elevada"
            if row.get("Recomendação") == "Troca prioritária":
                return "Prioridade combinada dos fatores analisados"
            return "Baixo impacto recente"               

        def _column(frame: pd.DataFrame, name: str) -> pd.Series:
            """Retorna uma coluna com o tipo escalar esperado pelo serviço."""
            return cast(pd.Series, frame[name])

        # ========================================================
        # region FORMA FEITA ANTERIORMENTE
        # ========================================================
        # def _percentile_score(series: pd.Series) -> pd.Series:
        #     numeric = cast(
        #         pd.Series, pd.to_numeric(series, errors="coerce")
        #     ).fillna(0)
        #     if numeric.empty or numeric.nunique(dropna=False) <= 1:
        #         return pd.Series(0.0, index=series.index)
        #     return numeric.rank(method="average", pct=True).fillna(0)
        # endregion
        # ========================================================

        def _percentile_score(series: pd.Series) -> pd.Series:
            numeric = cast(
                pd.Series,
                pd.to_numeric(series, errors="coerce")
            ).fillna(0)

            if numeric.empty or numeric.nunique(dropna=False) <= 1:
                return pd.Series(0.0, index=series.index)

            rank = numeric.rank(method="average")
            n = len(numeric)

            return ((rank - 1) / (n - 1)).fillna(0)        


        result = pd.DataFrame({
            "Série": [
                900101, 900102, 900103, 900104, 900105,
                900106, 900107, 900108, 900109, 900110,
                900111, 900112, 900113, 900114, 900115
            ],
            "Modelo": [
                "TE-500", "TE-500", "TE-600", "TE-2000", "TE-500",
                "TE-800", "TE-500", "TE-1000", "TE-500", "TE-500",
                "TE-500", "TE-2000", "TE-500", "TE-500", "TE-600"
            ],
            "Grupo": [
                'Comprado', 'Comprado', 'Comprado', 'Comprado',
                'Comprado', 'Comprado', 'Comprado', 'Comprado',
                'Comprado', 'Comprado', 'Comprado', 'Comprado',
                'Comprado', 'Comprado', 'Comprado'
            ],
            "Status da Ferramenta": [
                'Ativo', 'Ativo', 'Ativo', 'Ativo', 'Ativo', 'Ativo',
                'Ativo', 'Ativo', 'Ativo', 'Ativo', 'Ativo', 'Ativo',
                'Ativo', 'Ativo', 'Ativo'
            ],
            "Idade atual": [
                9.8, 9.4, 7.2, 6.1, 8.5,
                7.0, 6.3, 5.5, 4.2, 3.8,
                2.0, 1.1, 9.0, 6.8, 4.8
            ],
            "Reparações no período": [
                5, 4, 5, 4, 2,
                3, 3, 2, 4, 3,
                2, 1, 0, 1, 0
            ],
            "Anos obs.": [
                3, 3, 3, 3, 3,
                3, 3, 3, 3, 3,
                2, 1, 3, 3, 3
            ],
            "Anos c/ reparo": [
                3, 3, 2, 3, 2,
                2, 3, 2, 2, 3,
                2, 1, 0, 1, 0
            ],
            "Custo com impostos": [
                7200.00, 6100.00, 8600.00, 9500.00, 4800.00,
                5400.00, 3900.00, 3200.00, 4500.00, 3000.00,
                2500.00, 1800.00, 0.00, 1400.00, 0.00
            ]
        })

        result['Reparações por ano observado'] = result['Reparações no período'] / result['Anos obs.']
        result['Recorrência'] = result['Anos c/ reparo'] / result['Anos obs.']

        result['Percentil idade'] = _percentile_score(
            _column(result, 'Idade atual')
        )
        result["Percentil frequência"] = _percentile_score(
            _column(result, "Reparações por ano observado")
        )
        result["Percentil custo"] = _percentile_score(
            _column(result, "Custo com impostos")
        )
        result["Percentil recorrência"] = _percentile_score(
            _column(result, "Recorrência")
        )        
        result["Índice de prioridade"] = 100 * (
            weights.idade * result["Percentil idade"]
            + weights.frequencia * result["Percentil frequência"]
            + weights.custo * result["Percentil custo"]
            + weights.recorrencia * result["Percentil recorrência"]
        )
        result = result.sort_values(
            ["Índice de prioridade", "Custo com impostos", "Reparações no período"],
            ascending=False,
        ).reset_index(drop=True)
        result["Índice de prioridade"] = result["Índice de prioridade"].round(1)
        result["Recomendação"] = result.apply(_classificar_prioridade, axis=1)
        result["Motivo principal"] = result.apply(_motivo_principal, axis=1)
        st.dataframe(result)

    # endregion
    # ========================================================
    # indice_recomendacao_motivo()
