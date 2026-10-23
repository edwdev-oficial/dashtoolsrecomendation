from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable, Sequence

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

# -----------------------------------------------------------------------------
# Configuracao geral
# -----------------------------------------------------------------------------
PAGE_W, PAGE_H = A4
MARGIN_X = 15 * mm
MARGIN_TOP = 13.5 * mm
GRID_GUTTER = 3.5 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

# Paleta oficial Hilti Fundamentals (julho de 2026).
RED = colors.HexColor("#D2051E")
STEEL = colors.HexColor("#524F53")
HEAVY_CONCRETE = colors.HexColor("#887F6E")
WARM_CONCRETE = colors.HexColor("#D7CEBD")
BURGUNDY = colors.HexColor("#671C3E")
BLACK_20 = colors.HexColor("#CCCCCC")

# Tons neutros derivados das cores de apoio, usados em fundos e filetes.
DARK = STEEL
MID = HEAVY_CONCRETE
GRID = colors.HexColor("#D5D4D5")
LIGHT = colors.HexColor("#EEEDEE")
WARM = WARM_CONCRETE
WARM_BORDER = HEAVY_CONCRETE
MAGENTA = BURGUNDY
BEIGE = WARM_CONCRETE
WHITE = colors.white

HERE = Path(__file__).resolve().parent
ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO_PATH = ASSETS / "logoHilti.png"
OUTPUT_FILENAME = "Manual_Metodologia_Indice_Prioridade_Renovacao_v1.pdf"
DEFAULT_OUTPUT = Path.home() / "Downloads" / OUTPUT_FILENAME


# -----------------------------------------------------------------------------
# Fontes
# -----------------------------------------------------------------------------
def _first_existing(paths: Iterable[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def register_fonts() -> tuple[str, str]:
    """Registra a família Hilti; Arial é usado apenas se os assets não existirem."""
    regular = _first_existing(
        [
            ASSETS / "HiltiRoman.otf",
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path("/Library/Fonts/Arial.ttf"),
        ]
    )
    bold = _first_existing(
        [
            ASSETS / "HiltiBold.otf",
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
            Path("/Library/Fonts/Arial Bold.ttf"),
        ]
    )

    if regular and bold:
        pdfmetrics.registerFont(TTFont("HiltiRoman", str(regular)))
        pdfmetrics.registerFont(TTFont("HiltiBold", str(bold)))
        return "HiltiRoman", "HiltiBold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = register_fonts()


# -----------------------------------------------------------------------------
# Dados e calculos
# -----------------------------------------------------------------------------
BASE_DATA = [
    (900101, "TE-500", 9.8, 5, 3, 3, 7200),
    (900102, "TE-500", 9.4, 4, 3, 3, 6100),
    (900103, "TE-600", 7.2, 5, 3, 2, 8600),
    (900104, "TE-2000", 6.1, 4, 3, 3, 9500),
    (900105, "TE-500", 8.5, 2, 3, 2, 4800),
    (900106, "TE-800", 7.0, 3, 3, 2, 5400),
    (900107, "TE-500", 6.3, 3, 3, 3, 3900),
    (900108, "TE-1000", 5.5, 2, 3, 2, 3200),
    (900109, "TE-500", 4.2, 4, 3, 2, 4500),
    (900110, "TE-500", 3.8, 3, 3, 3, 3000),
    (900111, "TE-500", 2.0, 2, 2, 2, 2500),
    (900112, "TE-2000", 1.1, 1, 1, 1, 1800),
    (900113, "TE-500", 9.0, 0, 3, 0, 0),
    (900114, "TE-500", 6.8, 1, 3, 1, 1400),
    (900115, "TE-600", 4.8, 0, 3, 0, 0),
]

WEIGHTS = {
    "p_idade": 0.25,
    "p_frequencia": 0.30,
    "p_custo": 0.30,
    "p_recorrencia": 0.15,
}


def percentile_score(series: pd.Series) -> pd.Series:
    """Posicao percentilica normalizada: (rank_medio - 1) / (n - 1)."""
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if numeric.empty or numeric.nunique(dropna=False) <= 1:
        return pd.Series(0.0, index=series.index)
    rank = numeric.rank(method="average", ascending=True)
    n = len(numeric)
    return (rank - 1) / (n - 1)


def recommendation(row: pd.Series) -> str:
    # Regras aplicadas no Manual v2.
    idx = float(row["indice"])
    repairs = int(row["reparos"])
    age = float(row["idade"])

    if repairs == 0:
        return "Monitorar" if age >= 8 else "Manter"
    if idx >= 70 and repairs >= 2:
        return "Troca prioritária"
    if idx >= 50:
        return "Planejar renovação"
    # No exemplo do manual, qualquer máquina com ocorrência observada
    # permanece pelo menos na fila de monitoramento.
    return "Monitorar"


def build_dataframe() -> pd.DataFrame:
    df = pd.DataFrame(
        BASE_DATA,
        columns=["serie", "modelo", "idade", "reparos", "anos_obs", "anos_reparo", "custo"],
    )
    df["frequencia"] = df["reparos"] / df["anos_obs"]
    df["recorrencia"] = df["anos_reparo"] / df["anos_obs"]
    df["p_idade"] = percentile_score(df["idade"])
    df["p_frequencia"] = percentile_score(df["frequencia"])
    df["p_custo"] = percentile_score(df["custo"])
    df["p_recorrencia"] = percentile_score(df["recorrencia"])
    df["indice"] = 100 * sum(df[k] * w for k, w in WEIGHTS.items())
    df["recomendacao"] = df.apply(recommendation, axis=1)
    return df


# -----------------------------------------------------------------------------
# Helpers de desenho
# -----------------------------------------------------------------------------
def y_from_top(top: float) -> float:
    return PAGE_H - top


def br_number(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def br_money(value: float) -> str:
    return "R$ " + f"{value:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def draw_logo(c: canvas.Canvas, cover: bool = False) -> None:
    if not LOGO_PATH.exists():
        raise FileNotFoundError(
            f"Logo não encontrada em {LOGO_PATH}. Crie a pasta assets e coloque hilti_logo.png nela."
        )
    # A capa segue a largura A4 indicada no sistema geral. Nas páginas internas,
    # o tamanho compacto segue o padrão visual dos exemplos de manuais técnicos.
    width = 60 * mm if cover else 22.5 * mm
    height = width * 36 / 154
    c.drawImage(
        str(LOGO_PATH),
        MARGIN_X,
        PAGE_H - MARGIN_TOP - height,
        width=width,
        height=height,
        mask="auto",
    )


def draw_technical_cover_background(c: canvas.Canvas) -> None:
    """Fundo 20% preto com superfície dinâmica branca e corte de 30°."""
    slant_x = 58 * mm
    slant_y = slant_x / 0.577350269  # tan(30°)

    c.saveState()
    c.setFillColor(BLACK_20)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    surface = c.beginPath()
    surface.moveTo(0, 0)
    surface.lineTo(PAGE_W, 0)
    surface.lineTo(PAGE_W, PAGE_H - slant_y)
    surface.lineTo(PAGE_W - slant_x, PAGE_H)
    surface.lineTo(0, PAGE_H)
    surface.close()
    c.setFillColor(WHITE)
    c.drawPath(surface, fill=1, stroke=0)
    c.restoreState()


def draw_paragraph(
    c: canvas.Canvas,
    text: str,
    x: float,
    top: float,
    width: float,
    *,
    font: str = FONT,
    size: float = 9,
    leading: float | None = None,
    color=DARK,
    align=TA_LEFT,
    bold: bool = False,
) -> float:
    leading = leading or size * 1.2
    style = ParagraphStyle(
        "p",
        fontName=FONT_BOLD if bold else font,
        fontSize=size,
        leading=leading,
        textColor=color,
        alignment=align,
        spaceAfter=0,
        spaceBefore=0,
    )
    p = Paragraph(text, style)
    _, h = p.wrap(width, PAGE_H)
    p.drawOn(c, x, PAGE_H - top - h)
    return h


def draw_bullets(c: canvas.Canvas, items: Sequence[str], x: float, top: float, width: float, size=8.2, leading=10.5) -> float:
    current = top
    for item in items:
        h = draw_paragraph(
            c,
            f"• &nbsp;&nbsp;{item}",
            x + GRID_GUTTER,
            current,
            width - GRID_GUTTER,
            size=size,
            leading=leading,
        )
        current += h
    return current - top


def draw_section_header(c: canvas.Canvas, section: str, title: str, title_size=21.5, title_top=84) -> None:
    c.setFillColor(RED)
    c.setFont(FONT, 8.7)
    c.drawString(MARGIN_X, y_from_top(76), section)
    draw_paragraph(c, title, MARGIN_X, title_top, CONTENT_W, size=title_size, leading=title_size, bold=True, color=DARK)
    c.setStrokeColor(STEEL)
    c.setLineWidth(0.5)
    c.line(MARGIN_X, y_from_top(132), PAGE_W - MARGIN_X, y_from_top(132))


def draw_header_footer(c: canvas.Canvas, page_no: int) -> None:
    draw_logo(c)
    c.setFillColor(MID)
    c.setFont(FONT, 7.2)
    c.drawRightString(PAGE_W - MARGIN_X, y_from_top(45.5), "MANUAL METODOLÓGICO")

    c.setStrokeColor(GRID)
    c.setLineWidth(0.4)
    c.line(MARGIN_X, y_from_top(780), PAGE_W - MARGIN_X, y_from_top(780))
    c.setFillColor(MID)
    c.setFont(FONT, 7)
    c.drawString(MARGIN_X, y_from_top(794.5), "Índice de Prioridade de Renovação")
    c.drawCentredString(PAGE_W / 2, y_from_top(794.5), "Uso orientativo")
    c.drawRightString(PAGE_W - MARGIN_X, y_from_top(794.5), f"Página {page_no}")


def draw_info_box(
    c: canvas.Canvas,
    x: float,
    top: float,
    w: float,
    h: float,
    title: str,
    body: str,
    red_fill: bool = False,
    *,
    body_size: float = 8.2,
    body_leading: float = 10.3,
) -> None:
    y = PAGE_H - top - h
    c.setFillColor(RED if red_fill else colors.white)
    c.setStrokeColor(RED)
    c.setLineWidth(0.7)
    c.rect(x, y, w, h, fill=1 if red_fill else 0, stroke=1)
    text_color = WHITE if red_fill else DARK
    draw_paragraph(c, title, x + 8, top + 8, w - 16, size=9, leading=10.5, bold=True, color=text_color)
    draw_paragraph(c, body, x + 8, top + 24, w - 16, size=body_size, leading=body_leading, color=text_color)


def draw_formula_box(c: canvas.Canvas, text: str, top: float, height: float = 52, subtitle: str | None = None) -> None:
    x, w = 49, 497
    y = PAGE_H - top - height
    c.setFillColor(WARM)
    c.setStrokeColor(WARM_BORDER)
    c.setLineWidth(0.7)
    c.rect(x, y, w, height, fill=1, stroke=1)
    draw_paragraph(c, text, x + 14, top + 13, w - 28, size=10.5, leading=12, bold=True, color=DARK, align=TA_CENTER)
    if subtitle:
        draw_paragraph(c, subtitle, x + 14, top + 31, w - 28, size=8.0, leading=9.5, color=MID, align=TA_CENTER)


def make_table(
    c: canvas.Canvas,
    data: list[list[object]],
    x: float,
    top: float,
    col_widths: list[float],
    row_heights: float | list[float],
    *,
    font_size=7.2,
    header=True,
    aligns: list[str] | None = None,
    header_font_size=7.6,
    alternating=True,
    header_bg=DARK,
) -> float:
    t = Table(data, colWidths=col_widths, rowHeights=row_heights)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, GRID),
    ]
    if header:
        style.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, 0), header_font_size),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ]
        )
    if alternating:
        start = 1 if header else 0
        for r in range(start, len(data)):
            if (r - start) % 2 == 1:
                style.append(("BACKGROUND", (0, r), (-1, r), LIGHT))
    if aligns:
        for ci, al in enumerate(aligns):
            style.append(("ALIGN", (ci, 0), (ci, -1), al))
    t.setStyle(TableStyle(style))
    _, h = t.wrapOn(c, sum(col_widths), PAGE_H)
    t.drawOn(c, x, PAGE_H - top - h)
    return h


# -----------------------------------------------------------------------------
# Paginas
# -----------------------------------------------------------------------------
def page_1(c: canvas.Canvas) -> None:
    draw_technical_cover_background(c)
    draw_logo(c, cover=True)
    c.setFillColor(RED)
    c.setFont(FONT, 9)
    c.drawString(MARGIN_X, y_from_top(137), "MANUAL DE METODOLOGIA")

    draw_paragraph(
        c,
        "Índice de Prioridade<br/>de Renovação",
        MARGIN_X,
        150,
        360,
        size=30,
        leading=30,
        bold=True,
        color=DARK,
    )
    c.setStrokeColor(STEEL)
    c.setLineWidth(0.5)
    c.line(MARGIN_X, y_from_top(222), PAGE_W - MARGIN_X, y_from_top(222))

    draw_paragraph(
        c,
        "Como idade, frequência, custo e recorrência são combinados em uma fila transparente de avaliação técnica<br/>e comercial.",
        MARGIN_X,
        248,
        CONTENT_W,
        size=16,
        leading=16,
        color=DARK,
        bold=True,
    )

    x, top, w, h = MARGIN_X, 320, CONTENT_W, 52
    c.setFillColor(LIGHT)
    c.setStrokeColor(RED)
    c.rect(x, PAGE_H - top - h, w, h, fill=1, stroke=1)
    draw_paragraph(c, "Objetivo do manual", x + 8, top + 8, w - 16, size=9, bold=True, color=DARK)
    draw_paragraph(
        c,
        "Explicar, em linguagem não técnica, de onde vêm os índices apresentados nos estudos de renovação e como interpretar<br/>corretamente o resultado.",
        x + 8,
        top + 24,
        w - 16,
        size=8.8,
        leading=10.5,
        color=DARK,
    )

    rows = [
        ("Aplicação", "Estudos de renovação de parques de ferramentas"),
        ("Exemplo didático", "15 máquinas com dados inteiramente fictícios"),
        ("Princípio", "Priorizar investigação; não prever falha futura"),
    ]
    y = 462
    for label, val in rows:
        c.setFillColor(MID)
        c.setFont(FONT_BOLD, 8)
        c.drawString(MARGIN_X, y_from_top(y + 8), label)
        c.setFont(FONT, 8)
        c.drawString(145, y_from_top(y + 8), val)
        c.setStrokeColor(GRID)
        c.line(MARGIN_X, y_from_top(y + 27), PAGE_W - MARGIN_X, y_from_top(y + 27))
        y += 32
    c.showPage()


def page_2(c: canvas.Canvas) -> None:
    draw_header_footer(c, 2)
    draw_section_header(c, "1. VISÃO GERAL", "O que o índice mede")
    draw_paragraph(
        c,
        "O Índice de Prioridade de Renovação organiza as máquinas da maior para a menor necessidade de avaliação. Ele combina<br/>quatro sinais observáveis e transforma medidas diferentes em uma única escala comparável.",
        MARGIN_X,
        145,
        CONTENT_W,
        size=9,
        leading=11.5,
    )

    x, top, h = MARGIN_X, 176, 69
    widths = [127.8, 127.8, 127.8, 127.8]
    cards = [
        ("25%", "Idade", "Exposição ao envelhecimento e à<br/>obsolescência relativa."),
        ("30%", "Frequência", "Quantidade de reparações ajustada<br/>pelo tempo observado."),
        ("30%", "Custo", "Custo direto acumulado das<br/>reparações no período."),
        ("15%", "Recorrência", "Persistência das ocorrências em anos<br/>diferentes."),
    ]
    curx = x
    for i, (pct, label, desc) in enumerate(cards):
        c.setFillColor(LIGHT)
        c.setStrokeColor(GRID)
        c.rect(curx, PAGE_H - top - h, widths[i], h, fill=1, stroke=1)
        draw_paragraph(c, pct, curx + 6, top + 12, widths[i] - 12, size=13, bold=True, color=RED)
        draw_paragraph(c, label, curx + 6, top + 30, widths[i] - 12, size=8.5, bold=True, color=DARK)
        draw_paragraph(c, desc, curx + 6, top + 44, widths[i] - 12, size=6.7, leading=8, color=MID)
        curx += widths[i]

    draw_paragraph(c, "A leitura correta", MARGIN_X, 258, 250, size=15, bold=True, color=DARK)
    draw_bullets(
        c,
        [
            "Quanto maior o índice, maior a prioridade relativa dentro do universo analítico.",
            "O índice não representa probabilidade de falha ou vida útil restante.",
            "A classificação pode ser confirmada em campo, considerando aplicação, condição física, disponibilidade de reserva e criticidade operacional.",
            "O índice é relativo ao universo analítico. Filtros visuais apenas recortam a exibição e não alteram as posições.",
        ],
        MARGIN_X,
        275,
        505,
        size=8.2,
        leading=10.2,
    )
    draw_info_box(
        c,
        MARGIN_X,
        336,
        CONTENT_W,
        55,
        "Mensagem central",
        "A metodologia evita decisões baseadas somente na idade. Uma máquina entra no topo do ranking quando apresenta uma combinação desfavorável de idade, frequência, custo e recorrência.",
        red_fill=True,
        body_size=7.5,
        body_leading=9.0,
    )

    draw_paragraph(c, "Fluxo resumido", MARGIN_X, 409, 250, size=15, bold=True)
    steps = [
        ("Consolidar cada máquina", "Reunir em uma única linha a idade, as reparações, os anos observados, os anos com reparo e o custo."),
        ("Calcular frequência e recorrência", "Ajustar as ocorrências pelo tempo em que a máquina esteve efetivamente presente na janela analisada."),
        ("Converter em posições percentílicas", "Comparar cada máquina com as demais do mesmo parque em cada uma das quatro dimensões."),
        ("Aplicar pesos e classificar", "Somar os pontos ponderados e transformar o resultado em uma recomendação de ação."),
    ]
    top = 429
    for n, (ttl, desc) in enumerate(steps, start=1):
        c.setFillColor(LIGHT)
        c.setStrokeColor(LIGHT)
        c.rect(MARGIN_X, PAGE_H - top - 31, CONTENT_W, 31, fill=1, stroke=0)
        c.setFillColor(RED)
        c.rect(MARGIN_X, PAGE_H - top - 31, 29, 31, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 11)
        c.drawCentredString(MARGIN_X + 14.5, PAGE_H - top - 20, str(n))
        draw_paragraph(c, ttl, MARGIN_X + 36, top + 5, CONTENT_W - 61, size=8.2, bold=True)
        draw_paragraph(c, desc, MARGIN_X + 36, top + 17, CONTENT_W - 61, size=6.8, leading=8.2, color=MID)
        top += 43
    c.showPage()


def page_3(c: canvas.Canvas) -> None:
    draw_header_footer(c, 3)
    draw_section_header(c, "2. DADOS E INDICADORES", "Quais informações entram no cálculo")
    draw_paragraph(
        c,
        "A metodologia trabalha com poucos dados, desde que estejam associados de forma confiável ao número de série de cada máquina.",
        MARGIN_X,
        145,
        500,
        size=9.2,
        leading=11.5,
    )

    data = [
        ["Informação", "Significado", "Uso no índice"],
        ["Número de série", "Identificador individual da máquina.", "Consolida todos os registros do mesmo\nativo."],
        ["Idade (anos)", "Tempo desde a aquisição ou entrada em operação.", "Componente Idade - peso de 25%."],
        ["Reparações no período", "Total de reparações observadas na janela escolhida.", "Base para a frequência."],
        ["Anos observados", "Anos da janela em que a máquina já existia.", "Evita penalizar de forma indevida máquinas\nrecentes."],
        ["Anos com reparação", "Quantidade de anos diferentes com ao menos uma ocorrência.", "Base para a recorrência."],
        ["Custo observado", "Soma dos custos diretos de reparação no período.", "Componente Custo - peso de 30%."],
    ]
    # Substitui strings multiline por Paragraphs para manter o layout.
    pdata: list[list[object]] = []
    cell_style = ParagraphStyle("cell", fontName=FONT, fontSize=7.2, leading=8.2, textColor=DARK)
    head_style = ParagraphStyle("head", fontName=FONT_BOLD, fontSize=7.6, leading=8.5, textColor=WHITE, alignment=TA_CENTER)
    for ri, row in enumerate(data):
        pdata.append([Paragraph(str(v).replace("\n", "<br/>"), head_style if ri == 0 else cell_style) for v in row])
    make_table(c, pdata, MARGIN_X, 197, [123, 245, 143], [13, 21, 13, 13, 24, 13, 13], header=True, alternating=True)

    draw_paragraph(c, "Indicadores derivados", MARGIN_X, 317, 250, size=14, bold=True)
    draw_formula_box(c, "Frequência observada = Reparações no período / Anos observados", 342, 48,
                     "Exemplo: 5 reparações em 3 anos observados = 1,67 reparação por ano observado.")
    draw_formula_box(c, "Recorrência = Anos com reparação / Anos observados", 404, 48,
                     "Exemplo: ocorrência em 2 dos 3 anos observados = 0,67, ou 67%.")

    draw_info_box(
        c,
        MARGIN_X,
        468,
        CONTENT_W,
        58,
        "Por que ajustar pelo tempo?",
        "Duas máquinas podem ter o mesmo número de reparações, mas exposições diferentes. Duas reparações em um ano indicam<br/>intensidade maior do que duas reparações distribuídas em três anos.",
        red_fill=False,
    )
    draw_paragraph(c, "Janela de análise", MARGIN_X, 535, 250, size=14, bold=True)
    draw_paragraph(
        c,
        "O período deve ser definido antes do cálculo. No exemplo deste manual, considera-se uma janela de até três anos. Máquinas<br/>adquiridas depois do início da janela possuem menos anos observados, o que é refletido no cálculo de frequência e recorrência.",
        MARGIN_X,
        567,
        CONTENT_W,
        size=8.6,
        leading=10.5,
    )
    c.showPage()


def page_4(c: canvas.Canvas) -> None:
    draw_header_footer(c, 4)
    draw_section_header(c, "3. POSIÇÃO RELATIVA", "Como os valores viram posições percentílicas", title_size=21)
    draw_paragraph(
        c,
        "Como idade, frequência, custo e recorrência possuem unidades diferentes, os valores não são somados diretamente. Cada<br/>dimensão é primeiro convertida em uma posição percentílica normalizada dentro do parque analisado.",
        MARGIN_X,
        145,
        CONTENT_W,
        size=9.1,
        leading=11.5,
    )
    draw_formula_box(
        c,
        "Posição percentílica = (posição média no ranking - 1) / (quantidade de máquinas - 1)",
        195,
        52,
        "O ranking é crescente: valores maiores recebem posições percentílicas maiores.",
    )
    draw_paragraph(c, "Exemplo de empate", MARGIN_X, 255, 250, size=15, bold=True)
    draw_paragraph(
        c,
        "Na base fictícia, as séries 900101 e 900103 possuem a mesma frequência: 1,67 reparação por ano observado. Elas ocupam<br/>conjuntamente as posições 14 e 15 entre 15 máquinas.",
        MARGIN_X,
        283,
        CONTENT_W,
        size=8.7,
        leading=10.5,
    )
    data = [
        ["Etapa", "Cálculo", "Resultado"],
        ["Posições ocupadas", "14 e 15", "-"],
        ["Posição média", "(14 + 15) / 2", "14,5"],
        ["Posição percentílica de frequência", "(14,5 - 1) / (15 - 1)", "0,9643"],
        ["Leitura", "Posição percentílica x 100", "96,43%"],
    ]
    make_table(c, data, MARGIN_X, 326, [135, 280, 96], 13, font_size=7.5, header_font_size=7.6, aligns=["LEFT", "LEFT", "CENTER"])
    draw_paragraph(c, "O que a posição percentílica significa", MARGIN_X, 407, 350, size=14, bold=True)
    draw_bullets(
        c,
        [
            "Posição 0,00: menor valor da dimensão, quando não há empate na base.",
            "Posição 1,00: maior valor da dimensão, quando não há empate no topo.",
            "Posição 0,80: posição próxima aos 20% mais altos do conjunto.",
            "Empates recebem a posição média do grupo, para que ativos iguais tenham a mesma pontuação.",
            "A posição percentílica mostra posição relativa, não diferença absoluta. Um pequeno aumento no custo pode alterar a posição sem representar uma mudança proporcional no impacto econômico.",
        ],
        MARGIN_X,
        433,
        505,
        size=7.9,
        leading=9.7,
    )
    draw_info_box(
        c,
        MARGIN_X,
        498,
        CONTENT_W,
        59,
        "Importante",
        "O índice deve ser comparado dentro do mesmo estudo e do mesmo universo analítico. Mudanças de universo, período histórico ou data de corte podem alterar o ranking.",
        red_fill=True,
    )
    c.showPage()


def page_5(c: canvas.Canvas) -> None:
    draw_header_footer(c, 5)
    draw_section_header(c, "4. PESOS E RECOMENDAÇÃO", "Como o índice final é formado")
    draw_formula_box(
        c,
        "Índice = 100 x [(25% x P idade) + (30% x P frequência) + (30% x P custo) + (15% x P recorrência)]",
        161,
        52,
    )
    draw_paragraph(
        c,
        "Cada posição percentílica varia entre 0 e 1. Pela fórmula (r - 1) / (n - 1), a primeira posição vale 0 e a última vale 1 quando não há<br/>empate nos extremos. A multiplicação por 100 converte a soma ponderada para uma escala de 0 a 100. Os pesos refletem a<br/>intenção do estudo: custo e frequência têm maior influência, enquanto idade e recorrência complementam a decisão.",
        MARGIN_X,
        229,
        CONTENT_W,
        size=8.6,
        leading=11,
    )

    x, top, h = MARGIN_X, 286, 78
    widths = [127.8] * 4
    cards = [
        ("0-29,9", "Baixa prioridade", "Manter ou monitorar conforme idade<br/>e histórico."),
        ("30-49,9", "Monitorar", "Acompanhar e revisar evolução das<br/>ocorrências."),
        ("50-69,9", "Planejar renovação", "Avaliar troca programada e<br/>orçamento."),
        ("70-100", "Troca prioritária", "Desde que existam ao menos duas<br/>reparações."),
    ]
    curx = x
    for pct, label, desc in cards:
        c.setFillColor(LIGHT)
        c.setStrokeColor(GRID)
        c.rect(curx, PAGE_H - top - h, widths[0], h, fill=1, stroke=1)
        c.setStrokeColor(RED)
        c.setLineWidth(1)
        c.line(curx, PAGE_H - top, curx + widths[0], PAGE_H - top)
        draw_paragraph(c, pct, curx + 6, top + 12, widths[0] - 12, size=15, bold=True, color=RED)
        draw_paragraph(c, label, curx + 6, top + 35, widths[0] - 12, size=8.5, bold=True)
        draw_paragraph(c, desc, curx + 6, top + 51, widths[0] - 12, size=6.9, leading=8.2, color=MID)
        curx += widths[0]

    draw_paragraph(c, "Regras complementares", MARGIN_X, 382, 300, size=14, bold=True)
    draw_bullets(
        c,
        [
            "Máquina sem reparação e com menos de 8 anos: Manter.",
            "Máquina sem reparação e com 8 anos ou mais: Monitorar, pois a idade recomenda acompanhamento, mas não troca automática.",
            "Índice igual ou superior a 70 exige ao menos duas reparações para receber a classificação Troca prioritária.",
            "Índice entre 50 e 69,9: Planejar renovação.",
            "Índice entre 30 e 49,9, ou pelo menos duas reparações: Monitorar.",
        ],
        MARGIN_X,
        410,
        CONTENT_W,
        size=8.1,
        leading=10,
    )
    draw_info_box(
        c,
        MARGIN_X,
        470,
        CONTENT_W,
        58,
        "Governança da decisão",
        "As faixas transformam a pontuação em uma fila de ação. A autorização de troca deve considerar também a inspeção técnica, a aplicação e o impacto operacional da indisponibilidade.",
    )
    c.showPage()


def page_6(c: canvas.Canvas, df: pd.DataFrame) -> None:
    draw_header_footer(c, 6)
    draw_section_header(c, "5. EXEMPLO DIDÁTICO", "Base fictícia com 15 máquinas")
    draw_paragraph(
        c,
        "Todos os números, custos e séries desta seção são fictícios e servem apenas para demonstrar a metodologia. O exemplo<br/>considera uma janela máxima de três anos.",
        MARGIN_X,
        145,
        CONTENT_W,
        size=8.8,
        leading=11,
    )
    rows: list[list[object]] = [["Série", "Modelo", "Idade (anos)", "Reparações", "Anos obs.", "Anos c/ reparo", "Custo c/ impostos"]]
    for _, r in df.iterrows():
        rows.append(
            [
                str(int(r.serie)),
                r.modelo,
                br_number(r.idade, 1),
                str(int(r.reparos)),
                str(int(r.anos_obs)),
                str(int(r.anos_reparo)),
                br_money(r.custo),
            ]
        )
    make_table(c, rows, MARGIN_X, 198, [65, 92, 50, 52, 70, 88, 94], 12, font_size=6.7, header_font_size=7.6,
               aligns=["CENTER", "CENTER", "CENTER", "CENTER", "CENTER", "CENTER", "RIGHT"])
    draw_paragraph(c, "Leituras preliminares", MARGIN_X, 413, 300, size=14, bold=True)
    draw_bullets(
        c,
        [
            "A série 900101 combina idade elevada, alta frequência, recorrência anual e custo relevante.",
            "A série 900104 é mais nova que várias TE-500, porém possui o maior custo observado da base.",
            "A série 900113 tem 9 anos, mas nenhuma reparação observada; a idade isolada não a coloca em troca prioritária.",
            "As séries 900111 e 900112 têm menos anos observados, pois representam ativos mais recentes.",
        ],
        MARGIN_X,
        441,
        CONTENT_W,
        size=8,
        leading=10,
    )
    c.showPage()


def page_7(c: canvas.Canvas, df: pd.DataFrame) -> None:
    draw_header_footer(c, 7)
    draw_section_header(c, "6. RESULTADO DO EXEMPLO", "Ranking e recomendação")
    draw_paragraph(
        c,
        "A tabela abaixo mostra os principais indicadores derivados e a classificação final. Os índices foram calculados em relação às 15<br/>máquinas do exemplo, usando a posição percentílica normalizada.",
        MARGIN_X,
        145,
        CONTENT_W,
        size=8.8,
        leading=11,
    )
    ranked = df.sort_values("indice", ascending=False).reset_index(drop=True)
    rows: list[list[object]] = [["Pos.", "Série", "Freq./ano", "Recorr.", "Custo c/ impostos", "Índice", "Recomendação"]]
    for i, r in ranked.iterrows():
        rows.append(
            [
                str(i + 1),
                str(int(r.serie)),
                br_number(r.frequencia, 2),
                f"{round(r.recorrencia * 100):d}%",
                br_money(r.custo),
                br_number(r.indice, 1),
                r.recomendacao,
            ]
        )
    pdata: list[list[object]] = []
    head = ParagraphStyle("h7", fontName=FONT_BOLD, fontSize=7.6, leading=8, textColor=WHITE, alignment=TA_CENTER)
    head_left = ParagraphStyle(
        "h7-left",
        parent=head,
        alignment=TA_LEFT,
    )
    head_right = ParagraphStyle(
        "h7-right",
        parent=head,
        alignment=TA_RIGHT,
    )
    cell = ParagraphStyle("c7", fontName=FONT, fontSize=6.6, leading=7.5, textColor=DARK)
    cell_center = ParagraphStyle(
        "c7-center",
        parent=cell,
        alignment=TA_CENTER,
    )
    cell_right = ParagraphStyle(
        "c7-right",
        parent=cell,
        alignment=TA_RIGHT,
    )
    cell_bold_red = ParagraphStyle(
        "r7",
        fontName=FONT_BOLD,
        fontSize=6.6,
        leading=7.5,
        textColor=RED,
        alignment=TA_CENTER,
    )
    for ri, row in enumerate(rows):
        rr = []
        for ci, v in enumerate(row):
            if ri == 0:
                if ci == 4:
                    rr.append(Paragraph(str(v), head_right))
                elif ci == 6:
                    rr.append(Paragraph(str(v), head_left))
                else:
                    rr.append(Paragraph(str(v), head))
            elif ci == 5 and ri <= 4:
                rr.append(Paragraph(str(v), cell_bold_red))
            elif ci == 4:
                rr.append(Paragraph(str(v), cell_right))
            elif ci in {0, 1, 2, 3, 5}:
                rr.append(Paragraph(str(v), cell_center))
            else:
                rr.append(Paragraph(str(v), cell))
        pdata.append(rr)
    make_table(c, pdata, MARGIN_X, 195, [32, 65, 65, 60, 80, 55, 154], 11.8, font_size=6.6, header_font_size=7.6,
               aligns=["CENTER", "CENTER", "CENTER", "CENTER", "RIGHT", "CENTER", "LEFT"])
    draw_info_box(
        c,
        MARGIN_X,
        386,
        CONTENT_W,
        48,
        "Resultado do exemplo",
        "Quatro máquinas foram classificadas como troca prioritária; quatro como renovação planejada; seis para monitoramento; e uma para<br/>manutenção do cenário atual.",
        red_fill=True,
    )
    c.showPage()


def page_8(c: canvas.Canvas, df: pd.DataFrame) -> None:
    draw_header_footer(c, 8)
    row = df.loc[df["serie"] == 900101].iloc[0]
    draw_section_header(c, "7. EXEMPLO COMPLETO", f"Série 900101 - índice {br_number(row.indice, 1)}")
    draw_paragraph(
        c,
        "Esta máquina ficou em primeiro lugar porque apresentou desempenho desfavorável nas quatro dimensões. A seguir, o cálculo é<br/>demonstrado de forma integral.",
        MARGIN_X,
        145,
        CONTENT_W,
        size=8.8,
        leading=11,
    )
    rows = [
        ["Dado", "Valor", "Interpretação"],
        ["Idade (anos)", "9,8 anos", "Maior idade da base fictícia."],
        ["Reparações no período", "5", "Ocorrências distribuídas na janela analisada."],
        ["Anos observados", "3", "Máquina presente em toda a janela."],
        ["Frequência observada", "5 / 3 = 1,67", "Empatada com a maior frequência."],
        ["Anos com reparação", "3", "Houve reparação em todos os anos."],
        ["Recorrência", "3 / 3 = 100%", "Persistência máxima no exemplo."],
        ["Custo observado", "R$ 7.200", "Terceiro maior custo da base."],
    ]
    make_table(c, rows, MARGIN_X, 196, [140, 130, 241], 12.4, font_size=7.1, header_font_size=7.6,
               aligns=["LEFT", "LEFT", "LEFT"])

    draw_paragraph(c, "Posições percentílicas e pontos", MARGIN_X, 314, 320, size=13.5, bold=True)
    points = [
        ["Dimensão", "Posição/percentil", "Peso", "Pontos"],
        ["Idade", "(15 - 1) / (15 - 1) = 1,0000", "25%", "25,0"],
        ["Frequência", "(14,5 - 1) / (15 - 1) = 0,9643", "30%", "28,9"],
        ["Custo", "(13 - 1) / (15 - 1) = 0,8571", "30%", "25,7"],
        ["Recorrência", "(12 - 1) / (15 - 1) = 0,7857", "15%", "11,8"],
    ]
    make_table(c, points, MARGIN_X, 340, [110, 275, 60, 66], 13, font_size=7.2, header_font_size=7.6,
               aligns=["LEFT", "CENTER", "CENTER", "CENTER"])

    x, top, w, h = 49, 414, 497, 38
    c.setFillColor(WARM)
    c.setStrokeColor(WARM_BORDER)
    c.rect(x, PAGE_H - top - h, w, h, fill=1, stroke=1)
    draw_paragraph(c, "Índice = 25,0 + 28,9 + 25,7 + 11,8 = 91,4", x + 10, top + 7, w - 20, size=10.5, bold=True, align=TA_CENTER)
    draw_paragraph(c, "Classificação: Troca prioritária.", x + 10, top + 24, w - 20, size=7.8, color=MID, align=TA_CENTER)

    draw_info_box(
        c,
        MARGIN_X,
        468,
        CONTENT_W,
        58,
        "Leitura comercial",
        "O resultado não decorre somente dos 9,8 anos. A prioridade máxima é explicada pela presença simultânea de idade elevada, frequência alta, custo elevado e reparações em todos os anos observados.",
    )
    c.showPage()


def interpretation_card(c: canvas.Canvas, top: float, series: str, model: str, index: str, title: str, body: str, accent) -> None:
    x, h = MARGIN_X, 66
    leftw = 110
    c.setFillColor(accent)
    c.rect(x, PAGE_H - top - h, leftw, h, fill=1, stroke=0)
    c.setFillColor(LIGHT)
    c.setStrokeColor(GRID)
    c.rect(x + leftw, PAGE_H - top - h, 401, h, fill=1, stroke=1)
    draw_paragraph(c, series, x + 8, top + 10, leftw - 16, size=12, bold=True, color=WHITE if accent != BEIGE else DARK)
    draw_paragraph(c, model, x + 8, top + 32, leftw - 16, size=8, bold=True, color=WHITE if accent != BEIGE else DARK)
    draw_paragraph(c, f"Índice {index}", x + 8, top + 45, leftw - 16, size=8, bold=True, color=WHITE if accent != BEIGE else DARK)
    draw_paragraph(c, title, x + leftw + 10, top + 10, 381, size=9.2, bold=True, color=RED if accent == RED else (MAGENTA if accent == MAGENTA else DARK))
    draw_paragraph(c, body, x + leftw + 10, top + 31, 381, size=7.6, leading=9.3, color=DARK)


def page_9(c: canvas.Canvas) -> None:
    draw_header_footer(c, 9)
    c.setFillColor(RED)
    c.setFont(FONT, 8.7)
    c.drawString(MARGIN_X, y_from_top(76), "8. EXEMPLOS DE INTERPRETAÇÃO")
    draw_paragraph(
        c,
        "Máquinas diferentes podem chegar a decisões<br/>diferentes",
        MARGIN_X,
        84,
        CONTENT_W,
        size=20,
        leading=20,
        bold=True,
        color=DARK,
    )
    c.setStrokeColor(STEEL)
    c.setLineWidth(0.5)
    c.line(MARGIN_X, y_from_top(170), PAGE_W - MARGIN_X, y_from_top(170))
    interpretation_card(
        c,
        198,
        "900104",
        "TE-2000",
        "76,1",
        "Troca prioritária",
        "Idade de 6,1 anos, mas maior custo do conjunto (R$ 9.500), frequência de 1,33 e recorrência de 100%.<br/>Demonstra que uma máquina relativamente mais nova pode ser prioritária quando custo e frequência são altos.",
        RED,
    )
    interpretation_card(
        c,
        283,
        "900109",
        "TE-500",
        "51,4",
        "Planejar renovação",
        "Idade de 4,2 anos, quatro reparações e custo de R$ 4.500. Não é antiga, porém a frequência de 1,33 e o custo<br/>intermediário justificam planejamento de renovação, sem troca automática.",
        MAGENTA,
    )
    interpretation_card(
        c,
        368,
        "900113",
        "TE-500",
        "24,1",
        "Monitorar",
        "Idade de 9,0 anos, mas nenhuma reparação e custo zero na janela observada. A regra evita recomendar troca<br/>apenas pela idade; o acompanhamento é mantido por ser um ativo envelhecido.",
        WARM_BORDER,
    )
    interpretation_card(
        c,
        453,
        "900115",
        "TE-600",
        "9,8",
        "Manter",
        "Idade de 4,8 anos, nenhuma reparação e custo zero na janela observada. Sem ocorrências recentes e abaixo de 8 anos, a máquina permanece no cenário atual.",
        BEIGE,
    )
    draw_paragraph(c, "O que estes exemplos demonstram", MARGIN_X, 544, 350, size=14, bold=True)
    draw_bullets(
        c,
        [
            "Idade elevada não gera troca automática quando não há ocorrência observada.",
            "Custo e frequência podem elevar a prioridade de máquinas mais novas.",
            "Recorrência diferencia um evento pontual de um padrão persistente ao longo dos anos.",
        ],
        MARGIN_X,
        580,
        CONTENT_W,
        size=8.2,
        leading=10.2,
    )
    c.showPage()


def page_10(c: canvas.Canvas) -> None:
    draw_header_footer(c, 10)
    draw_section_header(c, "9. USO RESPONSÁVEL", "Como utilizar o ranking na decisão")
    draw_paragraph(c, "O índice deve apoiar", MARGIN_X, 154, 250, size=14, bold=True)
    draw_bullets(
        c,
        [
            "A seleção da primeira fila de inspeção técnica e comercial.",
            "A formação de ondas de renovação compatíveis com orçamento e criticidade.",
            "A comparação transparente entre máquinas do mesmo parque e período.",
            "A discussão sobre custo total, disponibilidade e risco operacional.",
        ],
        MARGIN_X,
        178,
        500,
        size=8.3,
        leading=10.4,
    )
    draw_paragraph(c, "O índice não substitui", MARGIN_X, 230, 250, size=14, bold=True)
    draw_bullets(
        c,
        [
            "Inspeção da condição física e teste de aplicação.",
            "Medição de dias indisponíveis, produtividade e custo de oportunidade.",
            "Avaliação de segurança, ergonomia, peças, acessórios e compatibilidade tecnológica.",
            "Análise financeira da alternativa comercial: compra ou Gestão de Frotas.",
        ],
        MARGIN_X,
        254,
        500,
        size=8.3,
        leading=10.4,
    )
    draw_info_box(
        c,
        MARGIN_X,
        304,
        CONTENT_W,
        55,
        "Limitação estatística",
        "As posições percentílicas expressam posição relativa, não magnitude absoluta. Além disso, os pesos são critérios de priorização definidos<br/>para apoiar a decisão; não foram estimados por um modelo preditivo de falha.",
        body_size=7.5,
        body_leading=9.0,
    )
    draw_paragraph(c, "Checklist antes de aprovar a troca", MARGIN_X, 375, 350, size=14, bold=True)
    checklist = [
        ["Etapa", "Verificação"],
        ["1", "Confirmar o número de série e a aplicação da máquina."],
        ["2", "Validar se os registros de reparação e custo estão completos para a janela analisada."],
        ["3", "Verificar condição física, disponibilidade de reserva e criticidade para a operação."],
        ["4", "Comparar o custo total de manter com as alternativas de renovação."],
        ["5", "Definir indicadores para acompanhar os resultados da primeira onda."],
    ]
    make_table(c, checklist, MARGIN_X, 402, [55, 456], 13, font_size=7.5, header_font_size=7.6, aligns=["CENTER", "LEFT"])
    draw_info_box(
        c,
        MARGIN_X,
        492,
        CONTENT_W,
        56,
        "Conclusão",
        "O ranking torna a decisão mais objetiva porque combina quatro dimensões em uma escala comum. Sua melhor utilização é como ponto de partida para uma renovação seletiva, validada tecnicamente e alinhada ao impacto real da operação.",
    )
    c.showPage()


# -----------------------------------------------------------------------------
# Geracao
# -----------------------------------------------------------------------------
def _render_manual(target: str | Path | BinaryIO) -> None:
    df = build_dataframe()

    canvas_target = str(target) if isinstance(target, (str, Path)) else target
    c = canvas.Canvas(canvas_target, pagesize=A4)
    c.setTitle("Manual - Índice de Prioridade de Renovação")
    c.setAuthor("Hilti do Brasil")
    c.setSubject("Metodologia de cálculo e interpretação do ranking de renovação")
    c.setKeywords("renovação, índice, prioridade, frequência, custo, recorrência, idade, posição percentílica")

    page_1(c)
    page_2(c)
    page_3(c)
    page_4(c)
    page_5(c)
    page_6(c, df)
    page_7(c, df)
    page_8(c, df)
    page_9(c)
    page_10(c)
    c.save()


def generate_manual(output_path: str | Path = DEFAULT_OUTPUT) -> Path:
    """Gera o PDF em disco; por padrão, usa a pasta Downloads do usuário."""
    output = Path(output_path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    _render_manual(output)
    return output


def generate_manual_bytes() -> bytes:
    """Gera o PDF em memória para download pelo navegador, sem arquivo temporário."""
    buffer = BytesIO()
    _render_manual(buffer)
    return buffer.getvalue()



    
