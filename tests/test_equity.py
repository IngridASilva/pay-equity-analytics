"""Testes da análise de equidade.

Alguns validam o método contra o gabarito do gerador: a base foi produzida com
penalidade de entrada conhecida, então a decomposição tem um alvo a recuperar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from equity.data import montar, panorama, suprimir
from equity.gap import CONTROLES_BASE, CONTROLES_COM_CARGO, decompor, rodar_duas_especificacoes
from equity.remediation import ParametrosRemediacao, resumir_politicas

# Valores injetados em config/params.yaml do gerador da base.
GABARITO_ENTRADA = {"Feminino": 0.045, "Preta": 0.030, "Parda": 0.020}


@pytest.fixture(scope="module")
def df():
    return montar("data_base")


@pytest.fixture(scope="module")
def rng():
    return np.random.default_rng(7)


def test_supressao_anula_grupos_pequenos():
    t = pd.DataFrame({"grupo": ["a", "b"], "n": [3, 40],
                      "salario_mediano": [5000.0, 6000.0]})
    out = suprimir(t)
    assert np.isnan(out.loc[0, "salario_mediano"])
    assert out.loc[1, "salario_mediano"] == 6000.0
    assert out["suprimido"].tolist() == [True, False]


def test_panorama_nao_expoe_grupo_pequeno(df):
    p = panorama(df, "raca_cor")
    pequenos = p[p["n"] < 5]
    if len(pequenos):
        assert pequenos["salario_mediano"].isna().all()


def test_decomposicao_soma_ao_gap_bruto(df, rng):
    d = decompor(df, "genero", "Masculino", "Feminino",
                 CONTROLES_COM_CARGO, "teste", rng, n_bootstrap=0)
    assert abs((d.explicado + d.nao_explicado) - d.gap_bruto) < 1e-8


def test_recupera_a_penalidade_injetada(df, rng):
    """O gap não explicado precisa conter a penalidade de entrada real.

    Este é o teste que separa um método que funciona de um que produz números
    bonitos: a base tem 4,5% de penalidade de entrada para mulheres no mesmo
    cargo, e o intervalo de confiança precisa alcançá-la.
    """
    decs = rodar_duas_especificacoes(df, "genero", "Masculino", "Feminino",
                                     rng, n_bootstrap=300)
    cargo = [d for d in decs if "mesmo cargo" in d.especificacao][0]
    alvo = GABARITO_ENTRADA["Feminino"]
    inf, sup = cargo.ic_nao_explicado
    assert inf > 0, "penalidade injetada não foi detectada"
    assert sup >= alvo * 0.8, (
        f"IC [{inf:.4f}, {sup:.4f}] não alcança o gabarito de {alvo}"
    )


def test_controlar_por_grade_reduz_o_nao_explicado(df, rng):
    """Incluir grade absorve o teto de vidro para dentro do explicado.

    Se este teste quebrar, o argumento central da documentação caiu junto.
    """
    decs = rodar_duas_especificacoes(df, "genero", "Masculino", "Feminino",
                                     rng, n_bootstrap=0)
    cargo = [d for d in decs if "mesmo cargo" in d.especificacao][0]
    carreira = [d for d in decs if "carreira" in d.especificacao][0]
    assert carreira.nao_explicado > cargo.nao_explicado


def test_nivelamento_individual_custa_mais_que_uniforme(df):
    pol = resumir_politicas(df, "genero", "Masculino", ["Feminino"], 0.03,
                            ParametrosRemediacao())
    ind = pol[pol["politica"] == "nivelamento individual"]["custo_anual"].iloc[0]
    uni = pol[pol["politica"] == "ajuste uniforme no grupo"]["custo_anual"].iloc[0]
    assert ind > uni


def test_remediacao_nao_toca_grupo_de_referencia(df):
    from equity.remediation import nivelamento_individual
    out = nivelamento_individual(df, "genero", "Masculino", ["Feminino"],
                                 ParametrosRemediacao())
    assert out.loc[out["genero"] == "Masculino", "deficit"].eq(0).all()


def test_controles_nao_incluem_variavel_de_grupo():
    """Gênero e raça/cor são o que se mede, nunca controle."""
    proibidas = {"genero", "raca_cor"}
    assert not proibidas & set(CONTROLES_BASE)
    assert not proibidas & set(CONTROLES_COM_CARGO)
