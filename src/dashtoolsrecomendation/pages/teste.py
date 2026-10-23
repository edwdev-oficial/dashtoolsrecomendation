import pandas as pd
import streamlit as st
from dataclasses import dataclass
import numpy as np
from typing import Any, cast
from datetime import date

from dashtoolsrecomendation import auth

from dashtoolsrecomendation.services import (
    dashboard_data,
    get_data_ids,
    renewal_analysis,
    data_processing,
    get_pq_normalizado2,
    normalization
)

from dashtoolsrecomendation.database.database import (
    get_database
)

from dashtoolsrecomendation.components import (
    create_filter
)

from dashtoolsrecomendation.utils import (
    download_xlsx,
    df_config,
    formatters,
)

from dashtoolsrecomendation.components import cards, dashboard_charts, dashboard_filters

def _percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if numeric.empty or numeric.nunique(dropna=False) <= 1:
        return pd.Series(0.0, index=series.index)
    return numeric.rank(method="average", pct=True).fillna(0)

def normalizar_itens(df):
    df = get_pq_normalizado2.get(df)
    return df, normalization.itens_nao_normalizados(df)

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
    # estudo_calculo_indice()

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
        keys = st.session_state.keys()
        keys_df = [k for k in keys if str(k).startswith('df')]
        st.write(keys_df)

        df_pq_row = st.session_state.get('df_pq_row').copy()
        df_pq_row = get_pq_normalizado2.get(df_pq_row)
        df_pq_row['Modelo-Serie'] = (
            df_pq_row['Modelo'] + ' - ' + df_pq_row['Número de série']
        )
        st.write('df_pq_row')
        st.dataframe(df_pq_row)
        df_config.footer_df(df_pq_row, 'registros')

        df_sap_split_row = st.session_state.get('df_sap_split_row')


        linha_cabecalho = df_sap_split_row.iloc[0]

        novos_nomes = {
            coluna_atual: novo_nome
            for coluna_atual, novo_nome in linha_cabecalho.items()
            if pd.notna(novo_nome) and str(novo_nome).strip() != ""
        }

        df_sap_split_row.rename(columns=novos_nomes, inplace=True)
        df_sap_split_row.rename(columns={'Tool Type': 'Descrição'}, inplace=True)
        df_sap_split_row = df_sap_split_row.iloc[2:].reset_index(drop=True)

        df_sap_split_row, df_sap_split_row_not_normalizer = normalizar_itens(df_sap_split_row)

        st.write('df_sap_split_row')
        st.dataframe(df_sap_split_row)
        df_config.footer_df(df_sap_split_row, 'registros')

        df_vazias = df_sap_split_row[df_sap_split_row['Tipo'].isna()].reset_index(drop=True)
        st.dataframe(df_vazias)

        unicos = df_vazias['Descrição'].unique()

        st.write(unicos)

        st.dataframe(df_sap_split_row_not_normalizer)
        st.session_state.df_descricoes_not_normalizer = pd.DataFrame({
            'Descrição': sorted(df_sap_split_row_not_normalizer['Descrição'].dropna().unique())
        })        

        # df_pq_row_not_in_split = compare_dfs(df_pq_row, df_sap_split, 'Modelo-Serie', 'Modelo-Serie')
        # df_pq_row_not_in_split = df_pq_row_not_in_split.reset_index(drop=True)
        # st.write('df_pq_row_not_in_split')
        # st.dataframe(df_pq_row_not_in_split)
        # df_config.footer_df(df_pq_row_not_in_split, 'registros')

        # df_sap_split_not_in_df_pq_row = compare_dfs(df_sap_split, df_pq_row, 'Modelo-Serie', 'Modelo-Serie')
        # df_sap_split_not_in_df_pq_row = df_sap_split_not_in_df_pq_row.reset_index(drop=True)
        # st.write('df_sap_split_not_in_df_pq_row')
        # st.dataframe(df_sap_split_not_in_df_pq_row)
        # df_config.footer_df(df_sap_split_not_in_df_pq_row, 'registros')

        # # st.dataframe(df_pq)
        # # df_pq.drop(columns=['Linha_x', 'Linha_y', 'Tipo_x', 'Tipo_y'], inplace=True)
        # # colunas_df_pq = sorted(list(df_pq.columns))
        # # st.write(colunas_df_pq)
        # # df_pq_not_in_split = compare_dfs(df_pq, df_sap_split, 'Modelo-Serie', 'Modelo-Serie')
        # # st.dataframe(df_pq_not_in_split)

        # # 49417
    # endregion
    # ========================================================
    estudo_das_bases()

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

    # ========================================================
    # region CHECK
    # ========================================================
    def check():
        # st.write(st.session_state)

        df_pq_row = st.session_state.df_pq.copy()

        status = create_filter.create_filter(df_pq_row, 'Status da Ferramenta', 'Status', True, 'multiselect')
        if status:
            df_pq_row = df_pq_row[df_pq_row['Status da Ferramenta'].isin(status)]

        linha = create_filter.create_filter(df_pq_row, 'Linha', 'Linha')
        if linha:
            df_pq_row = df_pq_row[df_pq_row['Linha'] == linha]
        modelo = create_filter.create_filter(df_pq_row, 'Modelo', 'Modelo')
        if modelo:
            df_pq_row = df_pq_row[df_pq_row['Modelo'] == modelo]

        grupo = create_filter.create_filter(df_pq_row, 'Grupo', 'Grupo', True, 'multiselect')
        if status:
            df_pq_row = df_pq_row[df_pq_row['Grupo'].isin(grupo)]            

        st.write(modelo)

        st.dataframe(df_pq_row)
        st.write(len(df_pq_row))

    # endregion
    # ========================================================
    # check()        

    # ========================================================
    # region DASHBOARD DATA
    # ========================================================
    
    # def get():
    #     db = get_database()
    #     collection = db['ccs_sorocaba_brasilia_ids']
    #     df = pd.DataFrame(collection.find().to_list())
    #     df.rename(columns={'codClie': 'Id'}, inplace=True)
    #     df['Id'] = df['Id'].astype(str).str.zfill(10)
    #     return df[['Id', 'UF', 'cliente']]    

    def analise_da_base_de_dados_do_dashboar():
        def prepare_df() -> pd.DataFrame:
            return dashboard_data.preparar_dashboard(
                cast(pd.DataFrame, st.session_state.df_pq),
                cast(pd.DataFrame, get_data_ids.get()),
            )

        def _anos_disponiveis(df_ams: pd.DataFrame) -> list[int]:

            if df_ams.empty or "ano_reparo" not in df_ams.columns:
                return []
            anos_numericos = cast(
                pd.Series,
                pd.to_numeric(df_ams["ano_reparo"], errors="coerce"),
            )
            anos = (
                anos_numericos
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            )
            return sorted(
                int(ano)
                for ano in anos
                if int(ano) >= renewal_analysis.ANALYSIS_START_YEAR
            )


        df_dashboard = prepare_df()

        status_dashboard = ['']
        values = sorted(list(df_dashboard['Status de conciliação'].unique()))
        status_dashboard.extend(values)
        status_option = st.multiselect('Status dashboard', status_dashboard)
        if status_option:
            df_dashboard = df_dashboard[df_dashboard['Status de conciliação'].isin(status_option)]

        st.write(f'df_dashboard com {len(df_dashboard)} registros')
        st.dataframe(df_dashboard)

        df_ams = st.session_state.get("df_ams", pd.DataFrame())

        # status_ams = ['']
        # values = sorted(list(df_ams['Status de conciliação'].unique()))
        # status_ams.extend(values)
        # status_option = st.multiselect('Staus dashboard', status_ams)
        # if status_option:
        #     df_dashboard = df_dashboard[df_dashboard['Status de conciliação'].isin(status_option)]

        st.write(f'df_ams {len(df_ams)} registros')
        st.dataframe(df_ams)

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
            .map(lambda repaired: "Sim" if bool(repaired) else "Não")
        )        

        st.write(f'df_com_periodo: {len(df_com_periodo)} registros')
        st.dataframe(df_com_periodo)


        df_filtrado, _ = dashboard_filters.aplicar_filtros(df_com_periodo)
        st.write(f'df_filtrado: {len(df_filtrado)} registros')
        st.dataframe(df_filtrado)


        if df_filtrado.empty:
            st.info("Nenhuma máquina foi encontrada para os filtros selecionados.")
            return
        download_xlsx.download(df_filtrado, 'baixar_df_iltrado', 'df_filtrado')

        st.divider()

        universo_ranking = dashboard_filters.aplicar_escopo_analitico(
            df_com_periodo,
            include_ams_only=bool(
                st.session_state.get(dashboard_filters.INCLUDE_AMS_KEY, False)
            ),
            include_stolen=bool(
                st.session_state.get(dashboard_filters.INCLUDE_STOLEN_KEY, False)
            ),
        )
        base_universo = renewal_analysis.preparar_base_maquinas(
            universo_ranking,
            df_ams,
            anos_selecionados,
            data_corte=data_corte,
            tax_factor=fator_impostos,
        )
        base = renewal_analysis.filtrar_base_maquinas(base_universo, df_filtrado)
        series = create_filter.create_filter(base, 'Número de série', 'Número de série', False, 'multiselect')
        if series:
            base = base[base['Número de série'].isin(series)]
        st.write(f'base: {len(base)} registros')
        st.dataframe(base)
        download_xlsx.download(base, 'baixar_base_tem_teste', 'dase')



    # endregion
    # ========================================================
    # analise_da_base_de_dados_do_dashboar()