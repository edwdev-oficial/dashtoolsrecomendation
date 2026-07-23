# Alterações implementadas

## Correções metodológicas

1. O parque atual passou a ser o denominador padrão dos indicadores.
2. Máquinas presentes somente no histórico AMS ficam fora dos KPIs comerciais por padrão e aparecem na aba de qualidade dos dados.
3. O período padrão começa em 2024.
4. O ano corrente é identificado como parcial e pode receber uma projeção opcional, claramente separada do realizado.
5. O termo “economia” foi substituído por “valor absorvido” nas novas visualizações.
6. Os textos do dashboard informam que a base não mede disponibilidade, tempo parado ou produtividade.

## Novas análises

- percentual do parque com reparação;
- reparações por máquina do parque;
- custo por máquina do parque;
- frequência e custo normalizados por faixa etária;
- matriz idade × reparações × custo;
- ranking individual de prioridade;
- Pareto do custo por máquina;
- cenário ajustável para avaliação de renovação;
- análise por modelo usando todas as máquinas do parque como denominador;
- conciliação de números de série entre as duas fontes.

## Índice de prioridade

O índice combina percentis relativos ao conjunto filtrado:

- idade: 25%;
- frequência por ano observado: 30%;
- custo: 30%;
- recorrência em anos diferentes: 15%.

O índice serve para ordenar a avaliação comercial e técnica. Ele não representa previsão de falha ou economia garantida.

## Correções técnicas adicionais

- correção do cálculo de `Custo Reparo c/Imp`, que era sobrescrito pelo valor sem o fator 1,4;
- normalização do número de série antes do merge;
- marcação explícita de origem do registro (`_presente_parque` e `_presente_ams`);
- correção de `preparar_ams` quando `ano_reparo` não existe;
- importação tardia do acesso ao MongoDB para permitir testes unitários sem Streamlit;
- inclusão de 5 testes para a nova camada analítica;
- remoção de credenciais do pacote devolvido e inclusão de `secrets.example.toml`.

## Limitações atuais dos dados

- os relatórios possuem agregação anual, sem data individual de cada reparação;
- não é possível calcular MTTR, dias de indisponibilidade ou intervalo exato entre reparações;
- a idade no momento de cada reparação não pode ser determinada com precisão sem a data do evento;
- concentração histórica de custo não deve ser apresentada como economia futura garantida.
