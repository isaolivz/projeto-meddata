# MedData Dashboard

Dashboard analitico de internacoes hospitalares (SP), construido em Python + Streamlit.

## Estrutura

```
app.py                      # entrada, navegacao e resumo dos dados
pages/
  0_Guia.py                 # como navegar e interpretar os indicadores, antes do resto
  1_Monitoramento.py        # alertas criticos e ranking de risco de ocupacao por hospital
  2_Visao_Geral.py          # dashboard operacional: KPIs, volume, diagnosticos, mapa, filtros
  3_Pergunte_aos_Dados.py   # assistente em linguagem natural (3 agentes + Select AI)
  4_Chat_MedData.py         # mesmos 3 agentes, em formato de chat (IA + RAG)
core/                        # codigo real: data_loader, consultas, components, tema_editorial,
                              # db, agente, agente_rag, casos_conhecidos, rag
data/                          # arquivos CSV V1 e V2 (ver secao "Dados" abaixo)
wallet/                        # wallet do Oracle ADB (meddataadb2)
.streamlit/config.toml         # tema visual (paleta clara "editorial serio")
.env.example                   # modelo de variaveis de ambiente (copiar para .env)
raio_x_meddata.html            # relatorio com o que o MVP entrega e as limitacoes conhecidas
```

## Dados

O projeto tem duas geracoes de dados locais em `data/`, ambas presentes no repositorio.
Qual delas a **Visao Geral** usa e controlado por uma unica constante,
`VERSAO_ATIVA`, no topo de `core/data_loader.py` (`"v2"` por padrao).

### V2 (ativa por padrao)

| Dataset | Arquivo | Linhas | Chave |
|---|---|---|---|
| DIM_HOSPITAL | `dim_hospital_SP_2024_01_v2.csv` | ~1.466 | `id_hospital` (codigo CNES, texto) |
| DIM_MUNICIPIO | `dim_municipio_SP_2024_01_v2.csv` | ~645 | `codigo_municipio` (texto) |
| DIM_TEMPO | `dim_tempo_SP_2024_01_v2.csv` | ~1.024 | `tempo_id` |
| DIM_DIAGNOSTICO | `dim_diagnostico_SP_2024_01_v2.csv` | ~12.451 | `diagnostico_id` (CID) |
| FATO_INTERNACAO | `fato_internacao_SP_2024_01_v2.csv` | ~692.929 | `internacao_id` |

Todos separados por `;`. Relacionamentos validados com query direta no Oracle ADB
(as mesmas 5 tabelas existem la, carregadas com os mesmos totais):

- `FATO_INTERNACAO.id_hospital` → `DIM_HOSPITAL.id_hospital`
- `FATO_INTERNACAO.codigo_municipio_paciente` → `DIM_MUNICIPIO.codigo_municipio`
- `FATO_INTERNACAO.tempo_id` → `DIM_TEMPO.tempo_id` (bate com `data_internacao`)
- `FATO_INTERNACAO.diagnostico_id` → `DIM_DIAGNOSTICO.diagnostico_id`

Observacoes importantes sobre a V2:

- **`DIM_HOSPITAL` ganhou uma coluna `nome_hospital`, mas ela nao e um nome real** —
  e sempre `"Hospital CNES " + id_hospital` (confirmado: 0 excecoes em 1.466
  hospitais). O dashboard continua identificando hospitais pelo codigo CNES.
- `id_hospital`, `codigo_municipio` e `codigo_municipio_paciente` agora vem como
  texto (com zero a esquerda, ex.: `"0008028"`) em vez de numero — tratado em
  `core/data_loader.py`.
- Cerca de **2% das internacoes** tem `diagnostico_id = 0`, um valor sentinela
  usado quando o codigo de diagnostico informado e mais generico do que o nivel
  de detalhe da dimensao (ex.: `"I21"` em vez de `"I219"`). Essas internacoes sao
  excluidas dos graficos de diagnostico (nao aparecem como uma fatia "em branco").
- As datas de internacao (`data_internacao`) cobrem 2008–2024 (casos de longa
  permanencia/backlog), mas ~98% do volume esta concentrado nos ultimos ~12
  meses — por isso o grafico animado de evolucao por hospital e restrito aos
  meses mais recentes (ver `evolucao_top_hospitais` em `consultas.py`).

### V1 (mantida para rollback)

| Dataset | Arquivo | Separador | Linhas | Chave |
|---|---|---|---|---|
| DIM_HOSPITAL | `dim_hospital_SP_2024_01_certo.csv` | `;` | ~1.404 | `id_hospital` (numerico) |
| DIM_MUNICIPIO | `dim_municipio_SP_2024_01_certo.csv` | `;` | ~645 | `codigo_municipio` (numerico) |
| DIM_TEMPO | `dim_tempo_SP_2024_01.csv` | `,` | ~1.213 | `tempo_id` |
| FATO_INTERNACAO | `fato_internacao_SP_2024_01_certo.csv` | `;` | ~1.524.916 | `internacao_id` |

Sem diagnosticos, sem `nome_hospital`, `ids` numericos. **Para reverter da V2 para a
V1** (caso a V2 apresente algum problema): abra `core/data_loader.py` e troque

```python
VERSAO_ATIVA = "v2"
```

para `"v1"`, depois reinicie o app. Nenhum outro arquivo precisa mudar — as
funcoes de carregamento e todas as consultas da Visao Geral funcionam com as
duas versoes (a secao de diagnosticos e o mapa/evolucao continuam aparecendo
normalmente; so a secao de diagnosticos some, pois so existe na V2).

## Como rodar

> ⚠️ **Use Python 3.11, 3.12 ou 3.13 — NAO use o Python 3.14 instalado como
> padrao nesta maquina.** Foi confirmado que pandas 2.3.0 + numpy 2.5.1 no
> Python 3.14 tem um bug de ambiente que gera **segmentation fault** em
> qualquer `pandas.Series` com dtype `datetime64` (reproduzivel com um unico
> elemento, nao e sobre volume de dados). Isso quebraria a pagina Visao Geral
> inteira, ja que ela depende de datas. Ja existe uma venv pronta em `.venv/`
> criada com Python 3.12, onde tudo foi testado e funciona.
>
> ⚠️ **Esta maquina tem pouca RAM (~4 GB total).** Se aparecer `MemoryError` ao
> carregar os dados, feche outros processos Python/terminais abertos antes de
> rodar o app — os DataFrames em si sao leves (a V2 completa usa ~60 MB), o
> problema costuma ser memoria ja ocupada por sessoes anteriores.

**Git Bash / MINGW64** (prompt `$`):

```bash
source .venv/Scripts/activate
streamlit run app.py

# ou, sem ativar nada, chamando o python da venv direto:
.venv/Scripts/python.exe -m streamlit run app.py
```

**cmd.exe ou PowerShell** (prompt `>`):

```bat
.venv\Scripts\activate
streamlit run app.py
```

> ⚠️ `.venv\Scripts\activate` (com contrabarra) e sintaxe de cmd/PowerShell.
> Em Git Bash isso **nao ativa a venv silenciosamente** (nao da erro, so nao
> faz nada) e o `streamlit run app.py` seguinte acaba rodando com o Python
> 3.14 do sistema -- reproduzindo o segmentation fault descrito acima. Se seu
> prompt for `usuario@maquina MINGW64 /caminho $`, use os comandos com `/` e
> `source` acima.

Do zero, com qualquer Python 3.11/3.12/3.13 instalado:

```bash
py -3.12 -m venv .venv
source .venv/Scripts/activate   # Git Bash; em cmd/PowerShell: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

A **Visao Geral** funciona direto, sem nenhuma configuracao adicional (le os
CSVs em `data/`).

## Visao Geral

KPIs, ranking de hospitais/municipios, distribuicoes (porte hospitalar, dias de
internacao, pacientes que viajaram) e, quando os dados V2 estao ativos:

- **Top 10 diagnosticos** e um **treemap** de diagnosticos por categoria CID.
- **Mapa geografico** dos municipios por volume de internacoes
  (`px.scatter_map`, sem necessidade de token/API key).
- **Grafico animado** da evolucao mensal dos hospitais de maior volume.

O tema visual (paleta clara "editorial serio", `.streamlit/config.toml`) e o
template Plotly compartilhado (`aplicar_tema_claro()` em `core/tema_editorial.py`)
sao aplicados a todos os graficos da pagina.

## Pergunte aos Dados / Chat MedData (Select AI + Cohere)

Essas duas paginas **nao** usam os DataFrames locais — consultam o Oracle
Autonomous Database (wallet em `wallet/`) atraves do Select AI, usando um
profile ja criado no banco com um modelo Cohere. A pagina 4 (Chat MedData) e
uma interface alternativa em formato de conversa para o mesmo backend da
pagina 3 -- as duas podem coexistir, sem risco de uma quebrar a outra.

Fluxo por pergunta:

```
pergunta do gestor
  -> roteamento para 1 dos 3 agentes (Capacidade / Predicao / Otimizacao)
  -> bate com um "caso conhecido" (core/casos_conhecidos.py)?
       sim -> calculo real em Pandas/statsmodels, sem IA (resposta em segundos)
       nao -> DBMS_CLOUD_AI.GENERATE(..., action => 'showsql')   # gera o SQL
              -> executa o SQL gerado direto no banco             # traz a tabela
              -> DBMS_CLOUD_AI.GENERATE(..., action => 'chat')   # explica em linguagem natural
```

(A action final e `'chat'`, nao `'narrate'` -- ver o motivo, ligado a um erro real
de estouro de tokens, na docstring de `db.py`.)

Os 3 agentes usam o mesmo fluxo e o mesmo profile Select AI; a diferenca e o
contexto que cada um agrega a pergunta (ver `agente.py`). Antes de cair no
Select AI, `core/casos_conhecidos.py` tenta reconhecer perguntas previsiveis
(ranking de hospitais em risco, comparacao entre municipios, previsao de curto
prazo, hospital sem leito) e responde com calculo real ja testado -- mais rapido
e imune a erros de geracao de SQL. Qualquer pergunta que nao bata com um caso
conhecido (ou de erro no calculo) cai automaticamente no fluxo livre acima, sem
quebrar nada.

### Configuracao

1. Copie `.env.example` para `.env`.
2. Preencha `ORACLE_USER`, `ORACLE_PASSWORD` e `ORACLE_DSN` (um alias de
   `wallet/tnsnames.ora`, ex.: `meddataadb_low`). Prefira o alias `_low`
   para uso interativo do Select AI -- testado: ~5s por pergunta, contra
   ~13-17s com `_high`/`_medium` (que alocam mais paralelismo por consulta,
   o que so atrapalha nessas consultas pequenas).
3. Preencha `SELECT_AI_PROFILE` com o nome do profile ja criado no banco
   (via `DBMS_CLOUD_AI.CREATE_PROFILE`, apontando para o modelo Cohere).
   Opcionalmente, defina `SELECT_AI_PROFILE_CAPACIDADE` /
   `SELECT_AI_PROFILE_PREDICAO` / `SELECT_AI_PROFILE_OTIMIZACAO` caso queira
   um profile dedicado por agente.
   > O profile `MEDDATA_PRECISAO_V2` chegou a ficar quebrado no banco (nome
   > errado no `object_list` + `temperature` gravado com virgula em vez de
   > ponto, causando `ORA-06502`) -- ja foi corrigido via
   > `DBMS_CLOUD_AI.SET_ATTRIBUTE` e testado com sucesso. `MEDDATA_PRECISAO`
   > (sem "_V2") tambem funciona, se preferir.
4. Rode `streamlit run app.py` e abra "Pergunte aos Dados" ou "Chat MedData".

Se `.env` nao estiver preenchido, a pagina mostra um erro explicando a
variavel faltante em vez de quebrar a aplicacao.

## Proximos passos (fora do escopo desta versao)

- Migrar tambem a Visao Geral para consultar o Oracle ADB (hoje so os agentes
  de linguagem natural usam o banco).
- Cachear os resultados do Select AI por pergunta para reduzir custo/latencia.
