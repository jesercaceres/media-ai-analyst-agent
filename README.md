# Media Analyst AI Agent

> MVP de um Agente de IA Autônomo que atua como "Analista Júnior de Mídia",  
> capaz de responder perguntas em linguagem natural consultando o dataset público  
> **thelook_ecommerce** no Google BigQuery.

**Repositório:** https://github.com/jesercaceres/media-ai-analyst-agent

---

## Sumário

- [Arquitetura](#arquitetura)
- [Tools do Agente](#tools-do-agente)
- [Stack Técnica](#stack-técnica)
- [Versão do Python](#versão-do-python)
- [Dependências](#dependências)
- [Pré-requisitos](#pré-requisitos)
- [Setup](#setup)
- [Executando a API](#executando-a-api)
- [Exemplos de uso](#exemplos-de-uso)
- [Estrutura de Pastas](#estrutura-de-pastas)
- [Solução de problemas](#solução-de-problemas)

---

## Arquitetura

O agente segue o padrão **ReAct** (Reason + Act) implementado com **LangGraph**:

```
Pergunta do usuário
       │
       ▼
  ┌────────────────┐   tool_calls?   ┌──────────────────┐
  │   LLM Node     │ ──────────────► │  Tools Node (BQ) │
  │ (Gemini 2.5    │                 │  executa SQL     │
  │     Flash)     │                 └──────────────────┘
  └────────────────┘                          │
       ▲                                      │
       │      resultado da tool               │
       └──────────────────────────────────────┘
                  loop até resposta final
                          │
                          ▼
                Insight em linguagem natural
```

### Fluxo detalhado

1. O usuário envia uma pergunta via `POST /api/v1/chat`.
2. O **LLM Node** (Google Gemini via `ChatGoogleGenerativeAI`) recebe a pergunta + histórico + system prompt.
3. Se precisar de dados, o LLM emite um **tool call** em vez de responder diretamente.
4. O **Tools Node** executa a função Python correspondente, que roda uma **query SQL parametrizada** no BigQuery e retorna um dict estruturado.
5. O resultado é anexado ao histórico de mensagens e o LLM é invocado novamente.
6. O loop continua até que o LLM produza uma resposta final (sem tool calls).
7. A resposta chega ao usuário como um insight acionável em linguagem natural.

> **Separação de responsabilidades**: a lógica de raciocínio fica no LLM; a lógica de execução de dados fica nas tools Python. O agente nunca "adivinha" números — ele sempre consulta o BigQuery.

---

## Tools do Agente

| Tool | Descrição | Quando é chamada |
|------|-----------|-----------------|
| `get_traffic_volume` | Novos usuários por canal em um janela de datas | "Quantos usuários vieram de Search no último mês?" |
| `get_channel_performance` | Taxa de conversão, receita, AOV e RPU por canal | "Qual canal tem a melhor performance?" |
| `get_revenue_trend` | Tendência mensal de receita por canal | "Como a receita do Facebook evoluiu nos últimos 6 meses?" |
| `get_user_demographics` | Perfil demográfico (gênero, faixa etária, país) por canal | "Qual é o perfil dos usuários de Email?" |
| `get_top_products_by_channel` | Produtos mais vendidos por canal | "Quais produtos são mais comprados por usuários do Organic?" |

Todas as tools:
- Recebem parâmetros tipados (Pydantic via `@tool`)
- Executam queries **parametrizadas** (sem interpolação de string) para segurança
- Retornam dicts estruturados que o LLM usa para formular insights

---

## Stack Técnica

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | **Python 3.13** (testado com 3.13.13) |
| Web Framework | FastAPI `0.115.12` |
| Orquestrador de IA | LangGraph `0.4.5` |
| LLM | Google Gemini (`gemini-2.5-flash` via `langchain-google-genai`) |
| Data Warehouse | Google BigQuery `3.31.0` |
| Validação | Pydantic `2.11.4` + pydantic-settings `2.9.1` |
| Servidor ASGI | Uvicorn `0.34.2` |

---

## Versão do Python

| Versão | Status |
|--------|--------|
| **Python 3.13.x** | Recomendada e testada — use no venv do projeto |
| Python 3.12.x | Provável compatibilidade (wheels disponíveis) |
| Python 3.14.x | **Não suportada** — `pydantic-core` e outras libs Rust ainda não têm wheels estáveis |

O case pede Python 3.10+, mas este repositório foi validado com **Python 3.13.13** no Windows.

Se `python --version` no terminal mostrar **3.14**, isso é o Python global do sistema. O projeto deve usar um venv criado com **3.13**:

```powershell
py -0                    # lista versões instaladas
py -3.13 -m venv .venv   # cria o venv com 3.13 (não use o default 3.14)
.\.venv\Scripts\python.exe --version   # deve exibir Python 3.13.x
```

Instalar Python 3.13 no Windows:

```powershell
winget install Python.Python.3.13
```

---

## Dependências

Versões fixadas em `requirements.txt`:

### Web & API

| Pacote | Versão |
|--------|--------|
| `fastapi` | 0.115.12 |
| `uvicorn[standard]` | 0.34.2 |
| `pydantic` | 2.11.4 |
| `pydantic-settings` | 2.9.1 |
| `httpx` | 0.28.1 |
| `python-dotenv` | 1.1.0 |

### LangChain / LangGraph / Gemini

| Pacote | Versão |
|--------|--------|
| `langchain` | 0.3.25 |
| `langchain-core` | 0.3.58 |
| `langchain-google-genai` | 2.1.4 |
| `langgraph` | 0.4.5 |
| `langsmith` | >=0.1.17, <0.2.0 |

### Google Cloud

| Pacote | Versão |
|--------|--------|
| `google-cloud-bigquery` | 3.31.0 |
| `google-auth` | 2.40.1 |

---

## Pré-requisitos

- **Python 3.13** no ambiente virtual (`py -3.13 -m venv .venv`)
- Conta **Google Cloud** (gratuita) com [BigQuery API habilitada](https://console.cloud.google.com/apis/library/bigquery.googleapis.com)
- **Service Account** com papéis:
  - `BigQuery Job User` (criar/executar queries)
  - `BigQuery Data Viewer` (ler dados)
- Chave de API do **Google AI Studio** (gratuita) — https://aistudio.google.com/apikey

---

## Setup

### 1. Clone o repositório

```bash
git clone https://github.com/jesercaceres/media-ai-analyst-agent.git
cd media-ai-analyst-agent
```

### 2. Crie e ative o ambiente virtual

> Use sempre **`py -3.13`**, mesmo que o Python padrão do sistema seja 3.14.

```powershell
# Windows (PowerShell)
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe --version   # confirme: Python 3.13.x
```

```bash
# Linux/macOS
python3.13 -m venv .venv
source .venv/bin/activate
python --version
```

**Alternativa (Windows):** script auxiliar que cria o venv e instala dependências:

```powershell
.\setup.ps1
```

### 3. Instale as dependências

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt --prefer-binary
```

### 4. Configure o Google Cloud (BigQuery)

1. Acesse o [Console GCP](https://console.cloud.google.com/) e crie ou selecione um projeto.
2. Habilite a [API do BigQuery](https://console.cloud.google.com/apis/library/bigquery.googleapis.com).
3. Em [IAM → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts), crie uma conta de serviço.
4. Atribua os papéis **BigQuery Job User** e **BigQuery Data Viewer**.
5. Gere uma chave **JSON** e salve em local seguro (ex.: pasta do projeto).
6. Anote o **ID do projeto** (ex.: `meu-projeto-123456`) — aparece no seletor de projetos ou no campo `project_id` do JSON.

> O dataset `bigquery-public-data.thelook_ecommerce` é **público**; sua conta paga apenas a execução do job de query no seu projeto.

### 5. Configure o Google AI Studio (Gemini / LLM)

1. Acesse https://aistudio.google.com/apikey
2. Clique em **Create API key**
3. Escolha **Create API key in new project** (recomendado — já habilita a Generative Language API)
4. Copie a chave (`AIza...`)

> A chave do AI Studio é **independente** da Service Account do BigQuery. Você precisa dos dois.

### 6. Configure as variáveis de ambiente

```powershell
# Windows
Copy-Item .env.example .env
```

```bash
# Linux/macOS
cp .env.example .env
```

Edite o `.env`:

```env
# Gemini (Google AI Studio)
GOOGLE_API_KEY=AIzaSy...

# BigQuery (Service Account)
GOOGLE_APPLICATION_CREDENTIALS=C:\caminho\completo\para\service-account.json
GCP_PROJECT_ID=seu-projeto-gcp

# Agente (opcional)
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0
AGENT_MAX_ITERATIONS=10
```

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `GOOGLE_API_KEY` | Sim | Chave do [Google AI Studio](https://aistudio.google.com/apikey) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Sim | Caminho **absoluto** do JSON da Service Account |
| `GCP_PROJECT_ID` | Sim | ID do projeto GCP (campo `project_id` no JSON) |
| `GEMINI_MODEL` | Não | Padrão no código: `gemini-2.0-flash`; recomendado: `gemini-2.5-flash` |
| `GEMINI_TEMPERATURE` | Não | `0` = respostas mais determinísticas |
| `AGENT_MAX_ITERATIONS` | Não | Limite de iterações do agente (padrão: `10`) |

---

## Executando a API

```bash
# Com o venv ativo
uvicorn app.main:app --reload --port 8000
```

```powershell
# Windows — sem ativar o venv
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Documentação interativa (Swagger): **http://localhost:8000/docs**

Health check: **http://localhost:8000/health**

---

## Exemplos de uso

### Via Swagger UI

1. Abra http://localhost:8000/docs
2. Expanda `POST /api/v1/chat` → **Try it out**
3. Cole o JSON e clique em **Execute**

```json
{
  "message": "Qual canal tem a melhor performance no último mês?",
  "history": []
}
```

### Via curl (PowerShell)

Use aspas simples no JSON ou `Invoke-RestMethod`:

```powershell
$body = @{
  message = "Qual canal tem a melhor performance no ultimo mes?"
  history = @()
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" -Method Post -Body $body -ContentType "application/json"
```

### Resposta esperada

```json
{
  "answer": "No último mês, o canal com melhor performance foi o **Search**...",
  "model": "gemini-2.5-flash"
}
```

---

## Estrutura de Pastas

```
.
├── app/
│   ├── main.py                    # Entry point FastAPI + lifespan
│   ├── api/
│   │   ├── __init__.py            # Router /api/v1
│   │   └── routes/
│   │       └── chat.py            # POST /api/v1/chat
│   ├── agent/
│   │   ├── agent.py               # LangGraph (ReAct) + run_agent()
│   │   └── tools/
│   │       └── bigquery_tools.py  # 5 tools + SQL thelook_ecommerce
│   ├── core/
│   │   ├── config.py              # Settings (.env)
│   │   └── bigquery.py            # Cliente BQ + run_query()
│   └── schemas/
│       └── chat.py                # ChatRequest / ChatResponse
├── requirements.txt
├── setup.ps1                      # Bootstrap venv (Windows)
├── .env.example
└── README.md
```

---

## Solução de problemas

| Erro | Causa provável | Solução |
|------|----------------|---------|
| Falha ao instalar `pydantic-core` | Python 3.14 no venv | Recrie o venv: `py -3.13 -m venv .venv` |
| `API_KEY_INVALID` (Gemini) | Chave inválida ou API não habilitada | Crie nova key em **new project** no AI Studio |
| `insufficient_quota` / `429` (Gemini) | Cota do free tier esgotada | Use `GEMINI_MODEL=gemini-2.5-flash` ou aguarde reset |
| `bigquery.jobs.create permission` | Service Account sem papel | Adicione **BigQuery Job User** + **Data Viewer** no IAM |
| `ACCESS_TOKEN_SCOPE_INSUFFICIENT` | Escopos OAuth incorretos | Já corrigido em `app/core/bigquery.py`; reinicie a API |
| `500` com chave antiga após trocar `.env` | Servidor uvicorn em cache | Pare todos os processos na porta 8000 e suba de novo |
| Caminho JSON no `.env` com `/` no início | Path Unix no Windows | Use caminho absoluto Windows: `C:\...\arquivo.json` |

---

## Licença

Projeto desenvolvido como case técnico (Media Analyst AI Agent).
