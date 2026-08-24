from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashtoolsrecomendation import auth
from dashtoolsrecomendation.services.fleet_renewal import (
    FleetRenewalScenario,
    build_cash_flow,
    build_maintenance_risk_scenarios,
    summarize_scenario,
)


def _currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', '_').replace('.', ',').replace('_', '.')}"


def _percent(value: float) -> str:
    return f"{value * 100:,.1f}%".replace(",", "_").replace(".", ",").replace("_", ".")


def show() -> None:
    if not auth.has_role("adm"):
        st.error(
            "Esta análise está disponível somente para administradores.",
            icon=":material/lock:",
        )
        st.stop()

    st.info(
        "Esta página compara modalidades de aquisição. Ela não trata preservação "
        "de caixa como economia nem usa o custo interno da Hilti como custo do cliente.",
        icon=":material/info:",
    )

    with st.form("renewal_decision_inputs", border=True):
        st.subheader("Premissas do cenário")
        equipment_quantity = st.number_input(
            "Equipamentos no cenário",
            min_value=1,
            value=7,
            step=1,
            help="Os valores financeiros abaixo devem representar este conjunto.",
        )
        purchase_col, fleet_col, adjustment_col = st.columns(3)
        with purchase_col:
            purchase_total = st.number_input(
                "Valor total da compra",
                min_value=0.0,
                value=112_822.76,
                step=1_000.0,
                format="%.2f",
            )
            purchase_months = st.number_input(
                "Prazo da compra (meses)",
                min_value=1,
                value=12,
                step=1,
            )
        with fleet_col:
            fleet_monthly_payment = st.number_input(
                "Mensalidade da Gestão de Frotas",
                min_value=0.0,
                value=5_200.88,
                step=100.0,
                format="%.2f",
            )
            fleet_months = st.number_input(
                "Prazo da Gestão de Frotas (meses)",
                min_value=1,
                value=36,
                step=1,
            )
        with adjustment_col:
            residual_value = st.number_input(
                "Valor residual estimado da compra",
                min_value=0.0,
                value=0.0,
                step=1_000.0,
                format="%.2f",
                help="Valor estimado do ativo ao final do horizonte analisado.",
            )
            uncovered_fleet_costs = st.number_input(
                "Despesas não cobertas na frota",
                min_value=0.0,
                value=0.0,
                step=500.0,
                format="%.2f",
            )
        st.form_submit_button(
            "Atualizar análise",
            type="primary",
            icon=":material/calculate:",
            width="stretch",
        )

    scenario = FleetRenewalScenario(
        purchase_total=float(purchase_total),
        purchase_months=int(purchase_months),
        fleet_monthly_payment=float(fleet_monthly_payment),
        fleet_months=int(fleet_months),
        residual_value=float(residual_value),
        uncovered_fleet_costs=float(uncovered_fleet_costs),
    )
    summary = summarize_scenario(scenario)

    st.subheader("Leitura executiva")
    metrics = st.columns(4, border=True)
    metrics[0].metric("Total da compra", _currency(summary["purchase_total"]))
    metrics[1].metric("Total da frota", _currency(summary["fleet_total"]))
    metrics[2].metric(
        "Premium da frota",
        _currency(summary["premium"]),
        _percent(summary["premium_rate"]),
        delta_color="off",
    )
    metrics[3].metric(
        "Caixa preservado no 1º ano",
        _currency(summary["liquidity_preserved_first_year"]),
        help="Diferença de desembolso no período; não representa economia total.",
    )

    comparison = pd.DataFrame(
        {
            "Aspecto": [
                "Equipamentos",
                "Pagamento",
                "Total nominal",
                "Desembolso no 1º ano",
                "Reparações",
                "Perda ou extravio",
                "Propriedade do ativo",
            ],
            "Compra": [
                str(equipment_quantity),
                f"{scenario.purchase_months} × {_currency(summary['purchase_monthly'])}",
                _currency(summary["purchase_total"]),
                _currency(summary["purchase_first_year"]),
                "Risco financeiro do cliente",
                "Risco do cliente",
                "Sim; considerar valor residual",
            ],
            "Gestão de Frotas": [
                str(equipment_quantity),
                f"{scenario.fleet_months} × {_currency(scenario.fleet_monthly_payment)}",
                _currency(summary["fleet_total"]),
                _currency(summary["fleet_first_year"]),
                "Cobertura conforme condições contratuais",
                "Compartilhamento conforme contrato",
                "Conforme o modelo contratual",
            ],
        }
    )
    st.dataframe(comparison, hide_index=True)
    st.caption(
        "A Gestão de Frotas não é apresentada como a alternativa de menor desembolso "
        "total. O premium remunera o serviço, a previsibilidade e a transferência de "
        "riscos definida no contrato."
    )

    st.subheader("Fluxo de caixa acumulado")
    cash_flow = build_cash_flow(scenario)
    chart_data = cash_flow[
        ["Mês", "Compra acumulada", "Frota acumulada"]
    ].melt(
        id_vars="Mês",
        var_name="Modalidade",
        value_name="Desembolso acumulado",
    )
    cash_flow_chart = (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("Mês:Q", title="Mês", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y(
                "Desembolso acumulado:Q",
                title="Desembolso acumulado (R$)",
                axis=alt.Axis(format="~s"),
            ),
            color=alt.Color(
                "Modalidade:N",
                scale=alt.Scale(
                    domain=["Compra acumulada", "Frota acumulada"],
                    range=["#ffffff", "#ef4056"],
                ),
                legend=alt.Legend(title=None, orient="bottom"),
            ),
            tooltip=[
                alt.Tooltip("Mês:Q", format=".0f"),
                alt.Tooltip("Modalidade:N"),
                alt.Tooltip(
                    "Desembolso acumulado:Q",
                    title="Desembolso",
                    format=",.2f",
                ),
            ],
        )
        .properties(height=340)
        .configure(background="transparent")
        .configure_view(stroke=None)
        .configure_axis(
            domainColor="#d6d6e7",
            gridColor="#6b676d",
            labelColor="#f7f7fa",
            titleColor="#ffffff",
        )
        .configure_legend(
            labelColor="#ffffff",
            titleColor="#ffffff",
        )
    )
    st.altair_chart(cash_flow_chart, width="stretch")

    with st.expander("Sensibilidade do risco de manutenção na compra", expanded=True):
        expected_cost = st.number_input(
            "Custo de manutenção de referência no horizonte",
            min_value=0.0,
            value=16_192.0,
            step=1_000.0,
            format="%.2f",
            help=(
                "O valor inicial reproduz a referência histórica descrita no estudo. "
                "Substitua-o por uma estimativa validada para o cenário em negociação."
            ),
        )
        risk_scenarios = build_maintenance_risk_scenarios(expected_cost)
        risk_scenarios["Compra ajustada"] = (
            summary["purchase_net_of_residual"]
            + risk_scenarios["Custo de manutenção da compra"]
        )
        risk_scenarios["Diferença para a frota"] = (
            summary["fleet_total"] - risk_scenarios["Compra ajustada"]
        )
        st.dataframe(
            risk_scenarios,
            hide_index=True,
            column_config={
                "Fator": st.column_config.NumberColumn(format="%.1f ×"),
                "Custo de manutenção da compra": st.column_config.NumberColumn(
                    format="R$ %.2f"
                ),
                "Compra ajustada": st.column_config.NumberColumn(format="R$ %.2f"),
                "Diferença para a frota": st.column_config.NumberColumn(
                    format="R$ %.2f"
                ),
            },
        )
        st.warning(
            "Os cenários são uma análise de sensibilidade, não uma previsão de falha "
            "nem uma probabilidade estatística. Custos indiretos, capital e sinistros "
            "devem ser incluídos quando houver dados confiáveis.",
            icon=":material/warning:",
        )

    st.subheader("Enquadramento da decisão")
    decision = st.segmented_control(
        "Qual é a objeção principal do cliente?",
        options=["Redução real do parque", "Substituir por parque próprio"],
        default="Redução real do parque",
        width="stretch",
    )
    if decision == "Redução real do parque":
        st.markdown(
            "**Próxima análise:** valide demanda, utilização e quantidade necessária. "
            "A decisão pode ser renovar menos posições, e não escolher entre compra e frota."
        )
    else:
        st.markdown(
            "**Próxima análise:** compare confiabilidade, idade, disponibilidade, riscos "
            "reassumidos e pressão de caixa do parque próprio antes de decidir pela modalidade."
        )
