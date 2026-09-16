# Painel de equidade salarial

Três telas. A regra que atravessa todas: **nenhuma métrica de remuneração
aparece para grupo com menos de 5 pessoas.**

## Tela 1 — Panorama

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Equidade salarial · dez/2025              [Diretoria ▾] [Recorte ▾]     │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────────────┐ │
│ │ GAP BRUTO       │ │ NÃO EXPLICADO   │ │ CUSTO DE CORREÇÃO            │ │
│ │    15,3%        │ │  3,1%           │ │  R$ 12,7 mi/ano              │ │
│ │                 │ │ IC [1,7%; 4,6%] │ │  2,9% da folha               │ │
│ └─────────────────┘ └─────────────────┘ └──────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────┤
│  Decomposição (cascata)          │  Representação por grade              │
│                                  │                                       │
│  Bruto 15,3%                     │   G1 ████████████ 49,7%               │
│    └ composição −12,1%           │   G3 ███████████  47,0%               │
│        └ não explicado 3,1%      │   G5 █████████    38,8%               │
│                                  │   G7 ████████     35,8%               │
└──────────────────────────────────────────────────────────────────────────┘
```

O cartão do gap não explicado exibe o intervalo de confiança **dentro do
cartão**, não no tooltip. Ponto sem intervalo em tema regulatório é como o
número vira manchete indefensável.

## Tela 2 — As duas especificações

Lado a lado, com a diferença nomeada como "parcela atribuível à progressão de
carreira". Nunca publique uma sem a outra.

```dax
Gap Não Explicado =
SELECTEDVALUE ( fato_gap[nao_explicado] )

Rótulo do Gap =
VAR G   = [Gap Não Explicado]
VAR Inf = SELECTEDVALUE ( fato_gap[ic95_inferior] )
VAR Sup = SELECTEDVALUE ( fato_gap[ic95_superior] )
RETURN
    IF (
        Inf <= 0 && Sup >= 0,
        "Não distinguível de zero nesta amostra",
        FORMAT ( G, "0,0%" ) & "  [" & FORMAT ( Inf, "0,0%" )
            & " a " & FORMAT ( Sup, "0,0%" ) & "]"
    )
```

A medida acima se recusa a exibir um número quando o intervalo contém zero. É
uma decisão de produto, não de estatística: se a leitura correta é "não dá
para afirmar", o painel precisa dizer isso em vez de mostrar 0,4% e deixar o
leitor concluir sozinho.

## Tela 3 — Simulador de remediação

Controle para escolher a política e o teto de ajuste individual, com o custo
respondendo em tempo real.

```dax
p_teto_ajuste = GENERATESERIES(0.05, 0.40, 0.05)
```

```dax
Custo de Remediação =
VAR Teto = SELECTEDVALUE ( p_teto_ajuste[p_teto_ajuste], 0.25 )
RETURN
    SUMX (
        fato_equidade,
        MIN ( fato_equidade[deficit], fato_equidade[salario] * Teto )
    ) * 12 * 1.94
```

```dax
Pessoas Corrigidas =
CALCULATE (
    DISTINCTCOUNT ( fato_equidade[matricula] ),
    KEEPFILTERS ( fato_equidade[deficit] > 0 )
)
```

## Supressão

Toda medida de remuneração passa por esta guarda:

```dax
_N Mínimo = 5

Salário Mediano (protegido) =
VAR N = DISTINCTCOUNT ( fato_equidade[matricula] )
RETURN
    IF ( N < [_N Mínimo], BLANK (), MEDIANX ( fato_equidade, fato_equidade[salario] ) )
```

## RLS

Duas funções e um workspace separado. A visão nominal fica restrita à equipe
que produz o relatório de transparência; gestores de linha recebem apenas
agregados da própria estrutura, com a mesma supressão aplicada.

Não resolva isso escondendo colunas no relatório: o usuário exporta os dados
subjacentes.
