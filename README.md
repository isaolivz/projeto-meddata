# MedData
<img width="1024" height="250" alt="image" src="https://github.com/user-attachments/assets/e8e18a8a-e85a-48f6-a564-b0327ad5fab6" />


**Apoio à gestão da rede hospitalar de São Paulo com IA sobre o Oracle Autonomous Database.**
Desenvolvido para o Challenge Oracle 2026.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Streamlit-dashboard-FF4B4B" alt="Streamlit">
  <img src="https://img.shields.io/badge/Oracle-Autonomous%20Database-red" alt="Oracle Autonomous Database">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT">
</p>

---

## O problema

A rede hospitalar de São Paulo processa centenas de milhares de internações por mês, com hospitais operando perto — ou acima — da capacidade em diversos municípios. Gestores precisam responder rápido a 3 perguntas:

-  **Onde está o risco de colapso agora?**
-  **Para onde encaminhar um paciente quando não há vaga?**
-  **Como a demanda vai evoluir nos próximos dias?**

Hoje essas respostas dependem de análise manual de planilhas e relatórios dispersos. O MedData usa dados reais de internações (SIH/DataSUS), leitos (CNES) e municípios (IBGE) para responder essas perguntas em linguagem natural — combinando cálculos estatísticos validados com consultas geradas por IA direto no banco.


## 🔗 Arquitetura do MVP

```mermaid
flowchart LR
    subgraph FONTES["Fontes públicas"]
        direction TB
        SIH["SIH<br/>internações"]
        CNES["CNES<br/>leitos"]
        IBGE["IBGE<br/>municípios"]
        CID["CID-10<br/>diagnósticos"]
    end

    subgraph PIPELINE["Pipeline (src/)"]
        direction LR
        ING["Ingestão"] --> BRONZE[("Bronze")] --> TRANS["Transformação"] --> SILVER[("Silver")] --> INTEG["Integração"] --> GOLD[("Gold")] --> VALID["Validação"] --> CARGA["Carga<br/>Analítica"]
    end

    subgraph ORACLE["Oracle Autonomous Database"]
        direction LR
        DIMFATO[("DIM_* / FATO")] --> VIEWS["Views<br/>analíticas"] --> SELECTAI["Select AI<br/>(Cohere, via wallet)"]
    end

    subgraph CONSUMO["Consumo"]
        direction TB
        PLATFORM["MedData Platform<br/>(Streamlit) — 3 agentes + RAG"]
        APEX["Oracle APEX<br/>relatório com IA"]
    end

    SIH --> ING
    CNES --> ING
    IBGE --> ING
    CID --> ING
    CARGA --> DIMFATO
    SELECTAI --> PLATFORM
    SELECTAI --> APEX
    VIEWS --> APEX
    PLATFORM -.->|link| APEX
    PLATFORM --> GESTOR["Recomendação<br/>pro gestor"]
    APEX --> GESTOR

```


## Screenshot

<img width="1550" height="741" alt="image" src="https://github.com/user-attachments/assets/2c4f8117-97ce-409d-bc6e-f27b1e4eff1c" />
<img width="1600" height="771" alt="image" src="https://github.com/user-attachments/assets/83594514-1449-40f9-b80c-3c65a51a08e4" />
<img width="1600" height="767" alt="image" src="https://github.com/user-attachments/assets/3db8acf1-53b5-4894-8593-fbf38fd371f1" />
<img width="1600" height="810" alt="image" src="https://github.com/user-attachments/assets/89be40eb-5546-4212-9fd9-08e6253e9d52" />
<img width="600" height="300" alt="image" src="https://github.com/user-attachments/assets/7923f2d0-1ce6-4d7f-a592-3b4bb32b6c7f" />
<img width="1600" height="771" alt="image" src="https://github.com/user-attachments/assets/319a248b-75d0-4ebe-8488-6da6a50c46eb" />
<img width="1600" height="775" alt="image" src="https://github.com/user-attachments/assets/08365dc1-a30f-4514-bef9-e23cf1b6feea" />
<img width="1600" height="839" alt="image" src="https://github.com/user-attachments/assets/44026ad3-bcc8-41d8-a62a-6a2649c0a0f9" />




## 🔗 Acesse o dashboard

**[projeto-meddata.streamlit.app](https://projeto-meddata-3qioneoard7hqeqx9srbsn.streamlit.app/)**


## Arquitetura

```mermaid
flowchart LR
    A["Dados públicos<br/>SIH · CNES · IBGE · CID-10"] --> B["Pipeline de ingestão<br/>(src/)"]
    B --> C[("Oracle Autonomous<br/>Database")]
    C --> D["Select AI<br/>(modelo Cohere)"]
    C --> E["Dashboard Streamlit<br/>(Pandas local)"]
    D --> F["3 agentes de IA<br/>Capacidade · Predição · Otimização"]
    F --> G["Recomendação prática<br/>para o gestor hospitalar"]
    E --> G
```

## Stack

- **Python 3.12** — pipeline de dados e aplicação
- **Oracle Autonomous Database** + **Select AI** (modelo Cohere) — consultas em linguagem natural direto no banco
- **Streamlit** + **Plotly** — dashboard interativo
- **statsmodels** (ETS/Holt-Winters) — previsão de curto prazo de internações
- **LangChain + Chroma** — base de conhecimento (RAG) dos agentes de IA

## Fontes de dados

| Fonte | Conteúdo | Órgão |
|---|---|---|
| SIH (Sistema de Informações Hospitalares) | Internações, grupo RD (AIH Reduzida) | DataSUS |
| CNES | Leitos por estabelecimento | DataSUS |
| IBGE | Municípios de São Paulo | IBGE |
| CID-10 | Descrição de diagnósticos | OMS/DATASUS |

Recorte: estado de São Paulo, ~690 mil internações no período coberto pelos dados V2.

## Estrutura de pastas

```
projeto-meddata/
├── src/                     # pipeline: ingestão, transformação e carga dos dados públicos
├── dashboard_streamlit/     # aplicação Streamlit
│   ├── app.py
│   ├── pages/               # Monitoramento, Visão Geral, Pergunte aos Dados, Chat MedData
│   ├── core/                # lógica: data_loader, consultas, agentes, Select AI, RAG
│   └── README.md            # documentação técnica detalhada do dashboard
├── notebooks/                # análises exploratórias e validação do modelo de previsão
├── analise_exploratoria/     # dicionário de dados e estatísticas descritivas
└── data/                     # dados de referência (CID-10, IBGE)
```

> Documentação técnica completa do dashboard (schema dos dados, como rodar, configuração do Select AI): [`dashboard_streamlit/README.md`](dashboard_streamlit/README.md).

## Funcionalidades

| Página | O que faz |
|---|---|
| **Monitoramento** | Alertas de risco de colapso por hospital, ocupação em tempo real, tendência de internações |
| **Visão Geral** | KPIs, ranking de hospitais/municípios, diagnósticos, mapa geográfico, evolução mensal |
| **Pergunte aos Dados** | Perguntas em linguagem natural, roteadas por palavra-chave entre 3 agentes |
| **Chat MedData** | Mesmos 3 agentes, com roteamento por IA e base de conhecimento própria (RAG) |

## Os 3 agentes de IA

Cada pergunta é roteada para um agente especializado, que sempre fecha a resposta com uma **recomendação prática** para o gestor — não só o dado bruto:

- **Capacidade** — volume de internações, ocupação de leitos, ranking de hospitais.
- **Predição** — evolução das internações ao longo do tempo e tendências futuras.
- **Otimização** — comparações entre municípios/hospitais, distância, custo, eficiência.

Antes de acionar a IA, o sistema tenta reconhecer **perguntas previsíveis** (ex.: "quais hospitais estão em risco?") e responde com um cálculo já testado (Pandas/statsmodels) em vez de gerar uma consulta nova toda vez — mais rápido e imune a erros de geração de SQL. Só quando nenhum caso conhecido bate, a pergunta cai no fluxo livre: Select AI gera o SQL, executa no Oracle, e explica o resultado em português.

Detalhes de implementação (roteamento, RAG, casos conhecidos): [`dashboard_streamlit/README.md`](dashboard_streamlit/README.md).

## Como rodar localmente

```bash
py -3.12 -m venv .venv
source .venv/Scripts/activate   # Git Bash; em cmd/PowerShell: .venv\Scripts\activate
pip install -r dashboard_streamlit/requirements.txt
cd dashboard_streamlit
cp .env.example .env            # preencha as credenciais do Oracle ADB
streamlit run app.py
```

A página **Visão Geral** funciona direto (dados locais); **Pergunte aos Dados** e **Chat MedData** exigem as credenciais do Oracle no `.env`. Passo a passo completo: [`dashboard_streamlit/README.md`](dashboard_streamlit/README.md#como-rodar).

## Limitações conhecidas

- A coluna `nome_hospital` não é um nome real de estabelecimento — hospitais são sempre identificados pelo código CNES.
- `alta_complexidade` tem o mesmo valor para todos os hospitais na base (não é um critério de filtro utilizável); use `porte_hospitalar`.
- Dados de internação cobrem 2008–2024, mas ~98% do volume está concentrado nos últimos ~12 meses.
- A previsão de curto prazo é uma projeção estatística (erro médio de ~22% em teste retrospectivo), não uma garantia.

## Autoria

Isabella Batista Santos Oliveira
Projeto desenvolvido para o **Challenge Oracle 2026**.

## Licença

[MIT](LICENÇA)
