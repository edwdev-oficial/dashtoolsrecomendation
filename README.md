# Dash Tools

Aplicação Streamlit para carga, conciliação e análise comercial do parque de máquinas.

## Objetivo do dashboard

O dashboard foi estruturado para apoiar uma proposta de renovação seletiva do parque, distinguindo claramente:

- parque atual;
- máquinas com reparações registradas pela Hilti;
- frequência observada por máquina;
- custo por máquina;
- recorrência em anos diferentes;
- diferenças de atualização entre a fonte do parque e a fonte AMS.

A análise de manutenção considera, por padrão, somente os anos a partir de **2024**. O histórico anterior não é tratado como completo porque parte das manutenções era realizada na oficina do cliente.

## Abas do dashboard

- **Resumo executivo:** KPIs com denominador do parque, comparação por faixa etária, matriz de prioridade e ranking individual.
- **Modelos e custos:** evolução anual, identificação de ano parcial, taxas por modelo e composição do custo.
- **Plano de renovação:** cenário ajustável para as máquinas de maior prioridade e Pareto de custo.
- **Qualidade dos dados:** conciliação por número de série entre parque e AMS.
- **Base filtrada:** base analítica exportável.

## Índice de prioridade

O índice é relativo ao conjunto filtrado e combina:

- idade: 25%;
- frequência observada: 30%;
- custo observado: 30%;
- recorrência em anos diferentes: 15%.

Ele serve para ordenar a investigação comercial e técnica. Não é uma previsão de falha, disponibilidade ou economia futura.

## Arquitetura

- `src/dashtoolsrecomendation/pages`: composição das páginas e fluxo de interface.
- `src/dashtoolsrecomendation/components`: componentes visuais, filtros e gráficos.
- `src/dashtoolsrecomendation/services`: transformações, normalização e análise.
- `src/dashtoolsrecomendation/services/renewal_analysis.py`: indicadores e priorização de renovação.
- `src/dashtoolsrecomendation/database`: acesso preguiçoso ao MongoDB.
- `src/dashtoolsrecomendation/utils`: formatação e carregamento de assets.
- `tests`: testes de regressão das transformações puras.

As páginas não devem concentrar regras de transformação. Novos cálculos devem ser implementados em `services` e cobertos por testes.

## Configuração de credenciais

Copie o arquivo de exemplo e preencha localmente:

```powershell
Copy-Item .streamlit/secrets.example.toml .streamlit/secrets.toml
```

O arquivo `secrets.toml` não deve ser versionado nem compartilhado.

## Execução

```powershell
poetry install
poetry run streamlit run app.py
```

## Testes

```powershell
poetry run python -m unittest discover -s tests -v
```

A suíte inclui testes para:

- normalização e agrupamento do AMS;
- cálculo de idade;
- denominadores por parque e por modelo;
- conciliação entre fontes;
- projeção opcional de ano parcial;
- cenário de concentração para renovação.
