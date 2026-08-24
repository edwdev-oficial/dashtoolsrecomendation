from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FleetRenewalScenario:
    """Premissas financeiras para comparar compra e Gestão de Frotas."""

    purchase_total: float
    purchase_months: int
    fleet_monthly_payment: float
    fleet_months: int
    residual_value: float = 0.0
    uncovered_fleet_costs: float = 0.0

    def validate(self) -> None:
        if self.purchase_total < 0:
            raise ValueError("O valor da compra não pode ser negativo.")
        if self.purchase_months <= 0:
            raise ValueError("O prazo da compra deve ser maior que zero.")
        if self.fleet_monthly_payment < 0:
            raise ValueError("A mensalidade da frota não pode ser negativa.")
        if self.fleet_months <= 0:
            raise ValueError("O prazo da frota deve ser maior que zero.")
        if self.residual_value < 0 or self.uncovered_fleet_costs < 0:
            raise ValueError("Valores residuais e custos devem ser não negativos.")


def summarize_scenario(scenario: FleetRenewalScenario) -> dict[str, float]:
    """Calcula os indicadores financeiros sem chamar preservação de caixa de economia."""
    scenario.validate()
    purchase_monthly = scenario.purchase_total / scenario.purchase_months
    fleet_total = (
        scenario.fleet_monthly_payment * scenario.fleet_months
        + scenario.uncovered_fleet_costs
    )
    purchase_first_year = purchase_monthly * min(12, scenario.purchase_months)
    fleet_first_year = scenario.fleet_monthly_payment * min(
        12, scenario.fleet_months
    )
    premium = fleet_total - scenario.purchase_total

    return {
        "purchase_monthly": purchase_monthly,
        "purchase_total": scenario.purchase_total,
        "fleet_total": fleet_total,
        "premium": premium,
        "premium_rate": (
            premium / scenario.purchase_total
            if scenario.purchase_total > 0
            else 0.0
        ),
        "purchase_first_year": purchase_first_year,
        "fleet_first_year": fleet_first_year,
        "liquidity_preserved_first_year": (
            purchase_first_year - fleet_first_year
        ),
        "purchase_net_of_residual": (
            scenario.purchase_total - scenario.residual_value
        ),
    }


def build_cash_flow(scenario: FleetRenewalScenario) -> pd.DataFrame:
    """Gera desembolsos mensais e acumulados durante todo o horizonte."""
    scenario.validate()
    horizon = max(scenario.purchase_months, scenario.fleet_months)
    purchase_monthly = scenario.purchase_total / scenario.purchase_months

    frame = pd.DataFrame({"Mês": range(1, horizon + 1)})
    frame["Compra no mês"] = frame["Mês"].le(
        scenario.purchase_months
    ).astype(float) * purchase_monthly
    frame["Frota no mês"] = frame["Mês"].le(
        scenario.fleet_months
    ).astype(float) * scenario.fleet_monthly_payment
    frame["Compra acumulada"] = frame["Compra no mês"].cumsum()
    frame["Frota acumulada"] = frame["Frota no mês"].cumsum()

    if scenario.uncovered_fleet_costs:
        frame.loc[frame.index[-1], "Frota no mês"] += (
            scenario.uncovered_fleet_costs
        )
        frame["Frota acumulada"] = frame["Frota no mês"].cumsum()

    return frame


def build_maintenance_risk_scenarios(
    expected_cost: float,
    low_factor: float = 0.5,
    severe_factor: float = 2.0,
) -> pd.DataFrame:
    """Cria sensibilidades simples; não representa previsão probabilística."""
    if expected_cost < 0:
        raise ValueError("O custo esperado não pode ser negativo.")
    if low_factor < 0 or severe_factor < 0:
        raise ValueError("Os fatores dos cenários não podem ser negativos.")

    return pd.DataFrame(
        {
            "Cenário": ["Baixo", "Referência", "Severo"],
            "Fator": [low_factor, 1.0, severe_factor],
            "Custo de manutenção da compra": [
                expected_cost * low_factor,
                expected_cost,
                expected_cost * severe_factor,
            ],
        }
    )
