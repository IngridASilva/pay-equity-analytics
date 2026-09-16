"""
Decomposição de gap salarial.

O gap bruto não é a resposta, e o gap ajustado sozinho também não. A pergunta
que importa é: quanto da diferença vem de as pessoas ocuparem posições
diferentes, e quanto vem de receberem menos na mesma posição.

Método: decomposição de Oaxaca-Blinder em duas partes, com coeficientes de
referência combinados (Neumark), sobre o log do salário.

    gap = (X̄_A − X̄_B)'β*          <- explicado, composição
        + X̄_A'(β_A − β*) + X̄_B'(β* − β_B)   <- não explicado

A escolha dos controles não é técnica, é política
-------------------------------------------------
Incluir `grade` entre os controles responde "mesmo cargo, mesmo salário?".
Excluir responde "a carreira inteira foi justa?".

São perguntas diferentes e dão respostas diferentes, porque se a promoção for
ela mesma enviesada, controlar por grade **absorve a discriminação para dentro
do explicado** e faz o número parecer melhor do que é.

Por isso este módulo sempre roda as duas especificações e reporta a diferença
entre elas, que é a parcela atribuível à progressão de carreira. Apresentar só
a primeira é a forma mais comum e mais elegante de subestimar um gap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Controles de produtividade observável, sem grade.
CONTROLES_BASE = [
    "log_tempo_casa", "idade", "performance", "escolaridade_anos",
    "familia_cargo", "modelo_trabalho", "uf",
]

# Especificação "mesmo cargo": acrescenta senioridade formal.
CONTROLES_COM_CARGO = CONTROLES_BASE + ["grade"]

CATEGORICAS = ["familia_cargo", "modelo_trabalho", "uf"]


@dataclass
class Decomposicao:
    especificacao: str
    grupo_referencia: str
    grupo_comparado: str
    n_referencia: int
    n_comparado: int
    gap_bruto: float          # diferença de log-salário médio
    explicado: float
    nao_explicado: float
    ic_nao_explicado: tuple[float, float] | None = None

    @property
    def pct_explicado(self) -> float:
        return float(self.explicado / self.gap_bruto) if self.gap_bruto else np.nan

    def como_linha(self) -> dict:
        ic = self.ic_nao_explicado
        return {
            "especificacao": self.especificacao,
            "grupo": self.grupo_comparado,
            "n": self.n_comparado,
            "gap_bruto": round(self.gap_bruto, 4),
            "explicado": round(self.explicado, 4),
            "nao_explicado": round(self.nao_explicado, 4),
            "ic95_inferior": round(ic[0], 4) if ic else None,
            "ic95_superior": round(ic[1], 4) if ic else None,
            "pct_explicado": round(self.pct_explicado, 3),
            "significante": (
                None if ic is None else not (ic[0] <= 0 <= ic[1])
            ),
        }


def matriz(df: pd.DataFrame, controles: list[str]) -> tuple[np.ndarray, list[str]]:
    """Matriz de desenho com intercepto e dummies, categorias alinhadas."""
    cats = [c for c in controles if c in CATEGORICAS]
    X = pd.get_dummies(df[controles], columns=cats, drop_first=True, dtype=float)
    X.insert(0, "intercepto", 1.0)
    return X.to_numpy(dtype=float), list(X.columns)


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def decompor(
    df: pd.DataFrame,
    coluna_grupo: str,
    referencia: str,
    comparado: str,
    controles: list[str],
    especificacao: str,
    rng: np.random.Generator | None = None,
    n_bootstrap: int = 500,
) -> Decomposicao:
    """Oaxaca-Blinder com coeficientes de referência combinados."""
    sub = df[df[coluna_grupo].isin([referencia, comparado])].copy()

    # Colunas alinhadas entre os dois grupos: dummies precisam da mesma base.
    X_todos, _ = matriz(sub, controles)
    y = np.log(sub["salario"].to_numpy(dtype=float))
    eh_ref = (sub[coluna_grupo] == referencia).to_numpy()

    def calcular(X: np.ndarray, y: np.ndarray, mask: np.ndarray) -> tuple[float, float, float]:
        Xa, ya = X[mask], y[mask]
        Xb, yb = X[~mask], y[~mask]
        beta_a, beta_b = _ols(Xa, ya), _ols(Xb, yb)
        beta_pool = _ols(X, y)

        xa, xb = Xa.mean(axis=0), Xb.mean(axis=0)
        gap = float(ya.mean() - yb.mean())
        explicado = float((xa - xb) @ beta_pool)
        nao_explicado = float(xa @ (beta_a - beta_pool) + xb @ (beta_pool - beta_b))
        return gap, explicado, nao_explicado

    gap, exp, nexp = calcular(X_todos, y, eh_ref)

    ic = None
    if rng is not None and n_bootstrap:
        # Bootstrap não paramétrico. Com ~1.700 pessoas o gap não explicado é
        # estimado com incerteza relevante, e reportar o ponto sem intervalo
        # é o que produz manchete indefensável.
        amostras = []
        n = len(y)
        for _ in range(n_bootstrap):
            idx = rng.integers(0, n, n)
            m = eh_ref[idx]
            if m.sum() < 30 or (~m).sum() < 30:
                continue
            try:
                amostras.append(calcular(X_todos[idx], y[idx], m)[2])
            except np.linalg.LinAlgError:
                continue
        if len(amostras) > 50:
            ic = (
                float(np.percentile(amostras, 2.5)),
                float(np.percentile(amostras, 97.5)),
            )

    return Decomposicao(
        especificacao=especificacao,
        grupo_referencia=referencia,
        grupo_comparado=comparado,
        n_referencia=int(eh_ref.sum()),
        n_comparado=int((~eh_ref).sum()),
        gap_bruto=gap,
        explicado=exp,
        nao_explicado=nexp,
        ic_nao_explicado=ic,
    )


def rodar_duas_especificacoes(
    df: pd.DataFrame, coluna_grupo: str, referencia: str, comparado: str,
    rng: np.random.Generator, n_bootstrap: int = 500,
) -> list[Decomposicao]:
    """As duas leituras, sempre juntas.

    A diferença entre o não explicado das duas é a parcela do gap que passa
    pela progressão de carreira. Se ela for grande, o problema não está na
    tabela salarial: está em quem é promovido.
    """
    return [
        decompor(df, coluna_grupo, referencia, comparado, CONTROLES_COM_CARGO,
                 "mesmo cargo (controla grade)", rng, n_bootstrap),
        decompor(df, coluna_grupo, referencia, comparado, CONTROLES_BASE,
                 "carreira (grade como resultado)", rng, n_bootstrap),
    ]


def parcela_de_carreira(decomposicoes: list[Decomposicao]) -> float:
    """Quanto do gap não explicado só aparece quando grade sai dos controles."""
    por_spec = {d.especificacao: d.nao_explicado for d in decomposicoes}
    return float(
        por_spec["carreira (grade como resultado)"]
        - por_spec["mesmo cargo (controla grade)"]
    )
