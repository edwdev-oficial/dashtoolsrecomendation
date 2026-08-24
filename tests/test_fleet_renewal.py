from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from dashtoolsrecomendation.services.fleet_renewal import (
    FleetRenewalScenario,
    build_cash_flow,
    build_maintenance_risk_scenarios,
    summarize_scenario,
)


@pytest.fixture
def scenario() -> FleetRenewalScenario:
    return FleetRenewalScenario(
        purchase_total=112_822.76,
        purchase_months=12,
        fleet_monthly_payment=5_200.88,
        fleet_months=36,
    )


def test_summary_reproduces_study_values(scenario: FleetRenewalScenario) -> None:
    result = summarize_scenario(scenario)

    assert result["fleet_total"] == pytest.approx(187_231.68)
    assert result["premium"] == pytest.approx(74_408.92)
    assert result["premium_rate"] == pytest.approx(0.65952047)
    assert result["fleet_first_year"] == pytest.approx(62_410.56)
    assert result["liquidity_preserved_first_year"] == pytest.approx(50_412.20)


def test_cash_flow_stops_purchase_after_month_twelve(
    scenario: FleetRenewalScenario,
) -> None:
    result = build_cash_flow(scenario)

    assert len(result) == 36
    assert result.loc[11, "Compra acumulada"] == pytest.approx(112_822.76)
    assert result.loc[12, "Compra no mês"] == 0
    assert result.loc[35, "Frota acumulada"] == pytest.approx(187_231.68)


def test_maintenance_scenarios_are_explicit_sensitivities() -> None:
    result = build_maintenance_risk_scenarios(16_192)

    assert result["Cenário"].tolist() == ["Baixo", "Referência", "Severo"]
    assert result["Custo de manutenção da compra"].tolist() == [
        8_096,
        16_192,
        32_384,
    ]


def test_invalid_terms_are_rejected() -> None:
    invalid = FleetRenewalScenario(100, 0, 10, 36)

    with pytest.raises(ValueError, match="prazo da compra"):
        summarize_scenario(invalid)


def test_admin_page_renders_metrics_and_cash_flow_chart() -> None:
    app = AppTest.from_string(
        """
import streamlit as st
from dashtoolsrecomendation.pages.fleet_renewal import show

with st.container(key="renewal_decision_tab"):
    show()
"""
    )
    app.session_state["authenticated"] = True
    app.session_state["authenticated_role"] = "adm"

    app.run(timeout=20)

    assert not app.exception
    assert len(app.metric) == 4
    assert len(app.get("vega_lite_chart")) == 1
