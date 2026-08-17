from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence, cast
from xml.sax.saxutils import escape

import pandas as pd
from PIL import Image, ImageChops
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from dashtoolsrecomendation.reports import generator_manual
from dashtoolsrecomendation.reports.config import PdfReportConfig
from dashtoolsrecomendation.services import renewal_analysis


PAGE_W, PAGE_H = A4
LANDSCAPE_W, LANDSCAPE_H = landscape(A4)
MARGIN = 50
CONTENT_W = PAGE_W - 2 * MARGIN
PDF_LAYOUT_VERSION = "hilti-brand-2026-08-v11-generated-methodology-annex"

RED = HexColor("#D2051E")
DARK = HexColor("#524F53")
TEXT = HexColor("#524F53")
MUTED = HexColor("#524F53")
LIGHT = HexColor("#F7F5F2")
LIGHTER = HexColor("#FBFAF8")
BEIGE = HexColor("#D7CEBD")
WINE = HexColor("#671C3E")
TAUPE = HexColor("#887F6E")
GRID = HexColor("#D7D3CD")
COVER_PANEL = HexColor("#F5F3F0")
WHITE = colors.white


def _register_brand_fonts() -> None:
    """Prioriza fontes Hilti e usa Arial como fallback oficial da marca."""
    assets = Path(__file__).parents[1] / "assets"
    candidates = [
        (assets / "HiltiRoman.otf", assets / "HiltiBold.otf"),
        (assets / "Hilti-Roman.ttf", assets / "Hilti-Bold.ttf"),
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
    ]
    for regular, bold in candidates:
        if not regular.exists() or not bold.exists():
            continue
        try:
            # Mantém os nomes já usados pelo gerador e incorpora as fontes ao PDF.
            pdfmetrics.registerFont(TTFont("Helvetica", str(regular)))
            pdfmetrics.registerFont(TTFont("Helvetica-Bold", str(bold)))
            return
        except Exception:
            continue


_register_brand_fonts()


class NumberedCanvas(canvas.Canvas):
    """Canvas que adiciona "página / total" sem uma segunda biblioteca."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 - assinatura ReportLab
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()  # type: ignore[attr-defined] - API interna do ReportLab

    def save(self) -> None:
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            page_width, _ = self._pagesize  # type: ignore[attr-defined]
            self.setFillColor(MUTED)
            self.setFont("Helvetica", 7)
            self.drawCentredString(
                page_width / 2,
                25,
                f"{self.getPageNumber()} / {total}",
            )
            super().showPage()
        super().save()


@dataclass(frozen=True)
class _PreparedData:
    base: pd.DataFrame
    selected: pd.DataFrame
    resumo: dict[str, float]
    cenario: dict[str, float]
    annual: pd.DataFrame
    modelos: pd.DataFrame
    faixas: pd.DataFrame
    pareto: pd.DataFrame
    reconciliation: pd.DataFrame
    reconciliation_summary: dict[str, int]


def _as_float(value: object) -> float:
    """Converte um valor escalar, inclusive escalares NumPy/pandas."""
    return float(cast(Any, value))


def _number(value: object, decimals: int = 0) -> str:
    text = f"{_as_float(value):,.{decimals}f}"
    return text.replace(",", "|").replace(".", ",").replace("|", ".")


def _money(value: object, decimals: int = 2) -> str:
    return f"R$ {_number(value, decimals)}"


def _percent(value: object, decimals: int = 1) -> str:
    return f"{_number(_as_float(value) * 100, decimals)}%"


def _date_br(value: date | pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%d/%m/%Y")


def _safe_text(value: object, default: str = "-") -> str:
    if value is None or bool(pd.isna(cast(Any, value))):
        return default
    text = str(value).strip()
    return text or default


def _trim_image_whitespace(image_bytes: bytes) -> bytes:
    """Remove margens vazias da logo sem alterar sua proporÃ§Ã£o."""
    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert("RGBA")
        flattened = Image.new("RGBA", image.size, (255, 255, 255, 255))
        flattened.alpha_composite(image)
        white = Image.new("RGB", image.size, (255, 255, 255))
        difference = ImageChops.difference(flattened.convert("RGB"), white).convert("L")
        visible = difference.point(
            [0 if value <= 12 else 255 for value in range(256)]
        )
        bbox = visible.getbbox()
        if bbox:
            padding = max(2, round(max(image.size) * 0.02))
            left, top, right, bottom = bbox
            bbox = (
                max(0, left - padding),
                max(0, top - padding),
                min(image.width, right + padding),
                min(image.height, bottom + padding),
            )
            image = image.crop(bbox)

        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


def _series_value(row: pd.Series) -> str:
    for column in ("Número de Série", "Número de série"):
        if column in row.index:
            return _safe_text(row[column])
    return "-"


def _prepare_data(
    base: pd.DataFrame,
    df_ams: pd.DataFrame,
    anos: Iterable[int],
    config: PdfReportConfig,
    *,
    projetar_ano_parcial: bool,
    dashboard_source: pd.DataFrame | None = None,
) -> _PreparedData:
    required = {
        "Número de Série",
        "Idade atual",
        "Reparações no período",
        "Custo com impostos",
        "Índice de prioridade",
    }
    missing = required - set(base.columns)
    if missing:
        raise ValueError(
            "A base analítica não possui as colunas necessárias para o PDF: "
            + ", ".join(sorted(missing))
        )
    if base.empty:
        raise ValueError("Não existem máquinas na base filtrada para gerar o PDF.")

    anos = list(anos)
    quantity = min(config.quantidade_cenario, len(base))
    selected, scenario = renewal_analysis.cenario_renovacao(base, quantity)
    annual = renewal_analysis.analise_anual(
        df_ams,
        anos,
        series=base["Número de Série"].astype("string").tolist(),
        data_corte=config.data_fim,
        tax_factor=config.fator_impostos,
        projetar_ano_parcial=projetar_ano_parcial,
    )
    modelos = renewal_analysis.analise_modelos(base)
    faixas = renewal_analysis.analise_faixas_idade(base, config.idade_corte)
    pareto = renewal_analysis.dados_pareto(base)
    reconciliation, reconciliation_summary = renewal_analysis.reconciliar_fontes(
        dashboard_source if dashboard_source is not None else base,
        df_ams,
        anos,
    )
    return _PreparedData(
        base=base.copy(),
        selected=selected,
        resumo=renewal_analysis.resumo_executivo(base),
        cenario=scenario,
        annual=annual,
        modelos=modelos,
        faixas=faixas,
        pareto=pareto,
        reconciliation=reconciliation,
        reconciliation_summary=reconciliation_summary,
    )


class _ReportRenderer:
    def __init__(self, output: BytesIO, data: _PreparedData, config: PdfReportConfig):
        self.data = data
        self.config = config
        self.c = NumberedCanvas(output, pagesize=A4)
        self.c.setCreator(f"Dash Tools · {PDF_LAYOUT_VERSION}")
        self.c.setSubject("Hilti Brand Fundamentals 2026")
        self.logo_hilti = self._resolve_hilti_logo()
        self._section_footer = "Análise técnica e econômica do parque"

        self.body_style = ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=TEXT,
            alignment=TA_LEFT,
        )
        self.small_style = ParagraphStyle(
            "small",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.2,
            textColor=MUTED,
            alignment=TA_LEFT,
        )
        self.table_style = ParagraphStyle(
            "table",
            fontName="Helvetica",
            fontSize=5.5,
            leading=6.5,
            textColor=TEXT,
            alignment=TA_LEFT,
        )
        self.table_header_style = ParagraphStyle(
            "table-header",
            fontName="Helvetica-Bold",
            fontSize=5.4,
            leading=6.2,
            textColor=WHITE,
            alignment=TA_LEFT,
        )

    def _resolve_hilti_logo(self) -> Path | None:
        if self.config.logo_hilti_path and Path(self.config.logo_hilti_path).exists():
            return Path(self.config.logo_hilti_path)
        default = Path(__file__).parents[1] / "assets" / "hilti_report_logo.jpg"
        return default if default.exists() else None

    # ---------- Base layout ----------
    def _logo(self, x: float = MARGIN, y: float = PAGE_H - 63, width: float = 92) -> None:
        if not self.logo_hilti:
            self.c.setFillColor(RED)
            self.c.rect(x, y, width, 23, fill=1, stroke=0)
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica-Bold", 16)
            self.c.drawCentredString(x + width / 2, y + 6, "HILTI")
            return
        try:
            image = ImageReader(str(self.logo_hilti))
            iw, ih = image.getSize()
            height = width * ih / iw
            self.c.drawImage(image, x, y, width=width, height=height, mask="auto")
        except Exception:
            self.c.setFillColor(RED)
            self.c.rect(x, y, width, 23, fill=1, stroke=0)
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica-Bold", 16)
            self.c.drawCentredString(x + width / 2, y + 6, "HILTI")

    def _footer(self, label: str | None = None) -> None:
        footer = label or self._section_footer
        self.c.setStrokeColor(GRID)
        self.c.setLineWidth(0.5)
        self.c.line(MARGIN, 40, PAGE_W - MARGIN, 40)
        self.c.setFillColor(MUTED)
        self.c.setFont("Helvetica", 7)
        self.c.drawString(MARGIN, 25, footer)
        if self.config.confidencial:
            self.c.drawRightString(PAGE_W - MARGIN, 25, "Confidencial")

    def _header(
        self,
        code: str,
        section_name: str,
        eyebrow: str,
        title: str,
        *,
        title_size: float = 25,
    ) -> float:
        self._logo()
        self.c.setFillColor(MUTED)
        self.c.setFont("Helvetica", 7)
        self.c.drawRightString(PAGE_W - MARGIN, PAGE_H - 42, code)
        self.c.drawRightString(PAGE_W - MARGIN, PAGE_H - 57, section_name)
        self.c.setFillColor(RED)
        self.c.setFont("Helvetica", 8)
        self.c.drawString(MARGIN, PAGE_H - 92, eyebrow.upper())
        y = PAGE_H - 115
        used = self._paragraph(
            title,
            MARGIN,
            y,
            CONTENT_W,
            76,
            font="Helvetica-Bold",
            size=title_size,
            leading=title_size * 1.05,
            color=TEXT,
        )
        return y - used - 15

    def _new_page(self, footer: str | None = None) -> None:
        self._footer(footer)
        self.c.showPage()

    def _paragraph(
        self,
        text: str,
        x: float,
        y_top: float,
        width: float,
        max_height: float,
        *,
        font: str = "Helvetica",
        size: float = 9,
        leading: float | None = None,
        color: Color = TEXT,
        align: Literal[0, 1, 2, 4] = TA_LEFT,
    ) -> float:
        style = ParagraphStyle(
            "dynamic",
            fontName=font,
            fontSize=size,
            leading=leading or size * 1.25,
            textColor=color,
            alignment=align,
            spaceAfter=0,
            spaceBefore=0,
        )
        paragraph = Paragraph(text, style)
        _, height = paragraph.wrap(width, max_height)
        paragraph.drawOn(self.c, x, y_top - height)
        return height

    def _metric_card(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        label: str,
        value: str,
        subtitle: str,
        *,
        value_size: float = 18,
        spread_content: bool = False,
    ) -> None:
        # draw card background
        self.c.setFillColor(LIGHT)
        self.c.roundRect(x, y, width, height, 9, fill=1, stroke=0)

        # prepare subtitle paragraph to measure height
        subtitle_style = ParagraphStyle(
            "metric-sub",
            fontName="Helvetica",
            fontSize=7,
            leading=8.2,
            textColor=MUTED,
            alignment=TA_LEFT,
            spaceAfter=0,
            spaceBefore=0,
        )
        subtitle_para = Paragraph(subtitle, subtitle_style)
        _, subtitle_h = subtitle_para.wrap(width - 22, height)

        if spread_content:
            label_style = ParagraphStyle(
                "metric-label-spread",
                fontName="Helvetica-Bold",
                fontSize=6.5,
                leading=7.5,
                textColor=MUTED,
                alignment=TA_LEFT,
                spaceAfter=0,
                spaceBefore=0,
            )
            label_para = Paragraph(escape(label.upper()), label_style)
            _, label_h = label_para.wrap(width - 22, 20)
            label_para.drawOn(
                self.c,
                x + 11,
                y + height - 10 - label_h,
            )

            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica-Bold", value_size)
            value_y = y + (height - value_size) / 2
            self.c.drawString(x + 11, value_y, value)
            subtitle_para.drawOn(self.c, x + 11, y + 10)
            return

        # baseline sizes and spacings
        label_h = 7.2
        value_h = value_size
        spacing_value_sub = 6
        spacing_label_value = 4

        # compute positions starting from bottom (subtitle) upwards
        subtitle_y = y + 12
        value_y = subtitle_y + subtitle_h + spacing_value_sub
        label_y = value_y + value_h + spacing_label_value

        # ensure content fits; if overflow, reduce spacings, then value size if needed
        top_limit = y + height - 6
        if label_y > top_limit:
            overflow = label_y - top_limit
            total_space = spacing_value_sub + spacing_label_value
            if total_space > 0:
                reduce_value = min(total_space, overflow)
                # proportionally reduce the spacings
                spacing_value_sub = max(0, spacing_value_sub - reduce_value * (spacing_value_sub / total_space))
                spacing_label_value = max(0, spacing_label_value - reduce_value * (spacing_label_value / total_space))
                # recompute positions
                value_y = subtitle_y + subtitle_h + spacing_value_sub
                label_y = value_y + value_h + spacing_label_value
                overflow = label_y - top_limit
            # if still overflowing, reduce value_size (but keep readable)
            if label_y > top_limit:
                available_for_value = max(8, top_limit - (subtitle_y + subtitle_h + spacing_label_value + label_h))
                if available_for_value < 1:
                    available_for_value = 8
                new_value_h = max(10, min(value_h, available_for_value))
                value_size = new_value_h
                value_h = new_value_h
                value_y = subtitle_y + subtitle_h + spacing_value_sub
                label_y = value_y + value_h + spacing_label_value

        # draw label, value and subtitle
        self.c.setFillColor(MUTED)
        self.c.setFont("Helvetica-Bold", 7.2)
        self.c.drawString(x + 11, label_y, label.upper())
        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", value_size)
        self.c.drawString(x + 11, value_y, value)
        # draw subtitle paragraph at its bottom coordinate
        subtitle_para.drawOn(self.c, x + 11, subtitle_y)

    def _callout(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        text: str,
        *,
        red: bool = False,
    ) -> None:
        self.c.setFillColor(RED if red else LIGHT)
        self.c.roundRect(x, y, width, height, 7, fill=1, stroke=0)
        if not red:
            self.c.setFillColor(RED)
            self.c.rect(x, y, 4, height, fill=1, stroke=0)
        self._paragraph(
            text,
            x + 14,
            y + height - 13,
            width - 28,
            height - 18,
            font="Helvetica-Bold" if red else "Helvetica",
            size=8.5 if red else 8,
            leading=10.5,
            color=WHITE if red else TEXT,
        )

    # ---------- Charts ----------
    def _vertical_bars(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        labels: Sequence[str],
        values: Sequence[float],
        *,
        title: str,
        bar_color: Color = RED,
        bar_colors: Sequence[Color] | None = None,
        value_formatter=None,
        max_ticks: int = 4,
    ) -> None:
        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", 8)
        self.c.drawString(x, y + height + 15, title)
        plot_x = x + 30
        plot_y = y + 24
        plot_w = width - 38
        plot_h = height - 30
        maximum = max([float(v) for v in values] + [1.0])
        maximum *= 1.12
        self.c.setStrokeColor(GRID)
        self.c.setLineWidth(0.4)
        for tick in range(max_ticks + 1):
            ty = plot_y + plot_h * tick / max_ticks
            self.c.line(plot_x, ty, plot_x + plot_w, ty)
            val = maximum * tick / max_ticks
            self.c.setFillColor(MUTED)
            self.c.setFont("Helvetica", 5.5)
            tick_text = value_formatter(val) if value_formatter else _number(val, 0)
            self.c.drawRightString(plot_x - 4, ty - 2, tick_text)
        count = max(len(labels), 1)
        slot = plot_w / count
        bar_w = max(4, slot * 0.56)
        for idx, (label, value) in enumerate(zip(labels, values)):
            value = float(value)
            bar_h = plot_h * value / maximum if maximum else 0
            bx = plot_x + idx * slot + (slot - bar_w) / 2
            color = (
                bar_colors[idx]
                if bar_colors is not None and idx < len(bar_colors)
                else bar_color
            )
            self.c.setFillColor(color)
            self.c.rect(bx, plot_y, bar_w, bar_h, fill=1, stroke=0)
            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica", 5.2)
            display = value_formatter(value) if value_formatter else _number(value, 0)
            self.c.drawCentredString(bx + bar_w / 2, plot_y + bar_h + 4, display)
            self.c.setFillColor(MUTED)
            self.c.drawCentredString(bx + bar_w / 2, plot_y - 11, str(label))

    def _horizontal_bars(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        labels: Sequence[str],
        values: Sequence[float],
        *,
        title: str,
        currency: bool = False,
    ) -> None:
        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", 8)
        self.c.drawString(x, y + height + 15, title)
        maximum = max([float(v) for v in values] + [1.0]) * 1.15
        label_w = min(70, width * 0.28)
        plot_x = x + label_w
        plot_w = width - label_w - 30
        count = max(len(labels), 1)
        slot = height / count
        bar_h = max(5, slot * 0.55)
        for idx, (label, value) in enumerate(zip(labels, values)):
            value = float(value)
            cy = y + height - (idx + 0.5) * slot
            self.c.setFillColor(MUTED)
            self.c.setFont("Helvetica", 5.8)
            self.c.drawRightString(plot_x - 5, cy - 2, str(label)[:18])
            bw = plot_w * value / maximum if maximum else 0
            self.c.setFillColor(RED)
            self.c.rect(plot_x, cy - bar_h / 2, bw, bar_h, fill=1, stroke=0)
            display = _money(value, 0) if currency else _number(value, 2)
            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica", 5.6)
            self.c.drawString(plot_x + bw + 4, cy - 2, display)

    def _donut(
        self,
        x: float,
        y: float,
        diameter: float,
        first_fraction: float,
        first_label: str,
        second_label: str,
    ) -> None:
        fraction = min(max(float(first_fraction), 0), 1)
        self.c.setFillColor(BEIGE)
        self.c.circle(x + diameter / 2, y + diameter / 2, diameter / 2, fill=1, stroke=0)
        self.c.setFillColor(RED)
        self.c.wedge(
            x,
            y,
            x + diameter,
            y + diameter,
            startAng=90,
            extent=-360 * fraction,
            fill=1,
            stroke=0,
        )
        self.c.setFillColor(WHITE)
        self.c.circle(x + diameter / 2, y + diameter / 2, diameter * 0.28, fill=1, stroke=0)
        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", 13)
        self.c.drawCentredString(
            x + diameter / 2,
            y + diameter / 2 + 3,
            _percent(fraction),
        )
        self.c.setFont("Helvetica", 6)
        self.c.drawCentredString(x + diameter / 2, y - 13, first_label)
        self.c.drawCentredString(x + diameter / 2, y - 22, second_label)

    def _scatter_priority(self, x: float, y: float, width: float, height: float) -> None:
        data = self.data.base
        max_age = max(_as_float(data["Idade atual"].max()), 1)
        max_rep = max(_as_float(data["Reparações no período"].max()), 1)
        plot_x, plot_y = x + 32, y + 23
        plot_w, plot_h = width - 42, height - 34
        self.c.setStrokeColor(GRID)
        self.c.setLineWidth(0.4)
        for tick in range(5):
            ty = plot_y + tick * plot_h / 4
            self.c.line(plot_x, ty, plot_x + plot_w, ty)
        sample = data if len(data) <= 800 else data.iloc[:: max(1, len(data) // 800)]
        for _, row in sample.iterrows():
            px = plot_x + _as_float(row["Idade atual"]) / max_age * plot_w
            py = plot_y + _as_float(row["Reparações no período"]) / max_rep * plot_h
            recommendation = _safe_text(row.get("Recomendação", ""), "")
            self.c.setFillColor(RED if recommendation == "Troca prioritária" else BEIGE)
            radius = 2.2 if recommendation == "Troca prioritária" else 1.5
            self.c.circle(px, py, radius, fill=1, stroke=0)
        self.c.setFillColor(MUTED)
        self.c.setFont("Helvetica", 6)
        self.c.drawCentredString(plot_x + plot_w / 2, y + 4, "Idade atual (anos)")
        self.c.saveState()
        self.c.translate(x + 7, plot_y + plot_h / 2)
        self.c.rotate(90)
        self.c.drawCentredString(0, 0, "Reparações no período")
        self.c.restoreState()

    def _pareto_chart(self, x: float, y: float, width: float, height: float) -> None:
        data = self.data.pareto
        if data.empty:
            return
        max_cost = max(_as_float(data["Custo com impostos"].max()), 1)
        plot_x, plot_y = x + 35, y + 25
        plot_w, plot_h = width - 50, height - 38
        sample_limit = min(len(data), 180)
        sampled = data.head(sample_limit)
        slot = plot_w / max(sample_limit, 1)
        for index, (_, row) in enumerate(sampled.iterrows()):
            cost = _as_float(row["Custo com impostos"])
            bar_h = plot_h * cost / max_cost
            self.c.setFillColor(RED if index < len(self.data.selected) else BEIGE)
            self.c.rect(plot_x + index * slot, plot_y, max(slot, 0.5), bar_h, fill=1, stroke=0)
        points: list[tuple[float, float]] = []
        for index, (_, row) in enumerate(sampled.iterrows()):
            px = plot_x + (index + 0.5) * slot
            py = plot_y + _as_float(row["Percentual acumulado"]) * plot_h
            points.append((px, py))
        self.c.setStrokeColor(TEXT)
        self.c.setLineWidth(1.2)
        for p1, p2 in zip(points, points[1:]):
            self.c.line(p1[0], p1[1], p2[0], p2[1])
        self.c.setFillColor(MUTED)
        self.c.setFont("Helvetica", 6)
        self.c.drawString(plot_x, y + 4, "Máquinas ordenadas por custo")
        self.c.drawRightString(plot_x + plot_w, y + 4, f"Primeiras {sample_limit}")

    # ---------- Tables ----------
    def _table(
        self,
        rows: Sequence[Sequence[object]],
        col_widths: Sequence[float],
        x: float,
        y_top: float,
        *,
        header: bool = True,
        font_size: float = 6,
        row_padding: float = 2.2,
        max_height: float = 500,
        draw: bool = True,
    ) -> float:
        normalized: list[list[object]] = []
        for row_index, row in enumerate(rows):
            style = self.table_header_style if header and row_index == 0 else self.table_style
            normalized.append(
                [
                    Paragraph(escape(_safe_text(cell, "")), style)
                    if not isinstance(cell, Paragraph)
                    else cell
                    for cell in row
                ]
            )
        table = Table(normalized, colWidths=list(col_widths), repeatRows=1 if header else 0)
        table_style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), row_padding),
            ("RIGHTPADDING", (0, 0), (-1, -1), row_padding),
            ("TOPPADDING", (0, 0), (-1, -1), 1.7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.7),
            ("GRID", (0, 0), (-1, -1), 0.25, GRID),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ]
        if header:
            table_style.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), DARK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
            data_start = 1
        else:
            data_start = 0
        for row_index in range(data_start, len(rows)):
            if (row_index - data_start) % 2:
                table_style.append(("BACKGROUND", (0, row_index), (-1, row_index), LIGHTER))
        table.setStyle(TableStyle(table_style))
        _, height = table.wrap(CONTENT_W, max_height)
        if draw:
            table.drawOn(self.c, x, y_top - height)
        return height

    def _recommendation_summary_table(self, x: float, y_top: float) -> float:
        order = [
            "Troca prioritária",
            "Planejar renovação",
            "Monitorar",
            "Manter",
        ]
        grouped = (
            self.data.base.groupby("Recomendação", dropna=False)
            .agg(
                Máquinas=("Número de Série", "nunique"),
                Reparações=("Reparações no período", "sum"),
                Custo=("Custo com impostos", "sum"),
            )
            .reindex(order, fill_value=0)
        )
        total_repairs = max(_as_float(grouped["Reparações"].sum()), 1)
        total_cost = max(_as_float(grouped["Custo"].sum()), 1)

        headers = [
            "Recomendação",
            "Máquinas",
            "Reparações",
            "% reparações",
            "% custo",
        ]
        col_widths = [145, 58, 70, 112, 50]
        header_h = 24
        row_h = 23
        total_h = header_h + row_h * len(order)
        table_bottom = y_top - total_h

        self.c.setFillColor(DARK)
        self.c.rect(x, y_top - header_h, CONTENT_W, header_h, fill=1, stroke=0)

        cursor_x = x
        for index, (header, col_w) in enumerate(zip(headers, col_widths)):
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica-Bold", 6.5)
            if index == 0:
                self.c.drawString(cursor_x + 8, y_top - 15, header)
            else:
                self.c.drawCentredString(cursor_x + col_w / 2, y_top - 15, header)
            cursor_x += col_w

        tag_colors = {
            "Troca prioritária": RED,
            "Planejar renovação": WINE,
            "Monitorar": TAUPE,
            "Manter": BEIGE,
        }
        for row_index, recommendation in enumerate(order):
            row_top = y_top - header_h - row_index * row_h
            row_bottom = row_top - row_h
            self.c.setFillColor(WHITE if row_index % 2 == 0 else LIGHTER)
            self.c.rect(x, row_bottom, CONTENT_W, row_h, fill=1, stroke=0)
            self.c.setStrokeColor(GRID)
            self.c.setLineWidth(0.35)
            self.c.line(x, row_bottom, x + CONTENT_W, row_bottom)

            row = cast(pd.Series, grouped.loc[recommendation])
            values = [
                _number(row["Máquinas"]),
                _number(row["Reparações"]),
                _percent(_as_float(row["Reparações"]) / total_repairs),
                _percent(_as_float(row["Custo"]) / total_cost),
            ]

            self.c.setFont("Helvetica-Bold", 6.2)
            tag_w = min(
                col_widths[0] - 16,
                stringWidth(recommendation, "Helvetica-Bold", 6.2) + 16,
            )
            tag_y = row_bottom + (row_h - 14) / 2
            self.c.setFillColor(tag_colors[recommendation])
            self.c.roundRect(x + 8, tag_y, tag_w, 14, 7, fill=1, stroke=0)
            self.c.setFillColor(DARK if recommendation == "Manter" else WHITE)
            self.c.drawString(x + 16, tag_y + 4.2, recommendation)

            cursor_x = x + col_widths[0]
            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica", 6.5)
            for value, col_w in zip(values, col_widths[1:]):
                self.c.drawCentredString(
                    cursor_x + col_w / 2,
                    row_bottom + 8,
                    value,
                )
                cursor_x += col_w

        return total_h

    # ---------- Pages ----------
    def build(self) -> None:
        self._cover()
        self._executive_summary()
        self._scope()
        self._fleet_profile()
        self._repair_exposure()
        self._age_evidence()
        self._models()
        self._cost_composition_and_recommendations()
        self._priority_method()
        self._critical_machines()
        self._concentration()
        self._total_cost_risks()
        self._scenarios()
        self._recommendations()
        self._dashboard_annex()
        self._filters_annex()
        self._machine_annex(self.data.selected, "ANEXO C", "Máquinas do cenário prioritário", "C")
        if self.config.incluir_base_completa:
            self._machine_annex(self.data.base, "ANEXO D", "Base analítica completa por máquina", "D")
        self.c.save()

    def _cover(self) -> None:
        # Superfície dinâmica lateral, alinhada ao modelo aprovado para a capa.
        side_panel_x = PAGE_W - 194
        self.c.setFillColor(COVER_PANEL)
        self.c.rect(side_panel_x, 0, PAGE_W - side_panel_x, PAGE_H, fill=1, stroke=0)
        self.c.setFillColor(RED)
        path = self.c.beginPath()
        path.moveTo(side_panel_x, PAGE_H)
        path.lineTo(PAGE_W - 72, PAGE_H)
        path.lineTo(side_panel_x, 150)
        path.close()
        self.c.setStrokeColor(RED)
        self.c.setLineWidth(2)
        self.c.drawPath(path, fill=1, stroke=1)

        # A logo Hilti permanece com as dimensões e o tratamento atuais, sem sombra.
        self._logo(MARGIN, PAGE_H - 75, 95)
        self.c.setFillColor(RED)
        self.c.setFont("Helvetica", 8)
        self.c.drawString(MARGIN, PAGE_H - 132, "DIAGNÓSTICO DO PARQUE DE FERRAMENTAS")
        title_y = PAGE_H - 152
        title_height = self._paragraph(
            self.config.titulo,
            MARGIN,
            title_y,
            365,
            125,
            font="Helvetica-Bold",
            size=30,
            leading=30,
            color=TEXT,
        )
        underline_y = title_y - title_height - 10
        self.c.setFillColor(RED)
        self.c.rect(MARGIN, underline_y, 34, 3, fill=1, stroke=0)
        self._paragraph(
            self.config.subtitulo,
            MARGIN,
            underline_y - 24,
            355,
            75,
            size=11.5,
            leading=15,
            color=TEXT,
        )

        logo_y = 185
        client_logo_max_w = 120
        client_logo_max_h = 55
        if self.config.logo_cliente:
            try:
                cropped_logo = _trim_image_whitespace(self.config.logo_cliente)
                image = ImageReader(BytesIO(cropped_logo))
                iw, ih = image.getSize()
                scale = min(client_logo_max_w / iw, client_logo_max_h / ih)
                width = iw * scale
                height = ih * scale
                self.c.drawImage(
                    image,
                    MARGIN,
                    logo_y,
                    width=width,
                    height=height,
                    mask="auto",
                )
            except Exception:
                self.c.setFillColor(LIGHT)
                self.c.roundRect(
                    MARGIN,
                    logo_y,
                    client_logo_max_w,
                    client_logo_max_h,
                    6,
                    fill=1,
                    stroke=0,
                )
        self.c.setFillColor(MUTED)
        self.c.setFont("Helvetica", 9)
        client_text_x = MARGIN + client_logo_max_w + 15
        self.c.drawString(client_text_x, logo_y + 37, "Preparado para")
        white_area_right = side_panel_x
        self._paragraph(
            escape(self.config.cliente),
            client_text_x,
            logo_y + 25,
            white_area_right - client_text_x - 15,
            40,
            font="Helvetica-Bold",
            size=10,
            leading=12,
            color=TEXT,
        )

        metadata = (
            f"<b>Período observado:</b> {_date_br(self.config.data_inicio)} a {_date_br(self.config.data_fim)}<br/>"
            f"<b>Base analítica:</b> {_number(self.data.resumo['maquinas'])} máquinas após filtros e conciliação<br/>"
            f"<b>Data de emissão:</b> {_date_br(self.config.data_emissao)}<br/>"
            f"<b>Responsável:</b> {self.config.responsavel} - {self.config.cargo_responsavel}"
        )
        self._paragraph(metadata, MARGIN, 130, 390, 70, size=8, leading=10, color=TEXT)

        # Na capa, o NumberedCanvas adiciona somente a numeração central.
        self.c.showPage()

    def _executive_summary(self) -> None:
        y = self._header(
            "01",
            "Resumo executivo",
            "Decisão recomendada",
            f"Renovar por ondas, começando pelas {int(self.data.cenario['maquinas'])} máquinas de maior exposição",
            title_size=23,
        )
        metrics = [
            ("PARQUE ANALISADO", _number(self.data.resumo["maquinas"]), "Máquinas após os filtros"),
            ("PARQUE COM REPARAÇÃO", _percent(self.data.resumo["percentual_reparadas"]), f"{_number(self.data.resumo['maquinas_reparadas'])} máquinas"),
            ("REPARAÇÕES OBSERVADAS", _number(self.data.resumo["reparacoes"]), "Registros no período analisado"),
            ("CUSTO OBSERVADO", _money(self.data.resumo["custo"], 0), "Valor com fator de impostos"),
            ("CUSTO POR MÁQUINA", _money(self.data.resumo["custo_por_maquina_parque"], 0), "Denominador: parque analisado"),
            (f"MÁQUINAS ACIMA DE {self.config.idade_corte} ANOS", _number(self.data.base["Idade atual"].gt(self.config.idade_corte).sum()), "Corte operacional selecionado"),
        ]
        card_w = (CONTENT_W - 20) / 3
        # use explicit row height + gap instead of magic number 105
        row_h = 86
        row_gap = 19
        for idx, item in enumerate(metrics):
            row, col = divmod(idx, 3)
            self._metric_card(
                MARGIN + col * (card_w + 10),
                y - 92 - row * (row_h + row_gap),
                card_w,
                row_h,
                *item,
                value_size=16 if len(item[1]) > 15 else 20,
            )
        conclusion = (
            f"Conclusão executiva: o histórico reúne <b>{_number(self.data.resumo['reparacoes'])}</b> reparações e "
            f"<b>{_money(self.data.resumo['custo'])}</b> em custo direto. O cenário de "
            f"<b>{_number(self.data.cenario['maquinas'])} máquinas</b> concentra "
            f"<b>{_percent(self.data.cenario['percentual_reparacoes'])}</b> das reparações e "
            f"<b>{_percent(self.data.cenario['percentual_custo'])}</b> do custo observado."
        )
        self._callout(MARGIN, y - 330, CONTENT_W, 70, conclusion, red=True)
        small = [
            ("TROCA PRIORITÁRIA", _number(self.data.cenario["maquinas"]), f"{_number(self.data.cenario['reparacoes'])} reparações no grupo"),
            ("PARTICIPAÇÃO NO PARQUE", _percent(self.data.cenario["maquinas"] / self.data.resumo["maquinas"]), "Tamanho do cenário"),
            ("IDADE MÉDIA DO CENÁRIO", f"{_number(self.data.cenario['idade_media'], 1)} anos", "Máquinas selecionadas"),
        ]
        for idx, item in enumerate(small):
            self._metric_card(MARGIN + idx * (card_w + 10), y - 435, card_w, 85, *item, value_size=18)
        self._new_page()

    def _scope(self) -> None:
        y = self._header(
            "02",
            "Escopo, premissas e limitações",
            "Base da análise",
            "Uma leitura transparente para sustentar a decisão comercial",
            title_size=24,
        )
        steps = [
            ("1", "Parque atual", "Base de máquinas, modelo, grupo, status e idade atual."),
            ("2", "Histórico de reparações", f"Ocorrências registradas entre {_date_br(self.config.data_inicio)} e {_date_br(self.config.data_fim)}."),
            ("3", "Base analítica", "Conciliação por número de série, normalização, custos e índice de prioridade."),
        ]
        card_w = (CONTENT_W - 20) / 3
        for idx, (number, title, body) in enumerate(steps):
            x = MARGIN + idx * (card_w + 10)
            self.c.setFillColor(LIGHT)
            self.c.roundRect(x, y - 105, card_w, 95, 8, fill=1, stroke=0)
            self.c.setFillColor(RED)
            self.c.setFont("Helvetica-Bold", 18)
            self.c.drawString(x + 12, y - 35, number)
            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica-Bold", 9)
            self.c.drawString(x + 38, y - 34, title)
            self._paragraph(body, x + 12, y - 52, card_w - 24, 42, size=7.5, leading=9, color=MUTED)
        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", 10)
        self.c.drawString(MARGIN, y - 145, "O que os dados demonstram")
        demonstrates = (
            "• frequência observada por máquina;<br/>"
            "• custo direto registrado no período;<br/>"
            "• recorrência em anos diferentes;<br/>"
            "• concentração por modelo e por equipamento;<br/>"
            "• prioridade relativa para avaliação comercial e técnica."
        )
        self._paragraph(demonstrates, MARGIN, y - 165, 230, 120, size=9, leading=14)
        self.c.setFont("Helvetica-Bold", 10)
        self.c.drawString(MARGIN + 270, y - 145, "O que ainda não está medido diretamente")
        missing = (
            "• dias efetivos de indisponibilidade;<br/>"
            "• perda de produtividade;<br/>"
            "• custo de equipe para troca no cliente;<br/>"
            "• csuto logístico para substituição;<br/>"
            "• impacto de atraso e custo de equipamento substituto."
        )
        self._paragraph(missing, MARGIN + 270, y - 165, 225, 120, size=9, leading=14)
        note = (
            f"Premissa crítica: o período termina em {_date_br(self.config.data_fim)}. Os custos representam registros disponíveis e não incluem "
            "custo de oportunidade, perda de produção, logística ou tempo administrativo. O índice ordena a investigação e não constitui previsão de falha."
        )
        self._callout(MARGIN, y - 330, CONTENT_W, 58, note)
        self._new_page()

    def _fleet_profile(self) -> None:
        y = self._header(
            "03",
            "Perfil atual do parque",
            "Envelhecimento e concentração",
            f"O parque tem {_number(self.data.resumo['maquinas'])} máquinas e {_number(self.data.cenario['maquinas'])} posições no cenário prioritário",
            title_size=23,
        )
        age_counts = (
            self.data.base.assign(Idade=self.data.base["Idade atual"].fillna(0).astype(int))
            .groupby("Idade")
            .size()
            .sort_index()
        )
        labels = [str(value) for value in age_counts.index.tolist()]
        values = [_as_float(value) for value in age_counts.to_numpy()]
        self._vertical_bars(MARGIN + 5, y - 245, 300, 180, labels, values, title="Distribuição por idade (anos)")
        older = int(
            _as_float(
                self.data.base["Idade atual"]
                .gt(self.config.idade_corte)
                .sum()
            )
        )
        cards = [
            (f"MÁQUINAS ACIMA DE {self.config.idade_corte} ANOS", _number(older), _percent(older / len(self.data.base))),
            ("MÁQUINAS NO CENÁRIO", _number(self.data.cenario["maquinas"]), "Lista priorizada"),
            ("IDADE MÉDIA DO PARQUE", f"{_number(self.data.base['Idade atual'].mean(), 1)} anos", "Indicador global do ativo"),
        ]
        # Use card_h + gap so vertical spacing adapts and avoids overlap when text wraps
        card_x = MARGIN + 335
        card_w = 160
        card_h = 68
        gap = 20
        for idx, item in enumerate(cards):
            self._metric_card(card_x, y - 80 - idx * (card_h + gap), card_w, card_h, *item, value_size=16)
        implication = (
            "Implicação comercial: a escala do parque favorece uma renovação por ondas e por famílias de produto, "
            "permitindo negociar padronização, acessórios, treinamento e gestão do ciclo de vida."
        )
        self._callout(MARGIN, y - 325, CONTENT_W, 50, implication)

        model_table = self.data.modelos.head(7)
        rows = [["Modelo", "Máquinas", "Participação", "Idade média", "Reparadas", "Prioritárias"]]
        for _, row in model_table.iterrows():
            machines = _as_float(row["Máquinas"])
            rows.append(
                [
                    _safe_text(row["Modelo"]),
                    _number(machines),
                    _percent(machines / self.data.resumo["maquinas"]),
                    f"{_number(row['Idade média'], 1)} anos",
                    f"{_number(row['Máquinas reparadas'])} ({_percent(row['Percentual reparadas'])})",
                    _number(row["Troca prioritária"]),
                ]
            )
        self._table(rows, [88, 55, 75, 75, 105, 80], MARGIN, y - 350, max_height=170)
        self._new_page()

    def _repair_exposure(self) -> None:
        y = self._header(
            "04",
            "Exposição a reparações",
            "Frequência observada",
            "O histórico é elevado e o último ano pode ser parcial",
            title_size=24,
        )
        annual = self.data.annual
        labels = (
            annual["Ano"].astype(str).tolist() if "Ano" in annual else []
        )
        repairs = (
            annual["Reparações realizadas"].tolist()
            if "Reparações realizadas" in annual
            else []
        )
        costs = (
            annual["Custo realizado"].tolist()
            if "Custo realizado" in annual
            else []
        )
        self._vertical_bars(MARGIN, y - 245, 235, 185, labels, repairs, title="Reparações por ano")
        self._vertical_bars(
            MARGIN + 260,
            y - 245,
            235,
            185,
            labels,
            costs,
            title="Custo de reparações por ano",
            bar_color=BEIGE,
            value_formatter=lambda v: _number(v, 0),
        )
        self._paragraph(
            f"Reparações por ano. O valor de {self.config.data_fim.year} representa o realizado até {_date_br(self.config.data_fim)} quando o ano está parcial.",
            MARGIN,
            y - 265,
            235,
            45,
            size=7,
            leading=9,
        )
        self._paragraph(
            f"Custo por ano. O acumulado de {self.config.data_fim.year} também deve ser interpretado conforme a data de corte.",
            MARGIN + 260,
            y - 265,
            235,
            45,
            size=7,
            leading=9,
        )
        cards = [
            ("REPARAÇÕES ACUMULADAS", _number(self.data.resumo["reparacoes"]), "Período integral da base"),
            ("MÁQUINAS REPARADAS", _number(self.data.resumo["maquinas_reparadas"]), f"{_percent(self.data.resumo['percentual_reparadas'])} do parque"),
            ("REPARAÇÕES POR MÁQUINA", _number(self.data.resumo["reparacoes_por_maquina_parque"], 2), "Denominador: parque total"),
        ]
        card_w = (CONTENT_W - 20) / 3
        for idx, item in enumerate(cards):
            self._metric_card(MARGIN + idx * (card_w + 10), y - 385, card_w, 85, *item, value_size=18)
        self._callout(
            MARGIN,
            y - 470,
            CONTENT_W,
            58,
            "A questão central não é somente quanto custa cada reparo, mas quantas vezes a operação precisa interromper, deslocar, registrar, aguardar e recompor o equipamento.",
            red=True,
        )
        self._new_page()

    def _age_evidence(self) -> None:
        y = self._header(
            "05",
            "Idade, frequência e custo",
            "Evidência técnica",
            f"O corte de {self.config.idade_corte} anos separa grupos com exposição diferente",
            title_size=24,
        )
        faixas = self.data.faixas
        labels = faixas["Faixa etária"].astype(str).tolist()
        self._vertical_bars(
            MARGIN,
            y - 210,
            235,
            150,
            labels,
            faixas["Reparações"].tolist(),
            title="Reparações por faixa de idade",
            bar_colors=[BEIGE, RED],
        )
        fraction = float(faixas.iloc[-1]["Reparações"] / max(faixas["Reparações"].sum(), 1))
        self._donut(MARGIN + 315, y - 195, 125, fraction, labels[-1], labels[0])
        self._vertical_bars(
            MARGIN,
            y - 410,
            235,
            140,
            labels,
            faixas["Reparações por máquina"].tolist(),
            title="Frequência por máquina",
            bar_colors=[BEIGE, RED],
            value_formatter=lambda v: _number(v, 2),
        )
        self._vertical_bars(
            MARGIN + 260,
            y - 410,
            235,
            140,
            labels,
            faixas["Custo por máquina"].tolist(),
            title="Custo por máquina",
            bar_color=BEIGE,
            bar_colors=[BEIGE, RED],
            value_formatter=lambda v: _money(v, 0),
        )
        first, second = faixas.iloc[0], faixas.iloc[-1]
        self._callout(
            MARGIN,
            y - 495,
            235,
            62,
            f"Grupo {first['Faixa etária']}: {_number(first['Máquinas'])} máquinas, {_number(first['Reparações'])} reparações e {_money(first['Custo'])} em custo.",
        )
        self._callout(
            MARGIN + 260,
            y - 495,
            235,
            62,
            f"Grupo {second['Faixa etária']}: {_number(second['Máquinas'])} máquinas, {_number(second['Reparações'])} reparações e {_money(second['Custo'])} em custo.",
        )
        self._new_page()

    def _models(self) -> None:
        y = self._header(
            "06",
            "Modelos e concentração",
            "Exposição por família",
            "Os principais modelos concentram a maior parte do impacto",
            title_size=24,
        )
        top = self.data.modelos.head(8)
        self._horizontal_bars(
            MARGIN,
            y - 210,
            235,
            160,
            top["Modelo"].astype(str).tolist(),
            top["Reparações por máquina"].tolist(),
            title="Taxa de reparação por modelo",
        )
        self._horizontal_bars(
            MARGIN + 260,
            y - 210,
            235,
            160,
            top["Modelo"].astype(str).tolist(),
            top["Custo por máquina"].tolist(),
            title="Custo por máquina e modelo",
            currency=True,
        )
        rows = [["Modelo", "Máquinas", "Reparações", "Custo", "Rep./máq.", "Custo/máq."]]
        for _, row in top.iterrows():
            rows.append(
                [
                    _safe_text(row["Modelo"]),
                    _number(row["Máquinas"]),
                    _number(row["Reparações"]),
                    _money(row["Custo"]),
                    _number(row["Reparações por máquina"], 2),
                    _money(row["Custo por máquina"], 0),
                ]
            )
        self._table(rows, [75, 58, 70, 115, 75, 100], MARGIN, y - 245, max_height=190)
        self._callout(
            MARGIN,
            y - 475,
            235,
            64,
            "A escala dos modelos líderes permite estruturar lotes comerciais por família, com acessórios, treinamento e cronograma de implantação.",
        )
        self._callout(
            MARGIN + 260,
            y - 475,
            235,
            64,
            "Modelos menores devem permanecer no ranking quando o custo unitário, a recorrência ou a criticidade operacional forem elevados.",
        )
        self._new_page()

    def _cost_composition_and_recommendations(self) -> None:
        y = self._header(
            "07",
            "Composição e recomendações",
            "Compoisição de custos e recomendações",
            "O custo observado e as recomendações mostram dimensões complementares da exposição",
            title_size=22,
        )
        composition = renewal_analysis.composicao_custo(self.data.base)
        paid = float(
            composition.loc[
                composition["Componente"].eq("Pago pelo cliente"),
                "Valor",
            ].sum()
        )
        absorbed = float(
            composition.loc[
                composition["Componente"].eq("Valor absorvido"),
                "Valor",
            ].sum()
        )
        total_composition = paid + absorbed
        paid_fraction = paid / total_composition if total_composition else 0
        absorbed_fraction = absorbed / total_composition if total_composition else 0

        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN, y - 55, "Composição do custo de reparações")
        self._donut(
            MARGIN + 42,
            y - 255,
            155,
            paid_fraction,
            "Pago pelo cliente",
            "Valor absorvido",
        )

        recommendation_order = [
            "Troca prioritária",
            "Planejar renovação",
            "Monitorar",
            "Manter",
        ]
        recommendation_counts = (
            self.data.base["Recomendação"]
            .value_counts()
            .reindex(recommendation_order, fill_value=0)
        )
        self._vertical_bars(
            MARGIN + 250,
            y - 275,
            245,
            200,
            ["Troca", "Planejar", "Monitorar", "Manter"],
            recommendation_counts.tolist(),
            title="Distribuição da recomendação analítica",
            bar_colors=[RED, WINE, TAUPE, BEIGE],
        )

        metrics = [
            (
                "CUSTO OBSERVADO",
                _money(total_composition, 0),
                "Soma dos componentes no período",
            ),
            (
                "PAGO PELO CLIENTE",
                _money(paid, 0),
                f"{_percent(paid_fraction)} do custo observado",
            ),
            (
                "VALOR ABSORVIDO",
                _money(absorbed, 0),
                f"{_percent(absorbed_fraction)} do custo observado",
            ),
        ]
        card_w = (CONTENT_W - 20) / 3
        for index, item in enumerate(metrics):
            self._metric_card(
                MARGIN + index * (card_w + 10),
                y - 385,
                card_w,
                78,
                *item,
                value_size=15,
            )

        self._recommendation_summary_table(MARGIN, y - 405)
        self._callout(
            MARGIN,
            y - 570,
            CONTENT_W,
            52,
            "Leitura recomendada: a composição explica quem suportou o custo direto; a distribuição das recomendações mostra como as máquinas se organizam para decisão. Nenhuma das duas medidas representa economia futura garantida.",
        )
        self._new_page()

    def _priority_method(self) -> None:
        y = self._header(
            "08",
            "Priorização da renovação",
            "Critério de decisão",
            "O índice transforma o histórico em uma fila de ação técnica e comercial",
            title_size=23,
        )
        self.c.setFillColor(LIGHTER)
        self.c.roundRect(MARGIN, y - 250, 310, 210, 10, fill=1, stroke=0)
        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN + 12, y - 58, "Matriz de prioridade de renovação")
        self._scatter_priority(MARGIN + 8, y - 242, 295, 170)
        scenario_fraction = self.data.cenario["maquinas"] / self.data.resumo["maquinas"]
        self.c.setFillColor(LIGHTER)
        self.c.roundRect(MARGIN + 330, y - 250, 165, 210, 10, fill=1, stroke=0)
        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawCentredString(MARGIN + 412, y - 58, "Distribuição do cenário")
        self._donut(MARGIN + 360, y - 200, 105, scenario_fraction, "Cenário", "Demais máquinas")

        weights = [
            ("IDADE", "25%", "Exposição de ciclo de vida"),
            ("FREQUÊNCIA", "30%", "Reparações observadas"),
            ("CUSTO", "30%", "Custo direto associado"),
            ("RECORRÊNCIA", "15%", "Anos diferentes com reparo"),
        ]
        card_w = (CONTENT_W - 30) / 4
        for idx, item in enumerate(weights):
            self._metric_card(MARGIN + idx * (card_w + 10), y - 355, card_w, 90, *item, value_size=20)
        self._callout(
            MARGIN,
            y - 445,
            CONTENT_W,
            62,
            "Governança da decisão: o índice ordena a investigação. A seleção deve ser validada quanto à aplicação, condição física, disponibilidade de reserva, criticidade do processo e viabilidade comercial.",
        )
        self._recommendation_summary_table(MARGIN, y - 470)
        self._new_page()

    def _critical_machines(self) -> None:
        y = self._header(
            "09",
            "Máquinas críticas",
            "Primeira fila de avaliação",
            f"{_number(self.data.cenario['maquinas'])} máquinas classificadas no cenário prioritário",
            title_size=24,
        )
        rows = [["Série", "Modelo", "Idade", "Rep.", "Anos", "Custo", "Índice", "Motivo"]]
        for _, row in self.data.selected.head(20).iterrows():
            rows.append(
                [
                    _series_value(row),
                    _safe_text(row.get("Modelo")),
                    _number(row.get("Idade atual", 0), 1),
                    _number(row.get("Reparações no período", 0)),
                    _number(row.get("Anos com reparação", 0)),
                    _money(row.get("Custo com impostos", 0)),
                    _number(row.get("Índice de prioridade", 0), 1),
                    _safe_text(row.get("Motivo principal")),
                ]
            )
        table_height = self._table(
            rows,
            [50, 48, 32, 30, 30, 68, 38, 199],
            MARGIN,
            y - 20,
            font_size=5.4,
            max_height=340,
        )
        cards_y = y - table_height - 125
        card_w = (CONTENT_W - 20) / 3
        cards = [
            ("REPARAÇÕES - GRUPO", _number(self.data.cenario["reparacoes"]), "Associadas ao cenário completo"),
            ("CUSTO OBSERVADO", _money(self.data.cenario["custo"]), "Valor direto do grupo prioritário"),
            ("IDADE MÉDIA", f"{_number(self.data.cenario['idade_media'], 1)} anos", "Média das máquinas selecionadas"),
        ]
        for idx, item in enumerate(cards):
            self._metric_card(MARGIN + idx * (card_w + 10), cards_y, card_w, 76, *item, value_size=14 if idx == 1 else 17)
        self._callout(
            MARGIN,
            cards_y - 70,
            CONTENT_W,
            50,
            f"A tabela mostra as 20 primeiras posições. A relação integral das {_number(self.data.cenario['maquinas'])} máquinas está no Anexo C"
            + (" e a base completa está no Anexo D." if self.config.incluir_base_completa else "."),
        )
        self._new_page()

    def _concentration(self) -> None:
        y = self._header(
            "10",
            "Concentração do impacto",
            "Pareto de custos",
            f"O cenário de {_number(self.data.cenario['maquinas'])} máquinas concentra a maior parcela do impacto",
            title_size=23,
        )
        self.c.setFillColor(LIGHTER)
        self.c.roundRect(MARGIN, y - 255, CONTENT_W, 210, 10, fill=1, stroke=0)
        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN + 12, y - 62, "Pareto do custo por máquina")
        self._pareto_chart(MARGIN + 8, y - 245, CONTENT_W - 16, 165)
        metrics = [
            ("MÁQUINAS NO CENÁRIO", _number(self.data.cenario["maquinas"]), _percent(self.data.cenario["maquinas"] / self.data.resumo["maquinas"])),
            ("REPARAÇÕES CONCENTRADAS", _percent(self.data.cenario["percentual_reparacoes"]), f"{_number(self.data.cenario['reparacoes'])} ocorrências"),
            ("CUSTO CONCENTRADO", _percent(self.data.cenario["percentual_custo"]), _money(self.data.cenario["custo"])),
            ("IDADE MÉDIA", f"{_number(self.data.cenario['idade_media'], 1)} anos", "Máquinas selecionadas"),
        ]
        card_w = (CONTENT_W - 30) / 4
        for idx, item in enumerate(metrics):
            self._metric_card(
                MARGIN + idx * (card_w + 10),
                y - 365,
                card_w,
                90,
                *item,
                value_size=16,
                spread_content=True,
            )
        self._callout(
            MARGIN,
            y - 455,
            CONTENT_W,
            62,
            "Vantagem da abordagem por ondas: iniciar a renovação pelos ativos mais expostos sem substituir todo o parque de uma vez, medir resultados operacionais e ajustar o ritmo das etapas seguintes.",
            red=True,
        )
        self._new_page()

    def _total_cost_risks(self) -> None:
        y = self._header(
            "11",
            "Riscos e custos além da oficina",
            "Custo total da operação",
            "O custo direto de reparação é apenas a parcela visível",
            title_size=24,
        )
        intro = (
            f"O valor observado de <b>{_money(self.data.resumo['custo'])}</b> não inclui, de forma mensurada, perda de produção, "
            "logística interna, tempo de gestão, equipamento reserva, atraso ou reprogramação. Esses efeitos devem ser validados com o cliente."
        )
        intro_top = y - 10
        intro_height = self._paragraph(
            intro,
            MARGIN,
            intro_top,
            CONTENT_W,
            80,
            size=11,
            leading=15,
        )
        items = [
            ("1. Disponibilidade", "Mais ocorrências significam maior exposição a períodos em que a ferramenta não está disponível."),
            ("2. Custo de oportunidade", "Quando a atividade depende do equipamento, a parada pode afetar produtividade."),
            ("3. Complexidade operacional", "Abertura de chamados, transporte, recebimento, controle de reserva e reprogramação consomem tempo administrativo."),
            ("4. Risco de qualidade e segurança", "A ausência do equipamento correto pode induzir improvisos, troca de método ou uso de ferramenta inadequada."),
        ]
        item_w = 240
        item_h = 100
        item_gap = 20
        cards_top = intro_top - intro_height - 16
        for idx, (title, body) in enumerate(items):
            col = idx % 2
            row = idx // 2
            x = MARGIN + col * 255
            yy = cards_top - item_h - row * (item_h + item_gap)
            self.c.setFillColor(LIGHT)
            self.c.roundRect(x, yy, item_w, item_h, 8, fill=1, stroke=0)
            self.c.setFillColor(RED)
            self.c.setFont("Helvetica-Bold", 10)
            self.c.drawString(x + 12, yy + 72, title)
            self._paragraph(body, x + 12, yy + 60, 216, 45, size=8.5, leading=11)
        formula = "Modelo recomendado: custo de oportunidade = dias indisponíveis × valor econômico diário da atividade afetada + logística + equipamento substituto + reprogramação."
        self._callout(MARGIN, y - 385, CONTENT_W, 62, formula)
        self._new_page()

    def _scenarios(self) -> None:
        y = self._header(
            "12",
            "Cenários de renovação",
            "Plano comercial em ondas",
            "Equilibrar urgência operacional, capacidade de investimento e velocidade de implantação",
            title_size=22,
        )
        quantities = sorted({min(50, len(self.data.base)), min(100, len(self.data.base)), len(self.data.selected)})
        quantities = [q for q in quantities if q > 0]
        scenarios = [renewal_analysis.cenario_renovacao(self.data.base, q)[1] for q in quantities]
        # Gráfico comparativo de concentração.
        labels = [str(int(s["maquinas"])) for s in scenarios]
        repairs = [s["percentual_reparacoes"] * 100 for s in scenarios]
        costs = [s["percentual_custo"] * 100 for s in scenarios]
        chart_y = y - 205
        self._vertical_bars(MARGIN, chart_y, 235, 145, labels, repairs, title="Reparações concentradas (%)", value_formatter=lambda v: f"{_number(v, 1)}%")
        self._vertical_bars(MARGIN + 260, chart_y, 235, 145, labels, costs, title="Custo concentrado (%)", bar_color=BEIGE, value_formatter=lambda v: f"{_number(v, 1)}%")

        card_w = (CONTENT_W - 20) / 3
        card_y = y - 385
        labels_title = ["Onda inicial", "Onda intermediária", "Programa estruturado"]
        for idx in range(3):
            if idx < len(scenarios):
                scenario = scenarios[idx]
                title = labels_title[idx]
                quantity = int(scenario["maquinas"])
                body = (
                    f"{_number(scenario['reparacoes'])} reparações ({_percent(scenario['percentual_reparacoes'])})<br/>"
                    f"{_money(scenario['custo'])} ({_percent(scenario['percentual_custo'])})<br/>"
                    f"Idade média: {_number(scenario['idade_media'], 1)} anos"
                )
            else:
                title, quantity, body = "Cenário", 0, "-"
            x = MARGIN + idx * (card_w + 10)
            self.c.setFillColor(LIGHT)
            self.c.roundRect(x, card_y, card_w, 130, 9, fill=1, stroke=0)
            self.c.setFillColor(MUTED)
            self.c.setFont("Helvetica-Bold", 8)
            self.c.drawString(x + 12, card_y + 105, title)
            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica-Bold", 18)
            self.c.drawString(x + 12, card_y + 78, f"{quantity} máquinas")
            self._paragraph(body, x + 12, card_y + 65, card_w - 24, 55, size=7.5, leading=10)
        self._callout(
            MARGIN,
            y - 475,
            CONTENT_W,
            62,
            f"Cenário configurado no Dashboard: {_number(self.data.cenario['maquinas'])} máquinas. A implantação pode ocorrer integralmente ou em ondas, conforme orçamento, criticidade e capacidade operacional.",
            red=True,
        )
        self._new_page()

    def _recommendations(self) -> None:
        y = self._header(
            "13",
            "Recomendação final",
            "Próximas ações",
            "Da análise à decisão: quatro passos para reduzir exposição operacional",
            title_size=23,
        )
        steps = [
            ("1", "Validar em campo", "Aplicação, condição física, criticidade e disponibilidade de reserva."),
            ("2", "Definir a implantação", f"Viabilizar as {int(self.data.cenario['maquinas'])} máquinas, de forma integral ou faseada."),
            ("3", "Quantificar indisponibilidade", "Adicionar dias parados, custo da atividade afetada e logística."),
            ("4", "Programar renovação", "Definir indicadores, responsáveis e cronograma de Gestão de Frotas."),
        ]
        card_w = (CONTENT_W - 30) / 4
        for idx, (number, title, body) in enumerate(steps):
            x = MARGIN + idx * (card_w + 10)
            self.c.setFillColor(LIGHT)
            self.c.roundRect(x, y - 145, card_w, 125, 9, fill=1, stroke=0)
            self.c.setFillColor(RED)
            self.c.setFont("Helvetica-Bold", 20)
            self.c.drawString(x + 12, y - 52, number)
            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica-Bold", 8)
            self._paragraph(title, x + 12, y - 68, card_w - 24, 28, font="Helvetica-Bold", size=8, leading=9)
            self._paragraph(body, x + 12, y - 95, card_w - 24, 52, size=7, leading=8.5, color=MUTED)
        statement = (
            "Manter o parque sem uma política de renovação significa continuar aceitando custos recorrentes, esforço operacional e risco de indisponibilidade sem reduzir o envelhecimento dos ativos."
        )
        statement_top = y - 185
        statement_height = self._paragraph(
            statement,
            MARGIN,
            statement_top,
            CONTENT_W,
            65,
            font="Helvetica-Bold",
            size=13,
            leading=16,
        )
        decision_card_h = 105
        decision_cards_top = statement_top - statement_height - 20
        decision_cards_y = decision_cards_top - decision_card_h
        self._callout(
            MARGIN,
            decision_cards_y,
            240,
            decision_card_h,
            f"<b>Decisão mínima recomendada</b><br/>Autorizar a avaliação técnica e comercial das {int(self.data.cenario['maquinas'])} máquinas do ranking, mantendo a alternativa de implantação por fases.",
        )
        self._callout(
            MARGIN + 255,
            decision_cards_y,
            240,
            decision_card_h,
            f"<b>Decisão estrutural recomendada</b><br/>Construir uma proposta em Gestão de Frotas para as {int(self.data.cenario['maquinas'])} máquinas, dividida por criticidade, família e cronograma.",
        )
        self._callout(
            MARGIN,
            decision_cards_y - 95,
            CONTENT_W,
            65,
            "Mensagem final: os dados sustentam uma renovação seletiva e planejada. O objetivo não é trocar máquinas apenas por idade, mas reduzir a exposição criada por frequência, custo, recorrência e risco operacional.",
            red=True,
        )
        self._new_page()

    def _snapshot_chart_box(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        title: str,
    ) -> tuple[float, float, float, float]:
        panel_card = HexColor("#3A373B")
        self.c.setFillColor(panel_card)
        self.c.roundRect(x, y, width, height, 3, fill=1, stroke=0)
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica-Bold", 4.6)
        self.c.drawString(x + 5, y + height - 9, title)
        return x + 7, y + 8, width - 14, height - 21

    def _snapshot_bars(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        values: Sequence[float],
        *,
        title: str,
        colors_sequence: Sequence[Color] | None = None,
        horizontal: bool = False,
        labels: Sequence[object] | None = None,
        value_formatter=None,
        show_values: bool = True,
    ) -> None:
        plot_x, plot_y, plot_w, plot_h = self._snapshot_chart_box(
            x,
            y,
            width,
            height,
            title,
        )
        numeric = [max(float(value), 0) for value in values]
        maximum = max(numeric + [1.0])
        category_labels = [str(value) for value in (labels or [])]
        formatter = value_formatter or (lambda value: _number(value, 0))

        if horizontal:
            label_space = min(35, plot_w * 0.28) if category_labels else 0
            value_space = min(28, plot_w * 0.22) if show_values else 0
            plot_x += label_space
            plot_w -= label_space + value_space
        else:
            label_space = 8 if category_labels else 0
            value_space = 7 if show_values else 0
            plot_y += label_space
            plot_h -= label_space + value_space

        self.c.setStrokeColor(HexColor("#5B575E"))
        self.c.setLineWidth(0.25)
        for tick in range(1, 4):
            if horizontal:
                tx = plot_x + plot_w * tick / 4
                self.c.line(tx, plot_y, tx, plot_y + plot_h)
            else:
                ty = plot_y + plot_h * tick / 4
                self.c.line(plot_x, ty, plot_x + plot_w, ty)

        count = max(len(numeric), 1)
        if horizontal:
            slot = plot_h / count
            bar_h = max(2, slot * 0.55)
            for index, value in enumerate(numeric):
                bar_w = plot_w * value / maximum if maximum else 0
                color = (
                    colors_sequence[index % len(colors_sequence)]
                    if colors_sequence
                    else RED
                )
                self.c.setFillColor(color)
                self.c.rect(
                    plot_x,
                    plot_y + plot_h - (index + 0.72) * slot,
                    bar_w,
                    bar_h,
                    fill=1,
                    stroke=0,
                )
                center_y = plot_y + plot_h - (index + 0.72) * slot + bar_h / 2
                self.c.setFillColor(HexColor("#D6D6E7"))
                self.c.setFont("Helvetica", 3.1)
                if index < len(category_labels):
                    self.c.drawRightString(
                        plot_x - 2,
                        center_y - 1.2,
                        category_labels[index][:16],
                    )
                if show_values:
                    self.c.setFillColor(WHITE)
                    self.c.setFont("Helvetica-Bold", 3.1)
                    self.c.drawString(
                        min(plot_x + bar_w + 2, plot_x + plot_w + 2),
                        center_y - 1.2,
                        str(formatter(value))[:13],
                    )
        else:
            slot = plot_w / count
            bar_w = max(1.5, slot * 0.62)
            for index, value in enumerate(numeric):
                bar_h = plot_h * value / maximum if maximum else 0
                color = (
                    colors_sequence[index % len(colors_sequence)]
                    if colors_sequence
                    else RED
                )
                self.c.setFillColor(color)
                self.c.rect(
                    plot_x + index * slot + (slot - bar_w) / 2,
                    plot_y,
                    bar_w,
                    bar_h,
                    fill=1,
                    stroke=0,
                )
                center_x = plot_x + index * slot + slot / 2
                if show_values:
                    self.c.setFillColor(WHITE)
                    self.c.setFont("Helvetica-Bold", 3.2)
                    self.c.drawCentredString(
                        center_x,
                        min(plot_y + bar_h + 2, plot_y + plot_h + 1),
                        str(formatter(value))[:12],
                    )
                if index < len(category_labels):
                    self.c.setFillColor(HexColor("#D6D6E7"))
                    self.c.setFont("Helvetica", 2.9)
                    self.c.drawCentredString(
                        center_x,
                        plot_y - 5.2,
                        category_labels[index][:9],
                    )

    def _snapshot_donut(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        values: Sequence[float],
        labels: Sequence[object],
        *,
        title: str,
        colors_sequence: Sequence[Color] | None = None,
        value_formatter=None,
    ) -> None:
        plot_x, plot_y, plot_w, plot_h = self._snapshot_chart_box(
            x,
            y,
            width,
            height,
            title,
        )
        numeric = [max(float(value), 0) for value in values]
        total = sum(numeric)
        if total <= 0:
            return
        colors_used = colors_sequence or [RED, BEIGE, WINE, TAUPE]
        diameter = min(plot_h - 2, plot_w * 0.45)
        center_x = plot_x + diameter / 2 + 2
        center_y = plot_y + plot_h / 2
        radius = diameter / 2
        start = 90.0
        for index, value in enumerate(numeric):
            extent = 360.0 * value / total
            if extent <= 0:
                continue
            self.c.setFillColor(colors_used[index % len(colors_used)])
            self.c.wedge(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                start,
                extent,
                fill=1,
                stroke=0,
            )
            start += extent
        self.c.setFillColor(HexColor("#3A373B"))
        self.c.circle(center_x, center_y, radius * 0.58, fill=1, stroke=0)

        formatter = value_formatter or (lambda value: _number(value, 0))
        legend_x = plot_x + diameter + 7
        line_y = plot_y + plot_h - 9
        for index, (label, value) in enumerate(zip(labels, numeric)):
            percent = value / total
            self.c.setFillColor(colors_used[index % len(colors_used)])
            self.c.circle(legend_x, line_y - index * 12 + 1, 2, fill=1, stroke=0)
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica-Bold", 3.4)
            self.c.drawString(
                legend_x + 5,
                line_y - index * 12,
                f"{_percent(percent)} · {str(formatter(value))[:10]}",
            )
            self.c.setFillColor(HexColor("#D6D6E7"))
            self.c.setFont("Helvetica", 2.9)
            self.c.drawString(
                legend_x + 5,
                line_y - index * 12 - 4,
                str(label)[:20],
            )

    def _snapshot_scatter(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        plot_x, plot_y, plot_w, plot_h = self._snapshot_chart_box(
            x,
            y,
            width,
            height,
            "Matriz de prioridade",
        )
        plot_y += 9
        plot_h -= 13
        data = self.data.base
        max_age = max(_as_float(data["Idade atual"].max()), 1)
        max_repairs = max(
            _as_float(data["Reparações no período"].max()), 1
        )
        self.c.setStrokeColor(HexColor("#5B575E"))
        self.c.setLineWidth(0.25)
        for tick in range(1, 4):
            self.c.line(
                plot_x,
                plot_y + plot_h * tick / 4,
                plot_x + plot_w,
                plot_y + plot_h * tick / 4,
            )
        sample = data if len(data) <= 280 else data.iloc[:: max(1, len(data) // 280)]
        recommendation_colors = {
            "Troca prioritária": RED,
            "Planejar renovação": WINE,
            "Monitorar": TAUPE,
            "Manter": BEIGE,
        }
        for _, row in sample.iterrows():
            px = plot_x + _as_float(row["Idade atual"]) / max_age * plot_w
            py = (
                plot_y
                + _as_float(row["Reparações no período"])
                / max_repairs
                * plot_h
            )
            priority = _safe_text(row.get("Recomendação"), "")
            self.c.setFillColor(recommendation_colors.get(priority, BEIGE))
            self.c.circle(px, py, 0.9, fill=1, stroke=0)
        legend_items = [
            ("Troca prioritária", RED),
            ("Planejar", WINE),
            ("Monitorar", TAUPE),
            ("Manter", BEIGE),
        ]
        legend_y = plot_y - 7
        legend_slot = plot_w / len(legend_items)
        for index, (label, color) in enumerate(legend_items):
            legend_x = plot_x + index * legend_slot
            self.c.setFillColor(color)
            self.c.circle(legend_x + 2, legend_y + 1, 1.3, fill=1, stroke=0)
            self.c.setFillColor(HexColor("#D6D6E7"))
            self.c.setFont("Helvetica", 2.7)
            self.c.drawString(legend_x + 5, legend_y, label)

    def _snapshot_pareto(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        by_score: bool = False,
    ) -> None:
        title = (
            "Ranking pelo índice de prioridade"
            if by_score
            else "Pareto do custo por máquina"
        )
        plot_x, plot_y, plot_w, plot_h = self._snapshot_chart_box(
            x,
            y,
            width,
            height,
            title,
        )
        if by_score:
            data = self.data.base.sort_values(
                "Índice de prioridade",
                ascending=False,
            ).head(180)
            values = data["Índice de prioridade"].astype(float)
        else:
            data = self.data.pareto.head(180)
            values = data["Custo com impostos"].astype(float)
        if data.empty:
            return
        maximum = max(_as_float(values.max()), 1)
        slot = plot_w / len(data)
        selected_series = set(
            self.data.selected["Número de Série"].astype(str)
        )
        cumulative: list[tuple[float, float]] = []
        running = 0.0
        total = max(_as_float(values.sum()), 1)
        for index, ((_, row), value) in enumerate(zip(data.iterrows(), values)):
            bar_height = plot_h * _as_float(value) / maximum
            is_selected = _series_value(row) in selected_series
            self.c.setFillColor(RED if is_selected else BEIGE)
            self.c.rect(
                plot_x + index * slot,
                plot_y,
                max(slot, 0.35),
                bar_height,
                fill=1,
                stroke=0,
            )
            running += _as_float(value)
            cumulative.append(
                (
                    plot_x + (index + 0.5) * slot,
                    plot_y + plot_h * running / total,
                )
            )
        if not by_score and len(cumulative) > 1:
            self.c.setStrokeColor(WHITE)
            self.c.setLineWidth(0.55)
            path = self.c.beginPath()
            path.moveTo(*cumulative[0])
            for point in cumulative[1:]:
                path.lineTo(*point)
            self.c.drawPath(path, fill=0, stroke=1)

    def _snapshot_table(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        frame: pd.DataFrame,
        *,
        title: str,
    ) -> None:
        table_x, table_y, table_w, table_h = self._snapshot_chart_box(
            x,
            y,
            width,
            height,
            title,
        )
        rows = frame.head(7)
        row_h = table_h / 8
        columns = [0.23, 0.23, 0.16, 0.18, 0.20]
        headers = ["Série", "Modelo", "Idade", "Índice", "Recomendação"]
        self.c.setFillColor(HexColor("#565159"))
        self.c.rect(table_x, table_y + 7 * row_h, table_w, row_h, fill=1, stroke=0)
        cursor = table_x
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica-Bold", 3.6)
        for header, fraction in zip(headers, columns):
            self.c.drawString(cursor + 2, table_y + 7.35 * row_h, header)
            cursor += table_w * fraction
        for row_index, (_, row) in enumerate(rows.iterrows()):
            baseline = table_y + (6.3 - row_index) * row_h
            if row_index % 2:
                self.c.setFillColor(HexColor("#423E45"))
                self.c.rect(
                    table_x,
                    table_y + (6 - row_index) * row_h,
                    table_w,
                    row_h,
                    fill=1,
                    stroke=0,
                )
            values = [
                _series_value(row),
                _safe_text(row.get("Modelo")),
                _number(row.get("Idade atual", 0), 1),
                _number(row.get("Índice de prioridade", 0), 1),
                _safe_text(row.get("Recomendação")),
            ]
            cursor = table_x
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica", 3.4)
            for value, fraction in zip(values, columns):
                self.c.drawString(cursor + 2, baseline, str(value)[:22])
                cursor += table_w * fraction

    def _snapshot_small_cards(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        cards: Sequence[tuple[str, str, str]],
    ) -> None:
        gap = 4
        card_w = (width - gap * (len(cards) - 1)) / max(len(cards), 1)
        for index, (label, value, subtitle) in enumerate(cards):
            card_x = x + index * (card_w + gap)
            self.c.setFillColor(HexColor("#403C43"))
            self.c.roundRect(card_x, y, card_w, height, 2.5, fill=1, stroke=0)
            self.c.setFillColor(HexColor("#D6D6E7"))
            self.c.setFont("Helvetica-Bold", 3.1)
            self.c.drawCentredString(
                card_x + card_w / 2,
                y + height - 7,
                label[:27],
            )
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica-Bold", 5.4)
            self.c.drawCentredString(
                card_x + card_w / 2,
                y + height / 2 - 1,
                value[:18],
            )
            self.c.setFillColor(HexColor("#D6D6E7"))
            self.c.setFont("Helvetica", 2.7)
            self.c.drawCentredString(
                card_x + card_w / 2,
                y + 4,
                subtitle[:39],
            )

    def _snapshot_quality_table(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        table_x, table_y, table_w, table_h = self._snapshot_chart_box(
            x,
            y,
            width,
            height,
            "Conciliação das fontes por número de série",
        )
        rows = self.data.reconciliation.head(13)
        row_count = max(len(rows) + 1, 2)
        row_h = table_h / row_count
        fractions = [0.27, 0.28, 0.45]
        headers = ["Série", "Modelo", "Status de conciliação"]
        self.c.setFillColor(HexColor("#565159"))
        self.c.rect(
            table_x,
            table_y + (row_count - 1) * row_h,
            table_w,
            row_h,
            fill=1,
            stroke=0,
        )
        cursor = table_x
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica-Bold", 3.8)
        for header, fraction in zip(headers, fractions):
            self.c.drawString(
                cursor + 2,
                table_y + (row_count - 0.68) * row_h,
                header,
            )
            cursor += table_w * fraction
        for row_index, (_, row) in enumerate(rows.iterrows()):
            row_y = table_y + (row_count - 2 - row_index) * row_h
            if row_index % 2:
                self.c.setFillColor(HexColor("#423E45"))
                self.c.rect(table_x, row_y, table_w, row_h, fill=1, stroke=0)
            values = [
                _safe_text(row.get("Número de Série")),
                _safe_text(row.get("Modelo")),
                _safe_text(row.get("Status de conciliação")),
            ]
            cursor = table_x
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica", 3.5)
            for value, fraction in zip(values, fractions):
                self.c.drawString(
                    cursor + 2,
                    row_y + row_h * 0.32,
                    value[:34],
                )
                cursor += table_w * fraction

    def _dashboard_snapshot_panel(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        kind: str,
        caption: str,
    ) -> None:
        self.c.setFillColor(WHITE)
        self.c.setStrokeColor(GRID)
        self.c.setLineWidth(0.6)
        self.c.roundRect(x, y, width, height, 7, fill=1, stroke=1)

        screen_x = x + 6
        screen_y = y + 29
        screen_w = width - 12
        screen_h = height - 37
        self.c.setFillColor(HexColor("#2D2A2F"))
        self.c.rect(screen_x, screen_y, screen_w, screen_h, fill=1, stroke=0)
        self._logo(screen_x + 5, screen_y + screen_h - 20, 35)
        self.c.setFillColor(WHITE)
        self.c.setFont("Helvetica-Bold", 4)
        self.c.drawRightString(
            screen_x + screen_w - 5,
            screen_y + screen_h - 12,
            "Dashboard",
        )

        if kind == "summary":
            metrics = [
                ("PARQUE ATUAL", _number(self.data.resumo["maquinas"])),
                ("PARQUE REPARADO", _percent(self.data.resumo["percentual_reparadas"])),
                ("REPARAÇÕES", _number(self.data.resumo["reparacoes"])),
                ("REPARAÇÕES/MÁQUINA", _number(self.data.resumo["reparacoes_por_maquina_parque"], 2)),
                ("CUSTO OBSERVADO", _money(self.data.resumo["custo"], 0)),
                ("CUSTO/MÁQUINA", _money(self.data.resumo["custo_por_maquina_parque"], 0)),
            ]
        elif kind == "models":
            metrics = [
                ("PARQUE ATUAL", _number(self.data.resumo["maquinas"])),
                ("PARQUE REPARADO", _percent(self.data.resumo["percentual_reparadas"])),
                ("REPARAÇÕES", _number(self.data.resumo["reparacoes"])),
                ("REPARAÇÕES/MÁQUINA", _number(self.data.resumo["reparacoes_por_maquina_parque"], 2)),
                ("CUSTO OBSERVADO", _money(self.data.resumo["custo"], 0)),
                ("MODELOS", _number(len(self.data.modelos))),
            ]
        elif kind == "renewal":
            metrics = [
                ("MÁQUINAS NO CENÁRIO", _number(self.data.cenario["maquinas"])),
                ("PARTICIPAÇÃO NO PARQUE", _percent(self.data.cenario["maquinas"] / max(len(self.data.base), 1))),
                ("REPARAÇÕES CONCENTRADAS", _percent(self.data.cenario["percentual_reparacoes"])),
                ("CUSTO CONCENTRADO", _percent(self.data.cenario["percentual_custo"])),
                ("IDADE MÉDIA", f"{_number(self.data.cenario['idade_media'], 1)} a"),
                ("REPARAÇÕES", _number(self.data.cenario["reparacoes"])),
            ]
        else:
            summary = self.data.reconciliation_summary
            metrics = [
                ("PARQUE ATUAL", _number(summary["parque_atual"])),
                ("AMS NO PERÍODO", _number(summary["ams_periodo"])),
                ("PRESENTES NAS DUAS", _number(summary["presentes_duas"])),
                ("SOMENTE NO PARQUE", _number(summary["somente_parque"])),
                ("SOMENTE NO AMS", _number(summary["somente_ams"])),
                ("UNIVERSO CONCILIADO", _number(summary["universo_conciliado"])),
            ]

        metrics_y = screen_y + screen_h - 53
        gap = 3
        metric_w = (screen_w - 10 - 5 * gap) / 6
        for index, (label, value) in enumerate(metrics):
            mx = screen_x + 5 + index * (metric_w + gap)
            self.c.setFillColor(HexColor("#403C43"))
            self.c.roundRect(mx, metrics_y, metric_w, 27, 2.5, fill=1, stroke=0)
            self.c.setFillColor(HexColor("#D6D6E7"))
            self.c.setFont("Helvetica", 3.2)
            self.c.drawCentredString(mx + metric_w / 2, metrics_y + 18, label)
            self.c.setFillColor(WHITE)
            self.c.setFont("Helvetica-Bold", 5.3)
            self.c.drawCentredString(
                mx + metric_w / 2,
                metrics_y + 8,
                value[:15],
            )

        content_x = screen_x + 5
        content_w = screen_w - 10
        half_w = (content_w - 6) / 2
        if kind == "summary":
            ages = (
                self.data.base["Idade atual"]
                .fillna(0)
                .astype(int)
                .value_counts()
                .sort_index()
                .head(12)
            )
            cut = self.config.idade_corte
            above_cut = int(
                _as_float(self.data.base["Idade atual"].gt(cut).sum())
            )
            top_quantity = min(20, len(self.data.base))
            _, top_scenario = renewal_analysis.cenario_renovacao(
                self.data.base,
                top_quantity,
            )
            self._snapshot_small_cards(
                content_x,
                screen_y + 333,
                content_w,
                27,
                [
                    (
                        f"ACIMA DE {cut} ANOS",
                        _number(above_cut),
                        f"{_percent(above_cut / max(len(self.data.base), 1))} do parque filtrado",
                    ),
                    (
                        "TROCA PRIORITÁRIA",
                        _number(
                            self.data.base["Recomendação"]
                            .eq("Troca prioritária")
                            .sum()
                        ),
                        "Classificação relativa ao conjunto filtrado",
                    ),
                    (
                        f"CUSTO CONCENTRADO NO TOP {top_quantity}",
                        _percent(top_scenario["percentual_custo"]),
                        "Participação no custo observado",
                    ),
                ],
            )
            self._snapshot_bars(
                content_x,
                screen_y + 234,
                half_w,
                93,
                ages.tolist(),
                title="Máquinas por idade",
                labels=ages.index.tolist(),
            )
            self._snapshot_scatter(
                content_x + half_w + 6,
                screen_y + 234,
                half_w,
                93,
            )
            quarter_gap = 4
            quarter_w = (content_w - 3 * quarter_gap) / 4
            faixa_labels = self.data.faixas["Faixa etária"].tolist()
            self._snapshot_bars(
                content_x,
                screen_y + 155,
                quarter_w,
                72,
                self.data.faixas["Reparações"].tolist(),
                title="Reparações por faixa de idade",
                colors_sequence=[RED, BEIGE],
                labels=faixa_labels,
            )
            self._snapshot_donut(
                content_x + quarter_w + quarter_gap,
                screen_y + 155,
                quarter_w,
                72,
                self.data.faixas["Reparações"].tolist(),
                faixa_labels,
                title="Percentual de reparações por faixa",
                colors_sequence=[RED, BEIGE],
            )
            self._snapshot_bars(
                content_x + 2 * (quarter_w + quarter_gap),
                screen_y + 155,
                quarter_w,
                72,
                self.data.faixas["Máquinas"].tolist(),
                title="Máquinas por faixa de idade",
                colors_sequence=[RED, BEIGE],
                labels=faixa_labels,
            )
            self._snapshot_donut(
                content_x + 3 * (quarter_w + quarter_gap),
                screen_y + 155,
                quarter_w,
                72,
                self.data.faixas["Máquinas"].tolist(),
                faixa_labels,
                title="Percentual de máquinas por faixa",
                colors_sequence=[RED, BEIGE],
            )
            self._snapshot_bars(
                content_x,
                screen_y + 89,
                half_w,
                60,
                self.data.faixas["Reparações por máquina"].tolist(),
                title="Frequência observada por faixa etária",
                colors_sequence=[RED, BEIGE],
                labels=faixa_labels,
                value_formatter=lambda value: _number(value, 2),
            )
            self._snapshot_bars(
                content_x + half_w + 6,
                screen_y + 89,
                half_w,
                60,
                self.data.faixas["Custo por máquina"].tolist(),
                title="Custo observado por máquina e faixa etária",
                colors_sequence=[RED, BEIGE],
                labels=faixa_labels,
                value_formatter=lambda value: _money(value, 0),
            )
            self._snapshot_table(
                content_x,
                screen_y + 5,
                content_w,
                78,
                self.data.base,
                title="Máquinas com maior prioridade analítica",
            )
        elif kind == "models":
            annual_repairs = self.data.annual["Reparações realizadas"].tolist()
            annual_cost = self.data.annual["Custo realizado"].tolist()
            top_models = self.data.modelos.head(7)
            year_labels = self.data.annual["Ano"].tolist()
            self._snapshot_bars(
                content_x,
                screen_y + 253,
                half_w,
                107,
                annual_repairs,
                title="Reparações por ano",
                labels=year_labels,
            )
            self._snapshot_bars(
                content_x + half_w + 6,
                screen_y + 253,
                half_w,
                107,
                annual_cost,
                title="Custo de reparações por ano",
                colors_sequence=[BEIGE],
                labels=year_labels,
                value_formatter=lambda value: _number(value, 0),
            )
            self._snapshot_bars(
                content_x,
                screen_y + 157,
                half_w,
                90,
                top_models["Reparações por máquina"].tolist(),
                title="Taxa de reparação por modelo",
                horizontal=True,
                labels=top_models["Modelo"].tolist(),
                value_formatter=lambda value: _number(value, 2),
            )
            self._snapshot_bars(
                content_x + half_w + 6,
                screen_y + 157,
                half_w,
                90,
                top_models["Custo por máquina"].tolist(),
                title="Custo por máquina e modelo",
                horizontal=True,
                labels=top_models["Modelo"].tolist(),
                value_formatter=lambda value: _money(value, 0),
            )
            composition = renewal_analysis.composicao_custo(self.data.base)
            self._snapshot_donut(
                content_x,
                screen_y + 88,
                half_w,
                63,
                composition["Valor"].tolist(),
                composition["Componente"].tolist(),
                title="Composição do custo de reparações",
                colors_sequence=[RED, BEIGE],
                value_formatter=lambda value: _money(value, 0),
            )
            recommendation_order = [
                "Troca prioritária",
                "Planejar renovação",
                "Monitorar",
                "Manter",
            ]
            recommendation_counts = (
                self.data.base["Recomendação"]
                .value_counts()
                .reindex(recommendation_order, fill_value=0)
            )
            self._snapshot_bars(
                content_x + half_w + 6,
                screen_y + 88,
                half_w,
                63,
                recommendation_counts.tolist(),
                title="Distribuição da recomendação analítica",
                colors_sequence=[RED, WINE, TAUPE, BEIGE],
                labels=["Troca", "Planejar", "Monitorar", "Manter"],
            )
            self._snapshot_table(
                content_x,
                screen_y + 5,
                content_w,
                77,
                self.data.base.loc[
                    self.data.base["Modelo"].isin(top_models["Modelo"])
                ],
                title="Impacto por modelo",
            )
        elif kind == "renewal":
            self._snapshot_pareto(
                content_x,
                screen_y + 175,
                content_w,
                165,
            )
            self._snapshot_table(
                content_x,
                screen_y + 10,
                content_w,
                155,
                self.data.selected,
                title="Máquinas sugeridas para avaliação comercial e técnica",
            )
        else:
            status_counts = (
                self.data.reconciliation["Status de conciliação"]
                .value_counts()
                .reindex(
                    [
                        "Presente nas duas fontes",
                        "Somente no parque atual",
                        "Somente no AMS do período",
                    ],
                    fill_value=0,
                )
            )
            self._snapshot_donut(
                content_x,
                screen_y + 245,
                half_w,
                115,
                status_counts.tolist(),
                ["Presentes nas duas", "Somente no parque", "Somente no AMS"],
                title="Distribuição da conciliação das fontes",
                colors_sequence=[RED, BEIGE, TAUPE],
            )
            self._snapshot_bars(
                content_x + half_w + 6,
                screen_y + 245,
                half_w,
                115,
                status_counts.tolist(),
                title="Registros por status de conciliação",
                colors_sequence=[RED, BEIGE, TAUPE],
                labels=["Duas", "Parque", "AMS"],
            )
            self.c.setFillColor(HexColor("#403C43"))
            self.c.roundRect(
                content_x,
                screen_y + 210,
                content_w,
                27,
                2.5,
                fill=1,
                stroke=0,
            )
            self.c.setFillColor(HexColor("#D6D6E7"))
            self.c.setFont("Helvetica", 3.5)
            self.c.drawString(
                content_x + 7,
                screen_y + 226,
                "Registros somente no parque indicam ausência no AMS dentro da janela selecionada;",
            )
            self.c.drawString(
                content_x + 7,
                screen_y + 219,
                "não significam ausência de manutenção durante toda a vida da máquina.",
            )
            self._snapshot_quality_table(
                content_x,
                screen_y + 5,
                content_w,
                198,
            )

        self.c.setFillColor(TEXT)
        self.c.setFont("Helvetica", 5.5)
        self.c.drawString(x + 7, y + 10, caption)

    def _dashboard_annex_footer(self) -> None:
        self.c.setStrokeColor(GRID)
        self.c.setLineWidth(0.5)
        self.c.line(MARGIN, 40, LANDSCAPE_W - MARGIN, 40)
        self.c.setFillColor(MUTED)
        self.c.setFont("Helvetica", 7)
        self.c.drawString(MARGIN, 25, "Anexo A - Painéis utilizados na análise")
        if self.config.confidencial:
            self.c.drawRightString(
                LANDSCAPE_W - MARGIN,
                25,
                "Confidencial",
            )

    def _dashboard_annex(self) -> None:
        pages = [
            [
                (
                    "summary",
                    "Resumo executivo e matriz de prioridade.",
                ),
                (
                    "models",
                    "Modelos, custos e evolução anual.",
                ),
            ],
            [
                (
                    "renewal",
                    "Plano de renovação.",
                ),
                (
                    "quality",
                    "Qualidade dos dados e conciliação das fontes.",
                ),
            ],
        ]
        self.c.setPageSize(landscape(A4))
        panel_gap = 16
        panel_w = (LANDSCAPE_W - 2 * 32 - panel_gap) / 2
        for page_index, panels in enumerate(pages, start=1):
            self.c.setFillColor(RED)
            self.c.setFont("Helvetica", 8)
            self.c.drawString(32, LANDSCAPE_H - 31, "ANEXO A")
            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica-Bold", 17)
            self.c.drawString(
                32,
                LANDSCAPE_H - 51,
                "Painéis utilizados na análise",
            )
            self._logo(LANDSCAPE_W - 83, LANDSCAPE_H - 41, 51)
            self.c.setFillColor(MUTED)
            self.c.setFont("Helvetica", 7)
            self.c.drawRightString(
                LANDSCAPE_W - 32,
                LANDSCAPE_H - 55,
                f"Página {page_index} de {len(pages)}",
            )
            for column, (kind, caption) in enumerate(panels):
                self._dashboard_snapshot_panel(
                    32 + column * (panel_w + panel_gap),
                    62,
                    panel_w,
                    458,
                    kind,
                    caption,
                )
            self._dashboard_annex_footer()
            self.c.showPage()
        self.c.setPageSize(A4)

    def _filters_annex(self) -> None:
        y = self._header(
            "B01",
            "Parâmetros utilizados",
            "Anexo B",
            "Filtros e parâmetros da geração do relatório",
            title_size=24,
        )
        rows: list[list[object]] = [
            ["Parâmetro", "Valor"],
            ["Cliente", self.config.cliente],
            ["Data inicial", _date_br(self.config.data_inicio)],
            ["Data final", _date_br(self.config.data_fim)],
            ["Idade de corte", f"{self.config.idade_corte} anos"],
            ["Fator de impostos", _number(self.config.fator_impostos, 2)],
            ["Quantidade no cenário", _number(self.data.cenario["maquinas"])],
            [
                "Incluir manual metodológico",
                "Sim" if self.config.incluir_manual_metodologia else "Não",
            ],
            ["Incluir base completa", "Sim" if self.config.incluir_base_completa else "Não"],
        ]
        for key, value in self.config.filtros.items():
            if value in (None, "", [], ()):
                continue
            if isinstance(value, (list, tuple, set)):
                display = ", ".join(str(item) for item in value)
            else:
                display = str(value)
            rows.append([str(key), display])
        self._table(rows, [160, 335], MARGIN, y - 20, font_size=8, max_height=420)
        self._callout(
            MARGIN,
            y - 460,
            CONTENT_W,
            65,
            "Rastreabilidade: os valores deste anexo devem ser preservados junto ao PDF para permitir a reprodução do cenário no Dashboard.",
        )
        self._new_page("Anexo B - Parâmetros utilizados")

    def _methodology_page_header(
        self,
        page_number: int,
        title: str,
        subtitle: str,
        *,
        title_size: float = 23,
    ) -> float:
        y = self._header(
            f"E{page_number:02d}",
            "Manual de metodologia",
            "Anexo E",
            title,
            title_size=title_size,
        )
        used = self._paragraph(
            subtitle,
            MARGIN,
            y,
            CONTENT_W,
            55,
            size=8.5,
            leading=11,
            color=MUTED,
        )
        return y - used - 18

    def _methodology_heading(self, text: str, y: float) -> float:
        self.c.setFillColor(RED)
        self.c.setFont("Helvetica-Bold", 10)
        self.c.drawString(MARGIN, y, text)
        return y - 18

    def _methodology_bullets(
        self,
        items: Sequence[str],
        y: float,
        *,
        width: float = CONTENT_W,
        size: float = 8.2,
    ) -> float:
        text = "<br/>".join(f"&#8226;&nbsp; {item}" for item in items)
        used = self._paragraph(
            text,
            MARGIN,
            y,
            width,
            500,
            size=size,
            leading=size * 1.45,
        )
        return y - used - 12

    def _methodology_annex(self) -> None:
        """Renderiza o manual v2 com a identidade visual do relatório."""
        footer = "Anexo E - Manual de metodologia do índice de prioridade"

        y = self._methodology_page_header(
            0,
            "Índice de Prioridade de Renovação",
            "Como idade, frequência, custo e recorrência são combinados em uma fila transparente de avaliação técnica e comercial.",
            title_size=25,
        )
        self._callout(
            MARGIN,
            y - 90,
            CONTENT_W,
            75,
            "Objetivo do manual: explicar, em linguagem não técnica, de onde vêm os índices apresentados nos estudos de renovação e como interpretar corretamente o resultado.",
            red=True,
        )
        rows = [
            ["Item", "Definição"],
            ["Aplicação", "Estudos de renovação de parques de ferramentas"],
            ["Exemplo didático", "15 máquinas com dados inteiramente fictícios"],
            ["Princípio", "Priorizar investigação; não prever falha futura"],
            ["Versão", "Metodologia v2 - posição percentílica normalizada"],
        ]
        self._table(rows, [130, 365], MARGIN, y - 125, font_size=8, max_height=180)
        self._callout(
            MARGIN,
            y - 360,
            CONTENT_W,
            62,
            "O índice é uma ferramenta de priorização relativa. A decisão de troca continua dependendo da validação técnica, da aplicação e do impacto operacional.",
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            1,
            "1. Visão geral",
            "O que o índice mede e como o resultado deve ser interpretado.",
        )
        y = self._methodology_heading("O que o índice mede", y)
        used = self._paragraph(
            "O Índice de Prioridade de Renovação organiza as máquinas da maior para a menor necessidade de avaliação. Ele combina quatro sinais observáveis e transforma medidas diferentes em uma única escala comparável.",
            MARGIN,
            y,
            CONTENT_W,
            60,
            size=8.5,
            leading=11,
        )
        y -= used + 14
        rows = [
            ["Peso", "Dimensão", "Finalidade"],
            ["25%", "Idade", "Exposição ao envelhecimento e à obsolescência relativa."],
            ["30%", "Frequência", "Quantidade de reparações ajustada pelo tempo observado."],
            ["30%", "Custo", "Custo direto acumulado das reparações no período."],
            ["15%", "Recorrência", "Persistência das ocorrências em anos diferentes."],
        ]
        height = self._table(rows, [50, 90, 355], MARGIN, y, font_size=7.4, max_height=160)
        y -= height + 18
        y = self._methodology_heading("A leitura correta", y)
        y = self._methodology_bullets(
            [
                "Quanto maior o índice, maior a prioridade relativa dentro do parque analisado.",
                "O índice não representa probabilidade de falha ou vida útil restante.",
                "A classificação deve ser confirmada em campo, considerando aplicação, condição física, reserva e criticidade operacional.",
                "Se o parque ou os filtros mudarem, as posições também podem mudar.",
            ],
            y,
        )
        self._callout(
            MARGIN,
            y - 63,
            CONTENT_W,
            55,
            "Mensagem central: a metodologia evita decisões baseadas somente na idade. O topo do ranking decorre de uma combinação desfavorável dos quatro fatores.",
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            2,
            "2. Dados e indicadores",
            "Poucos dados são necessários, desde que estejam associados de forma confiável ao número de série.",
        )
        rows = [
            ["Informação", "Significado", "Uso no índice"],
            ["Número de série", "Identificador individual da máquina.", "Consolida os registros do ativo."],
            ["Idade atual", "Tempo desde a aquisição ou entrada em operação.", "Idade - peso de 25%."],
            ["Reparações", "Total observado na janela escolhida.", "Base para a frequência."],
            ["Anos observados", "Anos da janela em que a máquina já existia.", "Evita penalizar máquinas recentes."],
            ["Anos com reparação", "Anos diferentes com ao menos uma ocorrência.", "Base para a recorrência."],
            ["Custo observado", "Soma dos custos diretos no período.", "Custo - peso de 30%."],
        ]
        height = self._table(rows, [105, 215, 175], MARGIN, y, font_size=6.8, max_height=220)
        y -= height + 20
        y = self._methodology_heading("Indicadores derivados", y)
        formulas = [
            ["Indicador", "Fórmula", "Exemplo"],
            ["Frequência observada", "Reparações / anos observados", "5 / 3 = 1,67 por ano"],
            ["Recorrência", "Anos com reparação / anos observados", "2 / 3 = 0,67, ou 67%"],
        ]
        height = self._table(formulas, [115, 190, 190], MARGIN, y, font_size=7.4, max_height=120)
        y -= height + 18
        self._callout(
            MARGIN,
            y - 65,
            CONTENT_W,
            58,
            "Por que ajustar pelo tempo? Duas reparações em um ano indicam intensidade maior do que duas reparações distribuídas em três anos.",
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            3,
            "3. Posição relativa",
            "As quatro dimensões são convertidas para uma escala comparável de 0 a 1.",
        )
        self._callout(
            MARGIN,
            y - 70,
            CONTENT_W,
            58,
            "Posição percentílica = (posição média no ranking - 1) / (quantidade de máquinas - 1)",
            red=True,
        )
        y -= 98
        used = self._paragraph(
            "O ranking é crescente: valores maiores recebem posições percentílicas maiores. Em caso de empate, as máquinas recebem a posição média do grupo.",
            MARGIN,
            y,
            CONTENT_W,
            50,
            size=8.5,
            leading=11,
        )
        y -= used + 16
        y = self._methodology_heading("Exemplo de empate", y)
        rows = [
            ["Etapa", "Cálculo", "Resultado"],
            ["Posições ocupadas", "14 e 15", "-"],
            ["Posição média", "(14 + 15) / 2", "14,5"],
            ["Posição percentílica", "(14,5 - 1) / (15 - 1)", "0,9643"],
            ["Leitura", "Posição percentílica x 100", "96,43%"],
        ]
        height = self._table(rows, [145, 215, 135], MARGIN, y, font_size=7.5, max_height=160)
        y -= height + 20
        y = self._methodology_heading("Como interpretar", y)
        self._methodology_bullets(
            [
                "0,00 representa o menor valor da dimensão, quando não há empate na base.",
                "1,00 representa o maior valor da dimensão, quando não há empate no topo.",
                "0,80 indica posição próxima aos 20% mais altos do conjunto.",
                "A posição é relativa; ela não mede a diferença absoluta entre as máquinas.",
            ],
            y,
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            4,
            "4. Pesos e recomendação",
            "A soma ponderada converte as posições percentílicas em uma escala de 0 a 100.",
        )
        self._callout(
            MARGIN,
            y - 72,
            CONTENT_W,
            60,
            "Índice = 100 x [(25% x P idade) + (30% x P frequência) + (30% x P custo) + (15% x P recorrência)]",
            red=True,
        )
        y -= 100
        rows = [
            ["Faixa", "Nível", "Orientação"],
            ["0-29,9", "Baixa prioridade", "Manter ou monitorar conforme idade e histórico."],
            ["30-49,9", "Monitorar", "Acompanhar a evolução das ocorrências."],
            ["50-69,9", "Planejar renovação", "Avaliar troca programada e orçamento."],
            ["70-100", "Troca prioritária", "Exige ao menos duas reparações."],
        ]
        height = self._table(rows, [70, 125, 300], MARGIN, y, font_size=7.4, max_height=165)
        y -= height + 20
        y = self._methodology_heading("Regras complementares", y)
        self._methodology_bullets(
            [
                "Sem reparação e com menos de 8 anos: <b>Manter</b>.",
                "Sem reparação e com 8 anos ou mais: <b>Monitorar</b>.",
                "Índice igual ou superior a 70 exige ao menos duas reparações para <b>Troca prioritária</b>.",
                "Índice entre 50 e 69,9: <b>Planejar renovação</b>.",
                "Índice entre 30 e 49,9, ou pelo menos duas reparações: <b>Monitorar</b>.",
            ],
            y,
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            5,
            "5. Exemplo didático",
            "Base inteiramente fictícia com 15 máquinas e janela máxima de três anos.",
        )
        rows = [
            ["Série", "Modelo", "Idade", "Reparos", "Anos obs.", "Anos c/ reparo", "Custo"],
            ["900101", "TE-500", "9,8", "5", "3", "3", "R$ 7.200"],
            ["900102", "TE-500", "9,4", "4", "3", "3", "R$ 6.100"],
            ["900103", "TE-600", "7,2", "5", "3", "2", "R$ 8.600"],
            ["900104", "TE-2000", "6,1", "4", "3", "3", "R$ 9.500"],
            ["900105", "TE-500", "8,5", "2", "3", "2", "R$ 4.800"],
            ["900106", "TE-800", "7,0", "3", "3", "2", "R$ 5.400"],
            ["900107", "TE-500", "6,3", "3", "3", "3", "R$ 3.900"],
            ["900108", "TE-1000", "5,5", "2", "3", "2", "R$ 3.200"],
            ["900109", "TE-500", "4,2", "4", "3", "2", "R$ 4.500"],
            ["900110", "TE-500", "3,8", "3", "3", "3", "R$ 3.000"],
            ["900111", "TE-500", "2,0", "2", "2", "2", "R$ 2.500"],
            ["900112", "TE-2000", "1,1", "1", "1", "1", "R$ 1.800"],
            ["900113", "TE-500", "9,0", "0", "3", "0", "R$ 0"],
            ["900114", "TE-500", "6,8", "1", "3", "1", "R$ 1.400"],
            ["900115", "TE-600", "4,8", "0", "3", "0", "R$ 0"],
        ]
        height = self._table(
            rows,
            [60, 72, 48, 52, 64, 92, 107],
            MARGIN,
            y,
            font_size=6.2,
            row_padding=1.8,
            max_height=330,
        )
        y -= height + 18
        self._callout(
            MARGIN,
            y - 68,
            CONTENT_W,
            60,
            "A série 900104 demonstra por que a idade não decide sozinha: apesar de mais nova que várias TE-500, ela possui o maior custo observado da base.",
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            6,
            "6. Ranking, recomendação e motivo",
            "Resultado da aplicação da posição percentílica normalizada às 15 máquinas fictícias.",
            title_size=21,
        )
        rows = [
            ["Pos.", "Série", "Freq.", "Recorr.", "Custo", "Índice", "Recomendação", "Motivo principal"],
            ["1", "900101", "1,67", "100%", "R$ 7.200", "91,4", "Troca prioritária", "Alta frequência e alto custo"],
            ["2", "900102", "1,33", "100%", "R$ 6.100", "82,1", "Troca prioritária", "Alta frequência e alto custo"],
            ["3", "900103", "1,67", "67%", "R$ 8.600", "80,0", "Troca prioritária", "Alta frequência e alto custo"],
            ["4", "900104", "1,33", "100%", "R$ 9.500", "76,1", "Troca prioritária", "Alta frequência e alto custo"],
            ["5", "900106", "1,00", "67%", "R$ 5.400", "57,9", "Planejar renovação", "Baixo impacto recente"],
            ["6", "900107", "1,00", "100%", "R$ 3.900", "54,3", "Planejar renovação", "Reparações recorrentes"],
            ["7", "900105", "0,67", "67%", "R$ 4.800", "51,8", "Planejar renovação", "Idade elevada"],
            ["8", "900109", "1,33", "67%", "R$ 4.500", "51,4", "Planejar renovação", "Alta frequência no período"],
            ["9", "900110", "1,00", "100%", "R$ 3.000", "41,1", "Monitorar", "Reparações recorrentes"],
            ["10", "900111", "1,00", "100%", "R$ 2.500", "37,1", "Monitorar", "Reparações recorrentes"],
            ["11", "900108", "0,67", "67%", "R$ 3.200", "34,6", "Monitorar", "Baixo impacto recente"],
            ["12", "900112", "1,00", "100%", "R$ 1.800", "33,2", "Monitorar", "Reparações recorrentes"],
            ["13", "900114", "0,33", "33%", "R$ 1.400", "25,0", "Manter", "Baixo impacto recente"],
            ["14", "900113", "0,00", "0%", "R$ 0", "24,1", "Monitorar", "Idade elevada"],
            ["15", "900115", "0,00", "0%", "R$ 0", "9,8", "Manter", "Baixo impacto recente"],
        ]
        height = self._table(
            rows,
            [25, 45, 35, 40, 55, 35, 105, 155],
            MARGIN,
            y,
            font_size=5.2,
            row_padding=1.2,
            max_height=350,
        )
        y -= height + 16
        self._callout(
            MARGIN,
            y - 66,
            CONTENT_W,
            58,
            "Resultado: quatro máquinas em troca prioritária, quatro em renovação planejada, cinco para monitoramento e duas para manutenção do cenário atual.",
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            7,
            "7. Exemplo completo: série 900101",
            "A primeira colocada apresenta desempenho desfavorável nas quatro dimensões.",
            title_size=21,
        )
        details = [
            ["Dado", "Valor", "Interpretação"],
            ["Idade atual", "9,8 anos", "Maior idade da base fictícia."],
            ["Reparações", "5", "Ocorrências distribuídas na janela."],
            ["Anos observados", "3", "Presente em toda a janela."],
            ["Frequência", "5 / 3 = 1,67", "Empatada com a maior frequência."],
            ["Recorrência", "3 / 3 = 100%", "Reparação em todos os anos."],
            ["Custo observado", "R$ 7.200", "Terceiro maior custo da base."],
        ]
        height = self._table(details, [110, 120, 265], MARGIN, y, font_size=7.2, max_height=190)
        y -= height + 20
        y = self._methodology_heading("Posições percentílicas e pontos", y)
        scores = [
            ["Dimensão", "Posição percentílica", "Peso", "Pontos"],
            ["Idade", "(15 - 1) / (15 - 1) = 1,0000", "25%", "25,0"],
            ["Frequência", "(14,5 - 1) / (15 - 1) = 0,9643", "30%", "28,9"],
            ["Custo", "(13 - 1) / (15 - 1) = 0,8571", "30%", "25,7"],
            ["Recorrência", "(12 - 1) / (15 - 1) = 0,7857", "15%", "11,8"],
        ]
        height = self._table(scores, [95, 255, 65, 80], MARGIN, y, font_size=7.1, max_height=150)
        y -= height + 20
        self._callout(
            MARGIN,
            y - 64,
            CONTENT_W,
            56,
            "Índice = 25,0 + 28,9 + 25,7 + 11,8 = 91,4. Classificação: Troca prioritária.",
            red=True,
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            8,
            "8. Exemplos de interpretação",
            "Máquinas com históricos diferentes podem chegar a recomendações diferentes.",
        )
        examples = [
            (
                "900104 · TE-2000 · índice 76,1 · Troca prioritária",
                "Idade de 6,1 anos, maior custo do conjunto, frequência de 1,33 e recorrência de 100%.",
            ),
            (
                "900109 · TE-500 · índice 51,4 · Planejar renovação",
                "Idade de 4,2 anos, quatro reparações e custo intermediário justificam planejamento, sem troca automática.",
            ),
            (
                "900113 · TE-500 · índice 24,1 · Monitorar",
                "Idade de 9 anos, nenhuma reparação e custo zero. A idade sustenta o acompanhamento, mas não a troca.",
            ),
            (
                "900115 · TE-600 · índice 9,8 · Manter",
                "Idade de 4,8 anos, nenhuma reparação e custo zero. Sem ocorrência recente e abaixo de 8 anos, permanece no cenário atual.",
            ),
        ]
        for title, description in examples:
            self.c.setFillColor(LIGHT)
            self.c.roundRect(MARGIN, y - 78, CONTENT_W, 68, 7, fill=1, stroke=0)
            self._paragraph(title, MARGIN + 14, y - 22, CONTENT_W - 28, 20, font="Helvetica-Bold", size=8.2, leading=10)
            self._paragraph(description, MARGIN + 14, y - 43, CONTENT_W - 28, 30, size=7.7, leading=9.5)
            y -= 82
        y = self._methodology_heading("O que os exemplos demonstram", y - 2)
        self._methodology_bullets(
            [
                "Idade elevada não gera troca automática sem ocorrência observada.",
                "Custo e frequência podem elevar a prioridade de máquinas mais novas.",
                "Baixo índice, ausência de reparações e idade inferior a 8 anos sustentam <b>Manter</b>.",
            ],
            y,
            size=7.8,
        )
        self._new_page(footer)

        y = self._methodology_page_header(
            9,
            "9. Uso responsável",
            "O ranking é um ponto de partida para uma renovação seletiva e tecnicamente validada.",
        )
        y = self._methodology_heading("O índice deve apoiar", y)
        y = self._methodology_bullets(
            [
                "A seleção da primeira fila de inspeção técnica e comercial.",
                "A formação de ondas de renovação compatíveis com orçamento e criticidade.",
                "A comparação transparente entre máquinas do mesmo parque e período.",
                "A discussão sobre custo total, disponibilidade e risco operacional.",
            ],
            y,
        )
        y = self._methodology_heading("O índice não substitui", y)
        y = self._methodology_bullets(
            [
                "Inspeção da condição física e teste de aplicação.",
                "Medição de dias indisponíveis, produtividade e custo de oportunidade.",
                "Avaliação de segurança, ergonomia, peças, acessórios e compatibilidade tecnológica.",
                "Análise financeira entre compra, locação ou Gestão de Frotas.",
            ],
            y,
        )
        self._callout(
            MARGIN,
            y - 72,
            CONTENT_W,
            64,
            "Limitação estatística: as posições percentílicas expressam posição relativa, não magnitude absoluta. Os pesos apoiam a decisão; não foram estimados por um modelo preditivo de falha.",
        )
        checklist = [
            ["Etapa", "Verificação antes de aprovar a troca"],
            ["1", "Confirmar número de série e aplicação."],
            ["2", "Validar registros de reparação e custo."],
            ["3", "Verificar condição física, reserva e criticidade."],
            ["4", "Comparar o custo de manter com as alternativas."],
            ["5", "Definir indicadores para acompanhar a primeira onda."],
        ]
        self._table(checklist, [55, 440], MARGIN, y - 95, font_size=7.2, max_height=160)
        self._new_page(footer)

    def _annex_rows(self, frame: pd.DataFrame) -> list[list[str]]:
        rows: list[list[str]] = []
        for _, row in frame.iterrows():
            recommendation = _safe_text(row.get("Recomendação"), "-")
            rows.append(
                [
                    _series_value(row),
                    _safe_text(row.get("Modelo")),
                    _safe_text(row.get("Grupo")),
                    _number(row.get("Idade atual", 0), 1),
                    _number(row.get("Reparações no período", 0)),
                    _number(row.get("Anos com reparação", 0)),
                    _money(row.get("Custo com impostos", 0)),
                    _number(row.get("Índice de prioridade", 0), 1),
                    recommendation,
                    _safe_text(row.get("Motivo principal")),
                ]
            )
        return rows

    def _paginate_annex_rows(
        self,
        rows: list[list[str]],
        header: list[str],
        widths: Sequence[float],
        available_height: float,
    ) -> list[list[list[str]]]:
        if not rows:
            return [[]]

        pages: list[list[list[str]]] = []
        start = 0
        while start < len(rows):
            low = 1
            high = len(rows) - start
            rows_that_fit = 0

            # A busca binÃ¡ria mede a tabela com o mesmo estilo usado no desenho.
            # Isso aproveita a pÃ¡gina sem assumir que todas as linhas tÃªm a mesma
            # altura, pois textos longos podem quebrar dentro das cÃ©lulas.
            while low <= high:
                candidate_count = (low + high) // 2
                candidate = rows[start : start + candidate_count]
                height = self._table(
                    [header, *candidate],
                    widths,
                    0,
                    0,
                    font_size=5.1,
                    row_padding=1.4,
                    max_height=available_height,
                    draw=False,
                )
                if height <= available_height:
                    rows_that_fit = candidate_count
                    low = candidate_count + 1
                else:
                    high = candidate_count - 1

            # Uma linha isolada sempre deve avanÃ§ar a paginaÃ§Ã£o. Na prÃ¡tica,
            # as dimensÃµes do anexo deixam uma margem muito maior que isso.
            rows_that_fit = max(rows_that_fit, 1)
            pages.append(rows[start : start + rows_that_fit])
            start += rows_that_fit

        return pages

    def _machine_annex(self, frame: pd.DataFrame, eyebrow: str, title: str, code: str) -> None:
        rows = self._annex_rows(frame)
        header = [
            "Número de série",
            "Modelo",
            "Grupo",
            "Idade",
            "Reparações",
            "Anos c/ reparo",
            "Custo c/ impostos",
            "Índice",
            "Status no cenário",
            "Motivo principal",
        ]
        widths = [53, 48, 45, 31, 40, 42, 63, 35, 66, 72]
        table_top = PAGE_H - 190
        table_bottom = 55
        available_height = table_top - table_bottom
        pages = self._paginate_annex_rows(rows, header, widths, available_height)
        total_pages = len(pages)
        for page_index, page_rows in enumerate(pages):
            self._logo()
            self.c.setFillColor(MUTED)
            self.c.setFont("Helvetica", 7)
            self.c.drawRightString(PAGE_W - MARGIN, PAGE_H - 42, f"ANEXO {code}")
            self.c.drawRightString(PAGE_W - MARGIN, PAGE_H - 57, title)
            self.c.setFillColor(RED)
            self.c.setFont("Helvetica", 8)
            self.c.drawString(MARGIN, PAGE_H - 92, eyebrow)
            self.c.setFillColor(TEXT)
            self.c.setFont("Helvetica-Bold", 18)
            self.c.drawString(MARGIN, PAGE_H - 125, title)
            self.c.setFillColor(MUTED)
            self.c.setFont("Helvetica", 7)
            self.c.drawRightString(PAGE_W - MARGIN, PAGE_H - 125, f"Página {page_index + 1} de {total_pages}")
            intro = (
                f"Tabela com {_number(len(frame))} máquinas, ordenada pelo índice de prioridade. "
                "A seleção deve ser validada em campo antes da definição comercial final."
            )
            self._paragraph(intro, MARGIN, PAGE_H - 160, CONTENT_W, 35, size=8, leading=10)
            self._table(
                [header, *page_rows],
                widths,
                MARGIN,
                table_top,
                font_size=5.1,
                row_padding=1.4,
                max_height=available_height,
            )
            self._new_page(f"Anexo {code} - {title}")


def gerar_manual_metodologia_pdf(*, config: PdfReportConfig) -> bytes:
    """Gera em memória o manual v2 usado como Anexo E do relatório."""
    config.validate()
    return generator_manual.generate_manual_bytes()


def _append_pdf(base_pdf: bytes, annex_pdf: bytes) -> bytes:
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(base_pdf)))
    writer.append(PdfReader(BytesIO(annex_pdf)))
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def gerar_relatorio_pdf(
    *,
    base: pd.DataFrame,
    df_ams: pd.DataFrame,
    anos: Iterable[int],
    config: PdfReportConfig,
    projetar_ano_parcial: bool = False,
    dashboard_source: pd.DataFrame | None = None,
) -> bytes:
    """Gera o relatório completo em memória e retorna os bytes do PDF.

    Parameters
    ----------
    base:
        Base analítica já filtrada e priorizada pelo Dashboard.
    df_ams:
        Histórico AMS usado para a série anual.
    anos:
        Anos atualmente selecionados no filtro do Dashboard.
    config:
        Dados variáveis do cliente e parâmetros de geração.
    projetar_ano_parcial:
        Mantém a mesma opção do Dashboard para anualização do último ano.
    dashboard_source:
        Base do parque antes da priorização, usada para reproduzir no Anexo A
        a aba de qualidade e conciliação das fontes.
    """

    config.validate()
    data = _prepare_data(
        base,
        df_ams,
        anos,
        config,
        projetar_ano_parcial=projetar_ano_parcial,
        dashboard_source=dashboard_source,
    )
    output = BytesIO()
    renderer = _ReportRenderer(output, data, config)
    renderer.build()
    report = output.getvalue()
    if config.incluir_manual_metodologia:
        manual = gerar_manual_metodologia_pdf(config=config)
        return _append_pdf(report, manual)
    return report
