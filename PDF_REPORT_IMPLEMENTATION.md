# Implementação do relatório PDF

## Fluxo

1. O Dashboard prepara e filtra a base normalmente.
2. A aba `Relatório PDF` recebe os dados variáveis do cliente.
3. `PdfReportConfig` registra os parâmetros usados na geração.
4. `gerar_relatorio_pdf()` calcula as visões auxiliares usando o mesmo módulo
   `renewal_analysis` já utilizado pelo Dashboard.
5. O ReportLab gera páginas executivas e pagina automaticamente os anexos.
6. Os bytes retornados são mantidos no `session_state` e disponibilizados para download.

## Conteúdo gerado

- capa personalizada;
- resumo executivo;
- escopo e limitações;
- perfil do parque;
- evolução anual;
- análise por idade;
- concentração por modelo;
- metodologia do índice;
- ranking das máquinas críticas;
- Pareto e concentração do cenário;
- riscos além do custo direto;
- cenários de implantação;
- recomendações finais;
- Anexo B com filtros e parâmetros;
- Anexo C com todas as máquinas do cenário;
- Anexo D opcional com toda a base filtrada.

## Escalabilidade

O gerador não depende do Streamlit. Ele pode ser chamado por tarefas em lote,
API, fila de processamento ou rotina agendada. Os gráficos são desenhados pelo
próprio ReportLab, evitando dependência de navegador/Chrome para exportação do
Plotly.

## Testes

```powershell
poetry run pytest -q
```

O teste do PDF verifica cabeçalho `%PDF`, marcador de encerramento e tamanho
mínimo do arquivo, além das validações da configuração.
