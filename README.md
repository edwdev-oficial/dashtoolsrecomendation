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

## Relatório PDF reutilizável

O Dashboard possui agora a aba **Relatório PDF**. A geração usa a mesma base
analítica já filtrada na tela e preserva:

- anos selecionados;
- filtros do parque;
- data de corte;
- fator de impostos;
- idade de corte;
- quantidade de máquinas do cenário;
- logo e nome do cliente;
- opção de incluir ou não a base completa no Anexo D.

O relatório é produzido inteiramente em memória com ReportLab e disponibilizado
por `st.download_button`. Não é necessário salvar arquivos temporários no servidor.

Código principal:

- `src/dashtoolsrecomendation/reports/config.py`: configuração variável do cliente;
- `src/dashtoolsrecomendation/reports/generator.py`: páginas, gráficos, tabelas e anexos;
- `tests/test_pdf_report.py`: testes de geração e validação do arquivo PDF.

Exemplo de uso fora do Streamlit:

```python
from datetime import date

from dashtoolsrecomendation.reports import PdfReportConfig, gerar_relatorio_pdf

config = PdfReportConfig(
    cliente="Cliente Exemplo",
    responsavel="Responsável",
    cargo_responsavel="Rental Hilti do Brasil",
    data_emissao=date.today(),
    data_inicio=date(2024, 1, 1),
    data_fim=date.today(),
    idade_corte=5,
    fator_impostos=1.4,
    quantidade_cenario=100,
)

pdf_bytes = gerar_relatorio_pdf(
    base=base_analitica_filtrada,
    df_ams=df_ams,
    anos=[2024, 2025, 2026],
    config=config,
)
```

O projeto limita explicitamente a versão do Python a `>=3.12,<4.0`, pois o `reportlab` ainda não declara compatibilidade com Python 4. O arquivo `poetry.lock` antigo foi removido para permitir a resolução das dependências. Na primeira instalação, execute:

```powershell
poetry lock
poetry install
```
