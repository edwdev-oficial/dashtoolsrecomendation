# ========================================================
# region IMPORT
# ========================================================
import pandas as pd
import streamlit as st
from io import BytesIO

from dashtoolsrecomendation.assets.colunas import colunas
from dashtoolsrecomendation.services import (
    data_processing,
    get_pq_normalizado,
    get_pq_normalizado2,
    write_xls
)
from dashtoolsrecomendation.services.normalization import itens_nao_normalizados
from dashtoolsrecomendation.utils import (
    formatters, 
    df_config,
    download_xlsx

)
# endregion
# ========================================================


# ========================================================
# region FUNÇÕES UTILITÁRIAS
# ========================================================
@st.cache_data(show_spinner="Carregando arquivos...")

def carregar_excel(file_bytes, sheet_name=0):
    return pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name)


def convert_col_df_to_date(df, colunas=None):
    return data_processing.converter_datas(df, colunas or [])


def convert_col_df_to_number(df, colunas=None):
    return data_processing.converter_numeros(df, colunas or [])


def mover_coluna(df, nome_coluna, poiscao:int=0):
    return data_processing.mover_coluna(df, nome_coluna, poiscao)


def normalizar_itens(df):
    df = get_pq_normalizado2.get(df)
    return df, itens_nao_normalizados(df)


def sum_column(df, colum):
    return df[colum].sum()

# endregion
# ========================================================


# ========================================================
# region SHOW
# ========================================================
def show():

    # ========================================================
    # region SESSION STATE
    # ========================================================
    if 'df_pq' not in st.session_state:
        st.session_state.df_pq = pd.DataFrame()

    if 'df_ams' not in st.session_state:
        st.session_state.df_ams = pd.DataFrame()    

    if 'df_sap_group' not in st.session_state:
        st.session_state.df_sap_group = pd.DataFrame()    

    if 'df_sap_split' not in st.session_state:
        st.session_state.df_sap_split = pd.DataFrame()    
    # endregion
    # ========================================================

    # ========================================================
    # region READ FILES
    # ========================================================
    files = st.file_uploader(
        'Dados',
        'xlsx',
        accept_multiple_files=True,
        help='Carregue arquivos xlsx',
        key='dados_upload',
    )
    # endregion
    # ========================================================

    if files:


        # ========================================================
        # region DFs
        # ========================================================
        df_pq_cols_data = [
            'Data de Início do Contrato',
            'Data de Término do Contrato',
            'Último Reparo',
            'Data de compra',
            'Fim do período sem custo'
        ]

        df_pq = pd.DataFrame()
        df_ams = pd.DataFrame()



        dfs_pq = []
        dfs_ams = []
        dfs_sap_group = []
        dfs_sap_split = []

        for file in files:
            if file.name.lower().startswith('gestão de ferramentas'):
                df = carregar_excel(file.getvalue())
                if 'Razao Social' not in df.columns:
                    raz_id = file.name.split('-')[2:]
                    df.insert(0, 'Razao Social', raz_id[0] )
                    df.insert(0, 'Id', raz_id[1].replace('.xlsx', '') )
                dfs_pq.append(df)
            if file.name.startswith('ams'):
                df = carregar_excel(file.getvalue())
                if 'Número de série' in df.columns:
                    df.rename(columns={'Número de série': 'Número de Série'}, inplace=True)
                if 'ano_reparo' not in df.columns:
                    df['ano_reparo'] = int(file.name.replace('.xlsx', '').split('_')[3])
                dfs_ams.append(df)
            if file.name.startswith('Tools with repairs info'):
                df = carregar_excel(file.getvalue())
                dfs_sap_group.append(df)
            if file.name.startswith('G_GMRRPCOPA_AMS_KF2_W2'):
                df = carregar_excel(file.getvalue())
                dfs_sap_split.append(df)
        # endregion
        # ========================================================


        # ========================================================
        # region DF_PQ
        # ========================================================
        if len(dfs_pq):
            df_pq = data_processing.preparar_parque(
                dfs_pq,
                df_pq_cols_data,
                colunas,
            )

            st.session_state.df_pq_row = df_pq.copy()

            df_pq["_presente_parque"] = True
            df_pq["Descrição"] = df_pq["Descrição"].astype("string")
            

            df_pq = get_pq_normalizado.get(df_pq)

            df_pq["Descrição"] = df_pq["Descrição"].astype("string")
            df_pq["Duração do contrato"] = (
                df_pq["Duração do contrato"]
                .replace("-", 0)
                .replace("", 0)
                .fillna(0)
                .astype(int)
            )

            df_not_normalizer = df_pq[
                df_pq[['Tipo', 'Linha', 'Modelo']].isna().any(axis=1) |
                df_pq[['Tipo', 'Linha', 'Modelo']].eq('').any(axis=1)
            ]

            if df_not_normalizer.empty:
                df_pq['Mensalidade c/Imp'] = round(df_pq['Mensalidade'] / (1-0.0925), 2) 
                df_pq['Custo Reparo c/Imp'] = (
                    df_pq['Custo de Reparo'].fillna(0) * 1.4
                ) 

                # st.write('')
                # st.subheader('Parque de Máquinas', divider='red')
                # st.dataframe(
                #     df_pq,
                #     column_config=df_config.date_colums_config(df_pq_cols_data)
                # )
                # texto = f'''
                #     registros carregados,
                #     Custo Reparos: R$ {df_config.sum_column(df_pq, 'Custo Reparo c/Imp', True)}
                # '''
                # df_config.footer_df(df_pq, texto)
                
                download_xlsx.download(df_pq, 'dowload_pq')

                df_pq['Pago pelo Cliente'] = df_pq['Custo de Reparo']
                st.session_state.df_pq = df_pq

            else:
                st.warning('Existem equipamentos não normalizados log como adm para correção...')
                st.session_state.df_descricoes_not_normalizer = pd.DataFrame({
                    'Descrição': sorted(df_not_normalizer['Descrição'].dropna().unique())
                })
                st.stop()

            st.divider()

        # endregion
        # ========================================================


        # ========================================================
        # region DF_AMS
        # ========================================================
        if len(dfs_ams):

        
            df_ams = data_processing.preparar_ams(pd.concat(dfs_ams))
            # st.dataframe(df_ams)
            st.subheader('AMS Report Brazil', divider='red')

            df_ams.rename(columns={'Nome do Material': 'Descrição'}, inplace=True)
            df_ams, df_not_normalizer = normalizar_itens(df_ams)
            df_ams.rename(columns={'Descrição': 'Nome do Material'}, inplace=True)

            # ========================================================
            # region FILTER DF_AMS
            # ========================================================
            if 'series_ams' not in st.session_state:
                st.session_state.series_ams = []
            input_serie_ams, clear_filter_ams, _ = st.columns(
                [2, 1, 4],
                vertical_alignment="bottom",
            )

            with input_serie_ams:
                serie_ams = st.text_input(
                    'Número de Série',
                    key='filtro_numero_serie_ams',
                )
            with clear_filter_ams:
                if st.button(
                    'Limpar Filtro',
                    type='primary',
                    key='limpar_filtro_ams'
                ):
                    st.session_state.series_ams = []

            if serie_ams:
                st.session_state.series_ams.append(serie_ams)
                series_ams = st.session_state.series_ams
                df_ams = df_ams[
                    (df_ams['Número de Série'].isin(series_ams))
                    
                ]
            # endregion
            # ========================================================

            st.subheader('df_ams')
            st.dataframe(df_ams)
            st.session_state.df_ams = df_ams
            texto = f'''
                registros localizados em df_ams,
                {int(df_ams['# Notif.'].sum())} ordems e 
                {int(df_ams['# Reparos'].sum())} reparos,
                Custo reparo: R$ {df_config.sum_column(df_ams, 'Custo de Reparos', True)} 
                Pago pelo Cliente: R$ {df_config.sum_column(df_ams, 'Pagado pelo Cliente', True)}
                Economia: R$ {df_config.sum_column(df_ams, 'Economia', True)}
            '''
            df_config.footer_df(df_ams, texto)
            df_ams['Número de série'] = ''
            download_xlsx.download(df_ams, 'dowload_ams')
            df_ams.drop(columns=['Número de série'], inplace=True)

            if not df_not_normalizer.empty:
                st.session_state.df_descricoes_not_normalizer = df_not_normalizer
                st.warning('Existem equipamentos não normalizados no df_ams log como adm para correção...')
                st.session_state.df_descricoes_not_normalizer = pd.DataFrame({
                    'Descrição': sorted(df_not_normalizer['Descrição'].dropna().unique())
                })
                st.stop()
            st.session_state.df_ams = df_ams                


            st.divider()


            st.subheader('DF_AMS', divider='red')
            df_series_mais_de_um_id = (
                df_ams.groupby(["Número de Série", "Nome do Material"], as_index=False)
                .agg(
                    qtd_ids=("Id", "nunique"),
                    ids=("Id", lambda x: list(x.dropna().unique()))
                )
            )

            st.dataframe(df_series_mais_de_um_id)

            df_series_mais_de_um_id = df_series_mais_de_um_id[
                df_series_mais_de_um_id["qtd_ids"] > 1
            ]

            st.dataframe(df_series_mais_de_um_id)

            st.write(df_series_mais_de_um_id['Número de Série'].value_counts())
            st.subheader('', divider='red')


            # ========================================================
            # region DF_AMS_GROUP
            # ========================================================
            df_ams_group = data_processing.agrupar_ams(df_ams)

            st.subheader('df_ams_group')
            st.dataframe(df_ams_group)
            texto = f'''
                registros localizados em df_ams,
                {int(df_ams_group['# Notif.'].sum())} ordems e 
                {int(df_ams_group['# Reparos'].sum())} reparos,
                Custo reparo: R$ {df_config.sum_column(df_ams_group, 'Custo de Reparos', True)} 
                Pago pelo Cliente: R$ {df_config.sum_column(df_ams_group, 'Pagado pelo Cliente', True)}
                Economia: R$ {df_config.sum_column(df_ams_group, 'Economia', True)}
            '''
            df_config.footer_df(df_ams_group, texto)

            df_ams_group['Número de série'] = ''
            download_xlsx.download(df_ams_group, 'downlod_df_ams_group')
            df_ams_group.drop(columns=['Número de série'], inplace=True)
            st.divider()
            # endregion
            # ========================================================


            # ========================================================
            # region AMS_MERGE
            # ========================================================
            if df_pq.empty:
                df_ams_group["_presente_parque"] = False
                df_ams_group["_presente_ams"] = True
                st.session_state.df_pq = df_ams_group
                return

            df_pq["Número de série"] = data_processing.normalizar_numero_serie(
                df_pq["Número de série"]
            )
            df_ams_group["Número de Série"] = data_processing.normalizar_numero_serie(
                df_ams_group["Número de Série"]
            )
            df_pq["_presente_parque"] = True
            df_ams_group["_presente_ams"] = True

            df_merge = pd.merge(
                df_pq,
                df_ams_group,
                how="outer",
                left_on="Número de série",
                right_on="Número de Série",
                indicator="_origem_merge",
            )
            df_merge["_presente_parque"] = (
                df_merge["_presente_parque"].fillna(False).astype(bool)
            )
            df_merge["_presente_ams"] = (
                df_merge["_presente_ams"].fillna(False).astype(bool)
            )

            df_merge['Pago pelo Cliente'] = df_merge[['Custo de Reparo', 'Pagado pelo Cliente']].max(axis=1)
            df_merge['Custo de Reparos'] = df_merge['Pago pelo Cliente'] + df_merge['Economia']

            df_merge.drop(columns=[
                'Número do item',
                'Número da Requisição',
                'Referência Organizacional',
                'Tipo de Contrato',
                'Ferramenta de empréstimo permitida',
                'Cobertura de roubo',
                'Número do Equipamento',
                'Material',
            ], inplace=True)
            df_merge.rename(columns={
                'Id_x': 'Id',
                'Razao Social_x': 'Razão Social',
            }, inplace=True)


            # ========================================================
            # region FILTER DF_MERGE
            # ========================================================
            if 'series' not in st.session_state:
                st.session_state.series_merge = []
            col1, col2, _ = st.columns(
                [2, 1, 4],
                vertical_alignment="bottom",
            )

            with col1:
                serie_merge = st.text_input(
                    'Número de Série',
                    key='filtro_numero_serie',
                )
            with col2:
                if st.button(
                    'Limpar Filtro',
                    type='primary',
                    key='limpar_filtro'
                ):
                    st.session_state.series_merge = []

            if serie_merge:
                st.session_state.series_merge.append(serie_merge)
                series_merge = st.session_state.series_merge
                df_merge = df_merge[
                    (df_merge['Número de série'].isin(series_merge))
                    |
                    (df_merge['Número de Série'].isin(series_merge))
                    
                ]
            # endregion
            # ========================================================

            df_merge['Id'] = df_merge['Id'].fillna(df_merge['Id_y'])
            df_merge['Razão Social'] = df_merge['Razão Social'].fillna(df_merge['Razao Social_y'])
            df_merge['Descrição'] = df_merge['Descrição'].fillna(df_merge['Nome do Material'])
            df_merge['Grupo'] = df_merge['Grupo'].fillna('Não informado')
            df_merge['Status da Ferramenta'] = (
                df_merge['Status da Ferramenta']
                .replace('', pd.NA)
                .fillna('Não informado')
            )
            df_merge['Número de série'] = df_merge['Número de série'].fillna(df_merge['Número de Série'])
            df_merge['Data de compra_x'] = df_merge['Data de compra_x'].fillna(df_merge['Data de compra_y'])
            df_merge['Mensalidade c/Imp'] = df_merge['Mensalidade c/Imp'].fillna(0)
            df_merge['Quantidade de reparos'] = df_merge['Quantidade de reparos'].fillna(df_merge['# Reparos'])
            df_merge['Custo de Reparos'] = df_merge['Custo de Reparos'].fillna(df_merge['Custo de Reparo'])
            df_merge['Custo de Reparos'] = df_merge['Custo de Reparos'].fillna(0)
            df_merge['Economia'] = df_merge['Economia'].fillna(0)

            df_merge = get_pq_normalizado.get(df_merge)

            df_not_normalizer = df_merge[
                df_merge[['Tipo', 'Linha', 'Modelo']].isna().any(axis=1) |
                df_merge[['Tipo', 'Linha', 'Modelo']].eq('').any(axis=1)
            ]

            if df_not_normalizer.empty:
                pass
            else:
                st.warning('Existem equipamentos não normalizados log como adm para correção...')
                st.session_state.df_descricoes_not_normalizer = pd.DataFrame({
                    'Descrição': sorted(df_not_normalizer['Descrição'].dropna().unique())
                })
                st.stop()

            df_merge.rename(columns={
                'Data de compra_x': 'Data de compra'
            }, inplace=True)                

            df_merge['Número de Série'] = df_merge['Número de Série'].fillna(df_merge['Número de série'])
            df_merge['Custo de Reparo'] = df_merge['Custo de Reparo'].fillna(0)
            df_merge['Custo Reparo c/Imp'] = df_merge['Custo Reparo c/Imp'].fillna(0)
            df_merge['# Reparos'] = df_merge['# Reparos'].fillna(df_merge['Quantidade de reparos'])
            df_merge['# Notif.'] = (
                pd.to_numeric(df_merge['# Notif.'], errors='coerce')
                .fillna(0)
            )

            st.session_state.df_pq = df_merge

            st.dataframe(
                df_merge,
                width='stretch'
            )
            custo_reparo = formatters.br_num(sum_column(df_merge, 'Custo de Reparos'), 2, True)
            pago_clie = formatters.br_num(sum_column(df_merge, 'Pago pelo Cliente'), 2, True)
            economia = formatters.br_num(sum_column(df_merge, 'Economia'), 2, True)
            df_config.footer_df(df_merge, f'''
                registros após o merge, custo reparos {custo_reparo} valor pago pelo cliente {pago_clie} economia {economia}
            ''')
            download_xlsx.download(df_merge, 'dowload_merge')
            st.divider()
            # endregion
            # ========================================================


            anos_disponiveis = sorted(
                df_ams['ano_reparo']
                .dropna()
                .astype(int)
                .unique()
            )        
            anos_selecionados = st.multiselect(
                "Ano da reparação",
                options=anos_disponiveis,
                default=anos_disponiveis,
                key="filtro_ano_reparacao_geral",
            )

            df_por_ano = data_processing.preparacoes_por_ano(df_merge, df_ams, anos_selecionados)

            st.dataframe(df_por_ano)
            texto = f'''
                registros localizados em df_por_ano,
                {int(df_por_ano['# Notif.'].sum())} ordems e 
                {int(df_por_ano['Reparos_no_período'].sum())} reparos,
                Custo reparo: R$ {df_config.sum_column(df_por_ano, 'Custo_no_período', True)} 
                Pago pelo Cliente: R$ {df_config.sum_column(df_por_ano, 'Pago_no_período', True)}
                Economia: R$ {df_config.sum_column(df_por_ano, 'Economia_no_período', True)}
            '''
            df_config.footer_df(df_por_ano, texto)

            st.write(df_por_ano["Situação_AMS"].value_counts())            


        # endregion
        # ========================================================
    

        # ========================================================
        # region DF_SAP_GROUP
        # ========================================================
        if dfs_sap_group:
            df_sap_group = data_processing.preparar_sap_group(pd.concat(dfs_sap_group))
            st.subheader('Report Group SAP', divider='red')
            st.dataframe(df_sap_group)
        # endregion
        # ========================================================


        # ========================================================
        # region DF_SAP_SPLIT
        # ========================================================
        
        # endregion
        # ========================================================


    else:
    
        st.session_state.df_pq_row = pd.DataFrame()
        st.session_state.df_pq = pd.DataFrame()
        st.session_state.df_ams = pd.DataFrame()
        st.session_state.df_sap_group = pd.DataFrame()    
        st.session_state.df_sap_split = pd.DataFrame()            



# endregion
# ========================================================


