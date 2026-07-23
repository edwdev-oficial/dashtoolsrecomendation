import pandas as pd
import streamlit as st

from dashtoolsrecomendation.services import (
    get_pq_normalizado
)
from dashtoolsrecomendation.utils import (
    df_config,
    formatters,
    download_xlsx
)

def show():

    if ('df_pq_row' not in st.session_state or st.session_state.df_pq_row.empty) and ('df_ams' not in st.session_state or st.session_state.df_ams.empty):
        st.warning('Carregue os arquivos do Parque de Máquinas HOL ou os Arquivos do AMS Report Brazil')
        return

    # ========================================================
    # region DF_PQ
    # ========================================================

    if 'df_pq_row' in st.session_state and not st.session_state.df_pq_row.empty:

        st.subheader('Parque de Máquina HOL', divider='red')

        df_pq = st.session_state.df_pq_row.copy()
        # df_pq['Custo de Reparo c/imp'] = df_pq['Custo de Reparo'] * 1.4
        df_config.insert_coluna_apos(df_pq, 'Custo de Reparo', 'Custo de Reparo c/imp', df_pq['Custo de Reparo'] * 1.4)

        df_pq = get_pq_normalizado.get(df_pq)

        # ========================================================
        # region FILTER DF_PQ
        # ========================================================
        if 'series_pq' not in st.session_state:
            st.session_state.series_pq = []
        if 'filtro_numero_serie_pq' not in st.session_state:
            st.session_state.filtro_numero_serie_pq = ''

        def limpar_filtro_pq():
            st.session_state.series_pq = []
            st.session_state.filtro_numero_serie_pq = ""

        input_serie_pq, clear_filter_pq, _ = st.columns(
            [2, 1, 4],
            vertical_alignment="bottom",
        )

        with clear_filter_pq:
            st.button(
                'Limpar Filtro',
                type='primary',
                key='limpar_filtro_pq',
                on_click=limpar_filtro_pq
            )

        with input_serie_pq:
            serie_pq = st.text_input(
                'Número de Série',
                key='filtro_numero_serie_pq',
            )

        if serie_pq and serie_pq not in st.session_state.series_pq:
            st.session_state.series_pq.append(serie_pq)

        series_pq = st.session_state.series_pq
        if series_pq:
            df_pq = df_pq[
                df_pq['Número de série'].isin(series_pq)
            ].reset_index(drop=True)
        # endregion
        # ========================================================

        st.dataframe(df_pq)
        mensal_gf = f'mensalidade G.F. c/Imp {formatters.br_num(df_pq['Mensalidade'].sum() / 0.9075, 2, True)}' if 'Mensalidade' in df_pq.columns else ''
        texto = f'''
            registros
            {mensal_gf}
            custo de reparos {formatters.br_num(df_pq['Custo de Reparo c/imp'].sum(), 2, True)}
        '''
        button_download_pq, footter_pq = st.columns(
            [1,2],
            vertical_alignment='top'
        )
        with button_download_pq:
            download_xlsx.download(df_pq, 'button_doload_pq', 'pq_maquinas')
        with footter_pq:
            df_config.footer_df(df_pq, texto)
    # endregion
    # ========================================================

    # ========================================================
    # region DF_AMS
    # ========================================================
    if 'df_ams' in st.session_state and not st.session_state.df_ams.empty:
        st.subheader('Relatório AMS Report Brazil', divider='red')
        df_ams = st.session_state.df_ams.copy()

        # ========================================================
        # region FILTER DF_AMS
        # ========================================================
        if 'series_ams' not in st.session_state:
            st.session_state.series_ams = []
        if 'filtro_numero_serie_ams' not in st.session_state:
            st.session_state.filtro_numero_serie_ams = ''

        def limpar_filtro_ams():
            st.session_state.series_ams = []
            st.session_state.filtro_numero_serie_ams = ''

        input_serie_ams, clear_filter_ams, _ = st.columns(
            [2,1,4],
            vertical_alignment='bottom'
        )

        with input_serie_ams:
            serie_ams = st.text_input(
                'Numero de Série',
                key='filtro_numero_serie_ams'
            )

        with clear_filter_ams:
            st.button(
                'Limpar Filtro',
                type='primary',
                key='limpar_filtro_ams',
                on_click=limpar_filtro_ams
            )

        if serie_ams and serie_ams not in st.session_state.series_ams:
            st.session_state.series_ams.append(serie_ams)

        series_ams = st.session_state.series_ams
        if series_ams:
            df_ams = df_ams[
                df_ams['Número de Série'].isin(series_ams)
            ].reset_index(drop=True)




        # endregion
        # ========================================================
        st.dataframe(df_ams)
        button_download_ams, footter_ams = st.columns(
            [1,2],
            vertical_alignment='top'
        )
        texto = f'''
            registros, 
            custo de reparação {formatters.br_num(df_ams['Custo de Reparos'].sum() * 1.4, 2, True)}
            pago pelo cliente {formatters.br_num(df_ams['Pagado pelo Cliente'].sum()* 1.4, 2, True)}
            valor absorvido {formatters.br_num(df_ams['Economia'].sum()* 1.4, 2, True)}
        '''
        with button_download_ams:
            download_xlsx.download(df_ams, 'button_dowload_ams', 'ams_report_brazil')

        with footter_ams:
            df_config.footer_df(df_ams, texto)

    # endregion
    # ========================================================