"""
Custo de remediação.

Medir o gap sem precificar a correção deixa o relatório sem consequência. Três
políticas, com custos muito diferentes, e a diferença entre elas é o que
transforma o tema em decisão de orçamento.

    nivelamento individual  sobe quem está abaixo do previsto para o próprio
                            perfil. Mais caro e o único que corrige casos.
    ajuste uniforme         aplica o mesmo percentual a todo o grupo. Mais
                            barato, fecha a média e não corrige ninguém em
                            particular.
    nivelamento por faixa   sobe quem está abaixo do piso da faixa do cargo.
                            Resolve um problema adjacente, não o gap.

O nivelamento individual é o único defensável em auditoria, e é sempre o mais
caro. Apresentar só o ajuste uniforme, porque cabe no orçamento, é o erro
clássico deste tema.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .gap import CONTROLES_COM_CARGO, matriz


@dataclass(frozen=True)
class ParametrosRemediacao:
    fator_encargos: float = 1.94
    meses: int = 12
    teto_ajuste_individual: float = 0.25   # limite por pessoa em uma rodada


def salario_previsto(df: pd.DataFrame, coluna_grupo: str,
                     referencia: str) -> np.ndarray:
    """Salário que a pessoa teria com os coeficientes do grupo de referência.

    Estima o modelo apenas no grupo de referência e aplica a todos. É o
    contrafactual 'e se as regras de remuneração do grupo majoritário
    valessem para todo mundo'.
    """
    X, _ = matriz(df, CONTROLES_COM_CARGO)
    y = np.log(df["salario"].to_numpy(dtype=float))
    mask = (df[coluna_grupo] == referencia).to_numpy()

    beta, *_ = np.linalg.lstsq(X[mask], y[mask], rcond=None)
    return np.exp(X @ beta)


def nivelamento_individual(df: pd.DataFrame, coluna_grupo: str,
                           referencia: str, grupos_alvo: list[str],
                           p: ParametrosRemediacao) -> pd.DataFrame:
    out = df.copy()
    out["salario_previsto"] = salario_previsto(out, coluna_grupo, referencia)
    out["deficit"] = (out["salario_previsto"] - out["salario"]).clip(lower=0)
    out["deficit"] = np.minimum(
        out["deficit"], out["salario"] * p.teto_ajuste_individual
    )
    out.loc[~out[coluna_grupo].isin(grupos_alvo), "deficit"] = 0.0
    out["custo_anual"] = out["deficit"] * p.meses * p.fator_encargos
    return out


def resumir_politicas(df: pd.DataFrame, coluna_grupo: str, referencia: str,
                      grupos_alvo: list[str], gap_nao_explicado: float,
                      p: ParametrosRemediacao | None = None) -> pd.DataFrame:
    p = p or ParametrosRemediacao()
    nivelado = nivelamento_individual(df, coluna_grupo, referencia, grupos_alvo, p)
    alvo = nivelado[nivelado[coluna_grupo].isin(grupos_alvo)]

    # Ajuste uniforme: fecha a média do grupo com o percentual do gap não
    # explicado. Barato porque não mexe em quem já está acima.
    custo_uniforme = (
        alvo["salario"].sum() * (np.exp(gap_nao_explicado) - 1)
        * p.meses * p.fator_encargos
    )

    # Nivelamento ao piso da faixa: usa compa-ratio como referência.
    abaixo_piso = alvo[alvo["compa_ratio"] < 0.80]
    custo_piso = (
        (abaixo_piso["salario"] / abaixo_piso["compa_ratio"] * 0.80
         - abaixo_piso["salario"]).sum() * p.meses * p.fator_encargos
    )

    folha_anual = df["salario"].sum() * p.meses * p.fator_encargos

    linhas = [
        {
            "politica": "nivelamento individual",
            "pessoas_ajustadas": int((alvo["deficit"] > 0).sum()),
            "custo_anual": float(alvo["custo_anual"].sum()),
            "ajuste_medio_pct": float(
                (alvo.loc[alvo["deficit"] > 0, "deficit"]
                 / alvo.loc[alvo["deficit"] > 0, "salario"]).mean()
            ),
            "corrige_casos_individuais": True,
        },
        {
            "politica": "ajuste uniforme no grupo",
            "pessoas_ajustadas": int(len(alvo)),
            "custo_anual": float(custo_uniforme),
            "ajuste_medio_pct": float(np.exp(gap_nao_explicado) - 1),
            "corrige_casos_individuais": False,
        },
        {
            "politica": "nivelamento ao piso da faixa",
            "pessoas_ajustadas": int(len(abaixo_piso)),
            "custo_anual": float(custo_piso),
            "ajuste_medio_pct": float(
                (0.80 / abaixo_piso["compa_ratio"] - 1).mean()
            ) if len(abaixo_piso) else 0.0,
            "corrige_casos_individuais": False,
        },
    ]
    out = pd.DataFrame(linhas)
    out["pct_da_folha_anual"] = (out["custo_anual"] / folha_anual).round(5)
    return out.round(4)
