"""Pipeline da análise de equidade salarial."""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .data import montar, panorama, representacao_por_faixa
from .gap import parcela_de_carreira, rodar_duas_especificacoes
from .remediation import ParametrosRemediacao, resumir_politicas

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)


def main() -> None:
    ap = argparse.ArgumentParser(description="Análise de equidade salarial")
    ap.add_argument("--base", default="data_base")
    ap.add_argument("--config", default="config/analise.yaml")
    ap.add_argument("--saida", default="reports")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    df = montar(args.base, cfg["mes_referencia"])
    print(f"\nQuadro ativo em {df['data_referencia'].iloc[0]:%b/%Y}: {len(df)} pessoas")

    decomposicoes, linhas_gap, remediacoes = [], [], []

    for recorte in cfg["recortes"]:
        col, ref = recorte["coluna"], recorte["referencia"]
        print(f"\n{'=' * 74}\nRECORTE: {col} (referência: {ref})\n{'=' * 74}")
        print(panorama(df, col).to_string(index=False))

        for grupo in recorte["comparados"]:
            sub = df[df[col].isin([ref, grupo])]
            if (sub[col] == grupo).sum() < 50:
                print(f"\n{grupo}: amostra insuficiente, análise omitida.")
                continue

            decs = rodar_duas_especificacoes(df, col, ref, grupo, rng,
                                             cfg["bootstrap"])
            decomposicoes.extend(decs)
            for d in decs:
                linhas_gap.append({"recorte": col, **d.como_linha()})

            print(f"\n--- {grupo} vs {ref} ---")
            print(pd.DataFrame([d.como_linha() for d in decs]).to_string(index=False))
            print(f"Parcela atribuível à progressão de carreira: "
                  f"{parcela_de_carreira(decs):+.4f} em log-salário")

            print("\nRepresentação por grade:")
            print(representacao_por_faixa(df, col, grupo).to_string(index=False))

            spec_cargo = [d for d in decs if "mesmo cargo" in d.especificacao][0]
            pol = resumir_politicas(
                df, col, ref, [grupo], spec_cargo.nao_explicado,
                ParametrosRemediacao(**cfg["remediacao"]),
            )
            pol.insert(0, "grupo", grupo)
            pol.insert(0, "recorte", col)
            remediacoes.append(pol)
            print("\nCusto de remediação:")
            print(pol.to_string(index=False))

    gaps = pd.DataFrame(linhas_gap)
    remed = pd.concat(remediacoes, ignore_index=True) if remediacoes else pd.DataFrame()

    gaps.to_csv(saida / "decomposicao_gap.csv", index=False)
    remed.to_csv(saida / "custo_remediacao.csv", index=False)

    # Fato para o Power BI: um registro por pessoa, sem nome, com o déficit.
    from .remediation import nivelamento_individual
    fato = nivelamento_individual(
        df, "genero", "Masculino", ["Feminino"],
        ParametrosRemediacao(**cfg["remediacao"]),
    )
    colunas = [
        "matricula", "data_referencia", "id_area", "diretoria", "gerencia",
        "id_cargo", "grade", "familia_cargo", "genero", "raca_cor",
        "escolaridade", "salario", "compa_ratio", "meses_de_casa",
        "performance", "salario_previsto", "deficit", "custo_anual",
    ]
    fato[colunas].to_parquet(saida / "fato_equidade.parquet", index=False)

    print(f"\n\nArtefatos em {saida.resolve()}")


if __name__ == "__main__":
    main()
