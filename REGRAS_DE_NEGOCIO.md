# Regras de Negócio — Dashboard de Controle de Budget

> Documento de referência para o dashboard Streamlit em `C:\Claude_Files\Dashboards\Controle_Budget`.
> Atualizado em: 2026-03-16

---

## 1. Fontes de Dados

| Arquivo | Padrão de nome | O que contém |
|---|---|---|
| `190B - Despesas liquidadas (5).csv` | fixo | Despesas liquidadas (realizado financeiro) |
| `de_para.xlsx` | fixo | DE-PARA de código de natureza → categoria |
| `projecoes_DD_MM_YYYY.xlsx` | versionado | Orçamento previsto por centro de custo e categoria |
| `equipe_DD_MM_YYYY.xlsx` | versionado | Headcount e custo de pessoal por departamento |
| `software_DD_MM_YYYY.xlsx` | versionado | Custos projetados de software por departamento |
| `notas_desvios.json` | gerado pelo app | Anotações de desvio inseridas pelos usuários |

Todos os arquivos de dados ficam em `data/`.

---

## 2. Centros de Custo por Página

Cada página agrega um ou mais centros de custo definidos em `GROUP_MAP` (`utils/data.py`).

| Página (page_key) | Label exibido | Centros de custo incluídos |
|---|---|---|
| `administrativo` | Administrativo | Administrativo, Business Intelligence, Financeiro, Facility |
| `cx` | Customer Experience | Client Support, Customer Success, Implementação |
| `diretoria` | Diretoria | Diretoria |
| `educacao` | Educação | Educação |
| `comercial` | Comercial | Field Sales, Inbound, Sales, Outside Sales |
| `marketing` | Marketing | Marketing |
| `parcerias` | Parcerias | Eventos, Parceiros |
| `people` | People | People Happiness |
| `tech` | Tech | Tech |
| `operacoes` | Operações | Operações & Processos |
| `outros` | Outros | Inchurch Music, Design, InChurch Conference, Key Account, Meio de Pagamentos, Outbound, Produto, Upsell, inChurch KIDS, inVolve, Recorrente |
| `consolidado` | Consolidado | Todos os centros de custo acima reunidos |

**Ordem das páginas na sidebar:** alfabética (Administrativo → Tech), depois Outros (penúltimo) e Consolidado (último).

---

## 3. Leitura do 190B (Despesas Realizadas)

O arquivo CSV tem linhas de comprimento variável porque uma mesma despesa pode ser rateada entre múltiplos centros de custo. Por isso a leitura é feita com `csv.reader` (não `pd.read_csv`).

### Estrutura das colunas
| Col | Conteúdo |
|---|---|
| 6 | Data de liquidação (`DD/MM/YYYY`) |
| 8 | Código de natureza (código contábil) |
| 12 | Valor pago — formato BR (ponto = milhar, vírgula = decimal) |
| 13, 14, 15 | Grupo 1: Centro de custo · Participação % · Participação R$ |
| 16, 17, 18 | Grupo 2: Centro de custo · Participação % · Participação R$ |
| … | Continua em grupos de 3 |

### Regras de leitura
- Encoding: `latin1`
- Primeira linha (cabeçalho) é pulada
- Linhas com menos de 13 colunas são descartadas
- Para cada grupo de 3 colunas a partir do índice 13:
  - `valor_alocado = valor_pago × (participação_pct / 100)` — a coluna de Participação R$ é **ignorada** por estar corrompida para valores grandes
- Apenas entradas onde `centro_custo` não é vazio e não é `"Centro de custo"` são registradas

### Exclusão de transferências entre contas
Linhas onde o centro de custo é literalmente `"Centro de custo"` representam transferências internas (CC Transitório) e são **excluídas** da base. Isso afeta todos os centros de custo de todas as páginas.

### Normalização de nomes de centro
| Nome no 190B | Nome normalizado |
|---|---|
| `Loja inteligente` | `Loja Inteligente` |

---

## 4. Mapeamento de Categorias (DE-PARA)

O arquivo `de_para.xlsx` mapeia `cod_natureza` → `classificacao` (categoria contábil). Linhas sem match no DE-PARA recebem `"Sem Classificação"` automaticamente.

### Normalização pós-DE-PARA (`CATEGORIA_MAP`)
As seguintes categorias são unificadas antes de qualquer exibição:

| Valor original | Categoria normalizada |
|---|---|
| `------------` | Sem Classificação |
| `Sem classificação` | Sem Classificação |
| `Diferença de budget total` | Sem Classificação |
| `Diferença Budget Total` | Sem Classificação |
| `Salarios` | Folha de Pagamento |
| `Encargos` | Folha de Pagamento |
| `Beneficios` | Folha de Pagamento |

### Exclusão de "Sem Classificação" no Administrativo
Para a página **Administrativo**, a categoria `"Sem Classificação"` é excluída do realizado após a normalização. Motivo: os lançamentos não classificados nesse centro de custo são transferências internas entre contas e não representam despesas reais.

---

## 5. Realizado — Regras de Cálculo

- Fonte: 190B já filtrado e com categorias normalizadas
- Apenas **despesas** são contadas: `valor < 0` no sistema (a 190B registra saídas como negativo)
- O valor exibido é o **valor absoluto** (`abs`)
- Agrupado por `[mes, categoria]`
- O campo `mes` é derivado de `liquidacao` truncado para o início do mês

---

## 6. Previsto — Regras de Leitura dos Arquivos de Projeção

### Estrutura do XLSX
- Linha de cabeçalho de meses: primeira linha, nas primeiras 20, onde a coluna 2 é um `datetime`
- Meses ficam nas colunas 2 a 13 (até 12 meses)
- Linhas de dados: `col[0]` = centro de custo, `col[1]` = categoria, `col[2..13]` = valores mensais
- Linhas onde `col[0]` contém `"Soma Aberta"` são ignoradas (totalizadores)
- Valores: armazenados como `abs(val)` — o arquivo pode conter negativos

### Seleção de arquivo por mês (get_previsto_all)
O dashboard mantém múltiplas versões de projeção (uma por mês). A regra é:

> Para cada mês do calendário, usa-se o **arquivo mais recente** que cobre aquele mês.

**Exemplo com 3 arquivos (jan, fev, mar):**
| Mês do orçamento | Arquivo usado |
|---|---|
| Jan/26 | projecoes_08_01_2026.xlsx (único que tem Jan) |
| Fev/26 | projecoes_11_02_2026.xlsx (mais recente com Fev) |
| Mar/26 em diante | projecoes_15_03_2026.xlsx (mais recente disponível) |

Isso garante que revisões de orçamento feitas ao longo do ano são respeitadas por período.

---

## 7. Gráfico Previsto vs Realizado

- Tipo: barras agrupadas lado a lado (`barmode="group"`)
- Barra **Previsto**: cinza escuro (`#4c4c4c`)
- Barra **Realizado**:
  - Verde (`#6eda2c`) quando `realizado ≤ previsto`
  - Vermelho (`#e74c3c`) quando `realizado > previsto`
- A cor é calculada mês a mês, independentemente

---

## 8. Tabela por Categoria

- Colunas: Categoria · Previsto · Realizado · Desvio
- Inclui apenas categorias com `valor_previsto > 0` ou `valor_realizado > 0`
- Ordenada **alfabeticamente** por categoria
- Coluna Desvio:
  - `↑ R$ X` em **vermelho** quando realizado > previsto
  - `↓ R$ X` em **verde** quando realizado ≤ previsto

---

## 9. Filtro de Período

O seletor de período está disponível na aba "2026 — Previsto vs Realizado" e filtra simultaneamente previsto e realizado.

| Opção | Meses incluídos |
|---|---|
| Ano Todo | Jan–Dez (1–12) |
| Q1 — Jan-Mar | 1, 2, 3 |
| Q2 — Abr-Jun | 4, 5, 6 |
| Q3 — Jul-Set | 7, 8, 9 |
| Q4 — Out-Dez | 10, 11, 12 |
| Jan/26 … Dez/26 | Mês individual |

---

## 10. KPIs da Aba Principal

| KPI | Cálculo |
|---|---|
| Total Previsto 2026 | Soma de `valor_previsto` no período selecionado |
| Total Realizado | Soma de `valor_realizado` no período selecionado |
| Desvio | `realizado − previsto` (valor absoluto exibido, sinal na seta) |
| % Executado | `realizado / previsto × 100` |

---

## 11. Análise de Desvios

Seção automática abaixo da tabela por categoria:

- Lista todas as categorias onde `desvio > R$ 100` (realizado acima do previsto)
- Exibe: nome da categoria · previsto · realizado · desvio absoluto · desvio percentual
- Se nenhuma categoria estiver acima, exibe mensagem de sucesso

### Anotações de desvio
- Campo de texto livre, editável, salvo em `data/notas_desvios.json`
- Chave de armazenamento: `{periodo_sel}_{page_key}` (ex: `Q1_comercial`)
- Notas são persistentes entre sessões e usuários

---

## 12. Equipe

### Estrutura do XLSX
- Linha de meses: primeira linha, nas primeiras 15, onde `col[2]` é `datetime` (cols 0-1 são NaN)
- Meses ficam nas colunas 2 a 13
- Dados: `col[0]` = departamento, `col[1]` = pessoa/tipo, `col[2..13]` = custo mensal

### Classificação de tipo por nome
| Nome em `col[1]` | Tipo interno | Exibição |
|---|---|---|
| `Reposição` | `reposicao` | 🔄 Reposição |
| `NOVO` (qualquer case) | `novo` | 🆕 Nova contratação |
| `Budget Livre` | `budget_livre` | 📦 Budget Livre |
| Qualquer outro | `pessoa` | (nome sem prefixo) |

- Linhas `"SIMULAÇÃO DE CORTE"` são **ignoradas**

### Mapeamento de departamentos → página
| Departamento no arquivo | page_key |
|---|---|
| FINANCEIRO | administrativo |
| BUSINESS INTELLIGENCE | administrativo |
| RECURSOS HUMANOS | people |
| EDUCAÇÃO | educacao |
| MARKETING | marketing |
| INBOUND | comercial |
| OUTSIDE | comercial |
| PARCERIAS | parcerias |
| EVENTOS | parcerias |
| IMPLEMENTAÇÃO | cx |
| ONGOING | cx |
| SUPORTE | cx |
| BOT | outros |
| TECH | tech |
| DIRETORIA | diretoria |
| (qualquer outro) | outros |

### Tabela de colaboradores
- Exibe **todos** que tiveram custo > 0 em **qualquer mês** (não apenas no mês de referência)
- Mês de referência = Mar/26 (índice 2) ou último mês disponível se houver menos de 3 meses
- Colunas: Departamento · Colaborador · Custo (mês ref.) · Início · Fim
- **Início**: `"< Jan/26"` se a pessoa já tinha custo no primeiro mês do arquivo; senão, primeiro mês com custo > 0
- **Fim**: `"—"` se a pessoa ainda tem custo no último mês do arquivo; senão, último mês com custo > 0
- Ordem dentro de cada departamento:
  1. Colaboradores (`pessoa`, `budget_livre`) — alfabético
  2. Reposições (`reposicao`) — sempre ao final
  3. Novas contratações (`novo`) — sempre ao final, após reposições

### Versão usada
Sempre a versão **mais recente** disponível (maior data no nome do arquivo).

---

## 13. Software

### Estrutura do XLSX
- Mesmo padrão de leitura de meses que o arquivo Equipe (col 2 é datetime)
- `col[0]` = departamento — campo pode estar vazio em linhas de dados; o valor é carregado da última célula não-vazia acima
- `col[1]` = nome do software
- `col[2..13]` = valor projetado por mês
- Linhas sem nome de software (totais ou vazias) são ignoradas
- Apenas valores > 0 são registrados

### Mapeamento de departamentos → página
| Departamento no arquivo | page_key |
|---|---|
| Support | cx |
| CS | cx |
| FIN | administrativo |
| RH | people |
| Marketing | marketing |
| Processos | operacoes |
| Sales Geral | comercial |
| Inbound | comercial |
| Outbound | comercial |
| Outside Sales | comercial |
| Tech | tech |
| Geral | administrativo |
| (qualquer outro) | outros |

### Realizado de software
O realizado de software é extraído do 190B filtrando as categorias `"Software"` e `"Servidor"` (pós-DE-PARA). Esse valor é comparado com a projeção do arquivo de software.

### Gráfico da aba Software
- Barras sobrepostas (`barmode="overlay"`)
- Projetado: cinza escuro
- Realizado: verde

### Tabela de software
- Pivô: linhas = softwares, colunas = meses + Total
- Ordenada por Total decrescente
- Células com valor zero exibidas como `"—"`

---

## 14. Log de Mudanças no Orçamento

Compara arquivos de projeção consecutivos (ordenados por data):

- Registra qualquer variação `> R$ 1` em `valor_previsto` para o mesmo `(centro_custo, categoria, mes)`
- Exibe: data de alteração · centro de custo · categoria · mês · valor antes → valor depois · variação
- Ordenado por data de alteração (mais recente primeiro)

---

## 15. Log de Alterações na Equipe

Compara versões consecutivas do arquivo equipe:

| Evento | Critério |
|---|---|
| Entrada | Pessoa aparece na versão nova mas não na anterior |
| Saída | Pessoa estava na versão anterior mas não na nova |
| Custo alterado | Custo total anual da pessoa difere em mais de R$ 1 entre versões |
| Reposição | Quantidade de linhas de reposição muda entre versões |

---

## 16. Autenticação e Controle de Acesso

### Fluxo
1. Login via Google OIDC (`st.login`) — validado pelo e-mail na lista `allowed_emails`
2. Cada página exige uma senha adicional (por centro de custo)
3. A senha mestra (`master`) dá acesso a **qualquer** página sem precisar da senha específica
4. Senha correta é salva em `st.session_state` e não é pedida novamente na mesma sessão

### Acesso restrito
| Página | Acesso |
|---|---|
| Outros | Apenas senha mestra |
| Consolidado | Apenas senha mestra |
| Demais | Senha da página ou senha mestra |

### Dev mode
Quando `dev_mode = true` em `secrets.toml`, o guard de login (`st.user.is_logged_in`) é ignorado. **Desativar antes do deploy em produção.**

---

## 17. Cache

Todas as funções de leitura de arquivo usam `@st.cache_data(ttl=3600)` — os dados são recarregados do disco a cada 1 hora. Para forçar recarga imediata, reiniciar o processo do Streamlit.

---

## 18. Resumo de Decisões de Negócio Tomadas Durante o Desenvolvimento

| Decisão | Motivo |
|---|---|
| Excluir `centro_custo == "Centro de custo"` | São transferências entre contas (CC Transitório), não despesas reais |
| Excluir "Sem Classificação" do realizado do Administrativo | Lançamentos não classificados nesse centro são transferências internas |
| `valor_alocado = valor_pago × pct / 100` (ignorar coluna de valor $) | A coluna de valor $ está corrompida para valores grandes no sistema de origem |
| Unificar Salarios + Encargos + Beneficios → "Folha de Pagamento" | Visibilidade consolidada do custo de pessoal |
| Usar arquivo mais recente por mês na projeção | Revisões orçamentárias ao longo do ano devem prevalecer para os meses futuros, mas meses já encerrados devem usar a projeção vigente àquele mês |
| Outside Sales → `comercial` (não `outros`) | Time faz parte da estrutura comercial da empresa |
| Reposições e novas contratações sempre ao final da tabela de equipe | Separar claramente headcount ativo de vagas em aberto |
| Desvio mínimo de R$ 100 para aparecer na Análise de Desvios | Evitar ruído de centavos e ajustes irrisórios |
| Mês de referência da equipe = Mar/26 (índice 2) | Representa o estado atual mais estável; jan/fev podem ter dados incompletos |
