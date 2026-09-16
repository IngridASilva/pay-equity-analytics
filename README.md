# pay-equity-analytics

Decomposição de gap salarial por gênero e raça/cor, com intervalos de
confiança, verificação contra gabarito e custo de remediação. Base sintética:
[hr-synthetic-data-br](../hr-synthetic-data-br), cenário com desigualdade
injetada.

```bash
pip install -e ".[dev]"
equity --base data_base --saida reports
```

---

## A pergunta

"Mulheres ganham 15% menos" é uma frase que não sustenta nenhuma decisão. Ela
não distingue entre duas situações completamente diferentes: pessoas ocuparem
posições diferentes, e pessoas receberem menos na mesma posição. A primeira
exige política de carreira, a segunda exige correção de folha, e as duas
custam valores muito distintos.

Este projeto separa as duas e precifica a correção.

## A base tem gabarito

O gerador foi estendido com três mecanismos de desigualdade, com valores
conhecidos:

| Mecanismo | Efeito | Valor injetado (Feminino) |
|---|---|---|
| Segregação ocupacional | gap **explicado** | peso 0,40 em Tecnologia, 1,90 em RH |
| Penalidade de entrada | gap **não explicado** | 4,5% no compa-ratio, mesmo cargo |
| Multiplicador de promoção | teto de vidro | 0,78 da taxa mensal |

O método só é confiável se recupera o que foi injetado. Há teste automatizado
que falha o build se o intervalo de confiança deixar de alcançar o gabarito.

## Resultado: gênero

Quadro ativo em dez/2025, 1.672 pessoas.

| Especificação | Gap bruto | Explicado | Não explicado | IC 95% |
|---|---|---|---|---|
| Mesmo cargo (controla grade) | 0,1527 | 0,1214 (80%) | **0,0313** | [0,0169; 0,0461] |
| Carreira (grade como resultado) | 0,1527 | 0,0936 (61%) | **0,0591** | [0,0190; 0,0947] |

Os dois intervalos excluem zero. O gabarito de 4,5% cai dentro do primeiro
intervalo, e o segundo captura também o efeito acumulado do teto de vidro.

Representação por grade, que mostra o mecanismo:

| Grade | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| % feminino | 49,7 | 45,2 | 47,0 | 49,4 | 38,8 | 41,7 | 35,8 |

Paridade na base, 36% no topo. Nenhuma decisão isolada produziu isso: uma taxa
de promoção 22% menor, mantida por anos, basta.

## A escolha dos controles é a escolha da resposta

Incluir `grade` entre os controles quase **dobra** ou **reduz pela metade** o
gap não explicado, conforme a direção: 3,13% contra 5,91%.

Não é detalhe técnico. Controlar por grade responde "mesmo cargo, mesmo
salário?". Não controlar responde "a carreira inteira foi justa?". E se a
promoção for ela mesma enviesada, controlar por grade **absorve a
discriminação para dentro do explicado** e produz um número melhor do que a
realidade.

O relatório de transparência salarial tende a puxar para a primeira leitura,
porque compara cargos comparáveis. Está correto para o fim a que se destina, e
é insuficiente como diagnóstico interno. Por isso este projeto sempre publica
as duas, com a diferença nomeada: **parcela atribuível à progressão de
carreira, +2,78 pontos percentuais em log-salário.**

Uma análise que reporta só uma especificação, sem dizer qual escolheu e por
quê, não deveria ser aceita — nem quando o número é favorável.

## O resultado que contraria a intuição

Recorte por raça/cor:

| Grupo | Gap bruto | Não explicado (mesmo cargo) | IC 95% | Significante |
|---|---|---|---|---|
| Preta vs Branca | **−0,0067** | **+0,0262** | [0,0003; 0,0486] | sim |
| Parda vs Branca | +0,0320 | +0,0283 | [0,0105; 0,0457] | sim |

O gap bruto para pessoas pretas é **negativo**: em média elas ganham
ligeiramente mais. Um relatório que parasse na comparação bruta concluiria que
não há problema.

A composição explica: pessoas pretas nesta base têm mais tempo de casa (58,5
contra 51 meses) e grade médio levemente maior. Controlando por isso, aparece
uma penalidade de 2,6% dentro do mesmo cargo, estatisticamente distinta de
zero — e próxima dos 3,0% injetados no gerador.

O inverso do caso de gênero, onde o gap bruto de 15% é 80% composição. Nas duas
direções, o número bruto engana. É o argumento mais forte deste repositório
contra o indicador único.

## Custo de remediação

Três políticas para o recorte de gênero:

| Política | Pessoas | Custo anual | % da folha | Corrige casos individuais |
|---|---|---|---|---|
| Nivelamento individual | 432 | R$ 12,68 mi | 2,86% | **sim** |
| Ajuste uniforme no grupo | 754 | R$ 5,79 mi | 1,31% | não |
| Nivelamento ao piso da faixa | 305 | R$ 8,01 mi | 1,81% | não |

O ajuste uniforme custa menos da metade do nivelamento individual e fecha a
média do grupo. E não corrige ninguém: quem estava 18% abaixo do previsto
continua 15% abaixo, e quem já estava acima recebe aumento sem motivo.

O nivelamento individual é o único defensável em auditoria e é sempre o mais
caro. Apresentar apenas o uniforme, porque cabe no orçamento, é o erro clássico
deste tema — e é auditável depois, o que o torna também o mais arriscado.

Custos anualizados com encargos (fator 1,94) e teto de 25% de ajuste por
pessoa em uma rodada.

## Privacidade

Dado sensível cruzado com remuneração exige tratamento diferente do resto do
projeto.

**Supressão por n mínimo.** Nenhuma métrica de remuneração é exibida para
grupos com menos de 5 pessoas. Com n=3, média salarial deixa de ser estatística
e vira exposição individual. A supressão vale para toda coluna de salário,
compa-ratio ou gap — basta uma escapar para o controle inteiro perder sentido.

**Corte único, não painel.** A análise usa um mês de referência. Repetir a
mesma pessoa em 60 meses infla o n artificialmente e estreita os intervalos até
qualquer diferença virar "significante".

**Gênero e raça/cor nunca são controles.** São o que se mede. Há teste que
falha o build se aparecerem na lista de covariáveis.

**Base legal.** Em produção, o tratamento se apoia no cumprimento de obrigação
legal (Lei 14.611/2023 e Decreto 11.795/2023) para o relatório de
transparência salarial, com acesso restrito à equipe que o produz.

## Dashboard

O modelo semântico, as medidas DAX e o wireframe das telas estão especificados
em `powerbi/`. **O arquivo `.pbix` ainda não está neste repositório** — a
especificação veio primeiro de propósito, porque tela desenhada antes de ser
construída custa muito menos para corrigir.

| Arquivo | Conteúdo |
|---|---|
| `powerbi/painel_equidade.md` | Três telas, medidas DAX, RLS e regras de supressão |

A medida `Rótulo do Gap` se recusa a exibir um número quando o intervalo de
confiança contém zero. É decisão de produto, não de estatística: se a
leitura correta é "não dá para afirmar", o painel precisa dizer isso.

## Estrutura

```
config/analise.yaml      recortes, bootstrap, parâmetros de remediação
src/equity/
  data.py                montagem do quadro, supressão, panorama
  gap.py                 Oaxaca-Blinder, duas especificações, bootstrap
  remediation.py         três políticas de correção e seus custos
  cli.py                 execução ponta a ponta
tests/                   8 testes, incluindo recuperação do gabarito
reports/                 fato_equidade.parquet, decomposição, custos
```

## Ressalvas

O bootstrap tem 500 reamostragens e trata a amostra como população. Para grupos
com menos de 100 pessoas os intervalos ficam largos, e o relatório deve dizer
isso em vez de arredondar.

A decomposição de Oaxaca-Blinder assume que os controles capturam produtividade
observável. Se houver um fator relevante ausente e correlacionado com o grupo,
parte dele vai parar no não explicado. O não explicado é um limite superior da
discriminação, nunca uma medida direta dela, e o relatório precisa usar essa
palavra.

O custo de remediação ignora o efeito sobre quem não recebeu ajuste. Corrigir
432 pessoas e não comunicar o critério gera um segundo problema de equidade,
desta vez percebida.
