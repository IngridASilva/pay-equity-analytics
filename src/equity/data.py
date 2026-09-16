"""
Preparação da base de análise e regras de exposição.

Duas responsabilidades: montar o quadro de referência e impedir que o
resultado exponha indivíduos. A segunda é tão importante quanto a primeira —
um relatório de equidade que permite deduzir o salário de uma pessoa criou um
problema maior que o que resolveu.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

N_MINIMO = 5

ANOS_DE_ESTUDO = {
    "Ensino Médio": 11,
    "Superior Incompleto": 13,
    "Superior Completo": 16,
    "Pós-graduação": 18,
    "Mestrado/Doutorado": 21,
}


def montar(dir_base: str | Path, mes: str | None = None) -> pd.DataFrame:
    """Quadro ativo em um mês de referência, com demografia anexada.

    Analisa-se um corte, não o painel inteiro: repetir a mesma pessoa em 60
    meses infla o n artificialmente e estreita os intervalos de confiança até
    o ponto em que qualquer diferença vira 'significante'.
    """
    d = Path(dir_base)
    snaps = pd.read_parquet(d / "fato_headcount_mensal.parquet")
    colabs = pd.read_parquet(d / "dim_colaborador.parquet")
    areas = pd.read_parquet(d / "dim_area.parquet")

    ref = pd.Timestamp(mes) if mes else snaps["data_referencia"].max()
    df = snaps[snaps["data_referencia"] == ref].copy()

    df = df.merge(
        colabs[["matricula", "genero", "raca_cor", "escolaridade", "uf",
                "data_admissao", "num_dependentes"]],
        on="matricula", how="left",
    ).merge(
        areas[["id_area", "diretoria", "gerencia", "criticidade"]],
        on="id_area", how="left",
    )

    df["escolaridade_anos"] = df["escolaridade"].map(ANOS_DE_ESTUDO)
    df["log_tempo_casa"] = np.log1p(df["meses_de_casa"])
    df["log_salario"] = np.log(df["salario"])
    df["data_referencia"] = ref
    return df


def suprimir(
    tabela: pd.DataFrame, coluna_n: str = "n", n_minimo: int = N_MINIMO,
    colunas_sensiveis: list[str] | None = None,
) -> pd.DataFrame:
    """Anula métricas de remuneração em grupos pequenos demais.

    Com n=3, média salarial deixa de ser estatística e vira exposição
    individual. A supressão precisa valer para toda métrica de remuneração —
    basta uma escapar para o controle inteiro perder sentido.
    """
    out = tabela.copy()
    alvo = colunas_sensiveis or [
        c for c in out.columns
        if any(k in c for k in ["salario", "compa", "gap", "mediana", "media"])
    ]
    pequeno = out[coluna_n] < n_minimo
    out.loc[pequeno, alvo] = np.nan
    out["suprimido"] = pequeno
    return out


def panorama(df: pd.DataFrame, coluna_grupo: str) -> pd.DataFrame:
    """Descritivo por grupo, já suprimido. É o que entra no relatório."""
    g = df.groupby(coluna_grupo)
    t = g.agg(
        n=("matricula", "size"),
        salario_mediano=("salario", "median"),
        compa_ratio_medio=("compa_ratio", "mean"),
        grade_medio=("grade", "mean"),
        meses_de_casa_mediano=("meses_de_casa", "median"),
        pct_lideranca=("grade", lambda s: float((s >= 6).mean())),
    ).reset_index()
    t["participacao"] = (t["n"] / t["n"].sum()).round(4)
    return suprimir(t).round(4)


def representacao_por_faixa(df: pd.DataFrame, coluna_grupo: str,
                            grupo: str) -> pd.DataFrame:
    """Participação do grupo em cada grade. Mostra o teto de vidro."""
    tab = pd.crosstab(df["grade"], df[coluna_grupo])
    if grupo not in tab.columns:
        return pd.DataFrame()
    out = pd.DataFrame({
        "grade": tab.index,
        "n": tab.sum(axis=1).to_numpy(),
        "participacao_grupo": (tab[grupo] / tab.sum(axis=1)).to_numpy(),
    })
    return suprimir(out, colunas_sensiveis=["participacao_grupo"]).round(4)
