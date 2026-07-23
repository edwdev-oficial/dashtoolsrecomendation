import pandas as pd
from io import BytesIO


SERIAL_COLUMN = 'Número de série'
SERIAL_ALIASES = (SERIAL_COLUMN, 'Número de Série')


def normalizar_coluna_numero_serie(df):
    """Consolida as variações do nome da coluna sem criar rótulos duplicados."""
    result = df.copy()
    aliases = [column for column in SERIAL_ALIASES if column in result.columns]
    if not aliases:
        return result

    position = min(result.columns.get_loc(column) for column in aliases)
    numero_serie = result[aliases[0]].replace(r'^\s*$', pd.NA, regex=True)
    for column in aliases[1:]:
        alternativa = result[column].replace(r'^\s*$', pd.NA, regex=True)
        numero_serie = numero_serie.fillna(alternativa)

    result = result.drop(columns=aliases)
    result.insert(position, SERIAL_COLUMN, numero_serie)
    return result

def formatar_colunas_data(
    df,
    worksheet,
    workbook,
    colunas_data,
    largura=13,
    formato_data_excel="dd/mm/yyyy",
    cor_linha='#D9D9D9'
):
    formato_data = workbook.add_format({
        "num_format": formato_data_excel,
        "align": "center",
        "valign": "vcenter",
        "bottom": 5,
        "bottom_color": cor_linha,
        "font_name": "Nunito",
        "font_size": 10,
    })

    for coluna in colunas_data:
        if coluna not in df.columns:
            continue

        # Garante que a coluna esteja como datetime
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce")

        idx_coluna = df.columns.get_loc(coluna)

        # Define largura e formato da coluna
        # worksheet.set_column(idx_coluna, idx_coluna, largura, formato_data)
        worksheet.set_column(idx_coluna, idx_coluna, largura)

        # Reescreve as células com write_datetime para o formato pegar corretamente
        for row_num, valor in enumerate(df[coluna], start=1):
            if pd.notna(valor):
                worksheet.write_datetime(
                    row_num,
                    idx_coluna,
                    valor.to_pydatetime(),
                    formato_data
                )
            else:
                worksheet.write_blank(
                    row_num,
                    idx_coluna,
                    None,
                    formato_data
                )


def gerar_excel(df_recebido):

    df = normalizar_coluna_numero_serie(df_recebido)

    output = BytesIO()

    linha_tenue = '#D9D9D9'
    linha_forte = ''

    colunas_data = [
        'Data de Início do Contrato',
        'Data de Término do Contrato',
        'Último Reparo',
        'Data de compra',
        'Fim do período sem custo'
    ]

    if SERIAL_COLUMN in df.columns:
        df[SERIAL_COLUMN] = pd.to_numeric(
            df[SERIAL_COLUMN],
            errors='coerce'
        ).astype("Int64")

    with pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        datetime_format="dd/mm/yyyy",
        date_format="dd/mm/yyyy"        
    ) as writer:

        df.to_excel(
            writer,
            sheet_name="Relatório",
            index=False
        )

        worksheet = writer.sheets["Relatório"]
        worksheet.hide_gridlines(2)
        worksheet.set_default_row(30)
        worksheet.set_zoom(80)
        workbook = writer.book


        formato_data = workbook.add_format({
            "num_format": "dd/mm/yyyy",
            "align": "center",
            "font_name": "Nunito",
            "font_size": 10,
        })

        formato_numero_int = workbook.add_format({
            "num_format": "0",
            "align": "center",
            "font_name": "Nunito",
            "font_size": 10,
            "valign": "vcenter",
        })

        formato_geral = workbook.add_format({
            "valign": "vcenter",
            "font_name": "Nunito",
            "font_size": 10,
        })

        formato_primeira_linha = workbook.add_format({
            "bold": True,
            "align": "left",
            "valign": "vcenter",
            "bottom": 5,
            "bottom_color": "#808080",
            "font_name": "Nunito",
            "font_size": 10,
        })

        formato_primeira_linha_centralizado = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "bottom": 5,
            "bottom_color": "#808080",
            "font_name": "Nunito",
            "font_size": 10,
        })

        formato_linha = workbook.add_format({
            "valign": "vcenter",
            "bottom": 5,
            "bottom_color": linha_tenue,
            "font_name": "Nunito",
            "font_size": 10,
        })

        formato_linha_centralizado = workbook.add_format({
            "align": "center",
            "valign": "vcenter",
            "bottom": 5,
            "bottom_color": linha_tenue,
            "font_name": "Nunito",
            "font_size": 10,
        })        

        ultima_linha = len(df)
        ultima_coluna = min(26, len(df.columns) - 1)  # AA = índice 26

        colunas_centralizadas = [
            'Id',
            'Número do item',
            'Status da Ferramenta',
            'Número de série',
            'Tipo de Contrato',
            'Ferramenta de empréstimo permitida',
            'Cobertura de roubo',
            'Quantidade de reparos',
            'Garantia',
            'Número do Equipamento',
            'Geração',
            'Status',
            'Duração do contrato'
        ]        

        for row_num in range(1, ultima_linha + 1):
            for col_num in range(0, ultima_coluna + 1):
                valor = df.iloc[row_num - 1, col_num]
                nome_coluna = df.columns[col_num]

                if nome_coluna in colunas_centralizadas:
                    formato = formato_linha_centralizado
                else:
                    formato = formato_linha

                if pd.isna(valor):
                    worksheet.write_blank(row_num, col_num, None, formato)
                else:
                    worksheet.write(row_num, col_num, valor, formato)

        worksheet.set_column(0, len(df.columns) - 1, None, formato_geral)
        worksheet.set_column("K:K", 12, formato_data)
        worksheet.set_column("G:G", 10, formato_numero_int)


        formatar_colunas_data(
            df=df,
            worksheet=worksheet,
            workbook=workbook,
            colunas_data=colunas_data,
            largura=13,
            cor_linha=linha_tenue
        )

        colunas_centralizadas.extend(['Mensalidade c/Imp'])

        for col in range(len(df.columns)):
            valor = df.columns[col]

            if valor in colunas_centralizadas:
                formato = formato_primeira_linha_centralizado
            else:
                formato = formato_primeira_linha

            worksheet.write(0, col, valor, formato)        

        worksheet.autofit()       


    output.seek(0)
    return output

