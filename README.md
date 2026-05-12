# Media Analyst AI Agent

> MVP de um Agente de IA Autônomo que atua como "Analista Júnior de Mídia",  
> capaz de responder perguntas em linguagem natural consultando o dataset público  
> **thelook_ecommerce** no Google BigQuery.

---

## Sumário

- [Arquitetura](#arquitetura)
- [Tools do Agente](#tools-do-agente)
- [Stack Técnica](#stack-técnica)
- [Pré-requisitos](#pré-requisitos)
- [Setup](#setup)
- [Executando a API](#executando-a-api)
- [Exemplos de uso](#exemplos-de-uso)
- [Estrutura de Pastas](#estrutura-de-pastas)

---

## Arquitetura

O agente segue o padrão **ReAct** (Reason + Act) implementado com **LangGraph**:

```
Pergunta do usuário
       │
       ▼
  ┌──────────┐   tool_calls?   ┌──────────────────┐
  │ LLM Node │ ──────────────► │  Tools Node (BQ) │
  │ (GPT-4o) │                 │  executa SQL     │
  └──────────┘                 └──────────────────┘
       ▲                               │
       │    resultado da tool          │
       └───────────────────────────────┘
             loop até resposta final
                      │
                      ▼
            Insight em linguagem natural
```

### Fluxo detalhado

1. O usuário envia uma pergunta via `POST /api/v1/chat`.
2. O **LLM Node** (ChatOpenAI) recebe a pergunta + histórico de conversa + system prompt.
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
| Web Framework | FastAPI 0.115 |
| Orquestrador de IA | LangGraph 0.2 |
| LLM | OpenAI GPT-4o (via LangChain) |
| Data Warehouse | Google BigQuery (cliente Python oficial) |
| Validação | Pydantic v2 |
| Servidor ASGI | Uvicorn |

---

## Pré-requisitos

- Python 3.10+
- Conta Google Cloud (gratuita) com acesso ao BigQuery
- Chave de API da OpenAI

---

## Setup

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/media-analyst-agent.git
cd media-analyst-agent
```

### 2. Crie e ative um ambiente virtual

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as credenciais do Google Cloud

#### Opção A — Service Account (recomendado para produção)

1. Acesse o [Console GCP](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Crie uma Service Account com a role **BigQuery Data Viewer** + **BigQuery Job User**
3. Gere e baixe a chave JSON
4. Anote o caminho do arquivo e o ID do projeto

#### Opção B — Application Default Credentials (desenvolvimento local)

```bash
gcloud auth application-default login
```

Nesse caso, defina `GOOGLE_APPLICATION_CREDENTIALS` apontando para o arquivo gerado em `~/.config/gcloud/`.

### 5. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env`:

```env
OPENAI_API_KEY=sk-...                        # sua chave OpenAI
GOOGLE_APPLICATION_CREDENTIALS=/caminho/para/service-account.json
GCP_PROJECT_ID=seu-projeto-gcp               # ex: my-project-123456
OPENAI_MODEL=gpt-4o                          # ou gpt-4o-mini para menor custo
```

---

## Executando a API

```bash
uvicorn app.main:app --reload --port 8000
```

A documentação interativa (Swagger UI) estará disponível em:  
**http://localhost:8000/docs**

---

## Exemplos de uso

### Via curl

```bash
# Volume de tráfego do canal Search no último mês
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Como foi o volume de usuários vindos de Search no último mês?",
    "history": []
  }'

# Comparação de canais
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Qual dos canais tem a melhor performance? E por quê?",
    "history": []
  }'

# Pergunta de follow-up (multi-turn)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "E como foi a tendência de receita do Facebook nos últimos 6 meses?",
    "history": [
      {"role": "user", "content": "Qual dos canais tem a melhor performance?"},
      {"role": "assistant", "content": "O canal Organic liderou com..."}
    ]
  }'
```

### Resposta esperada

```json
{
  "answer": "No último mês, o canal **Search** trouxe **12.430 novos usuários**, sendo o segundo maior canal de aquisição. Comparado com Organic (15.210 usuários), Search gerou uma taxa de conversão ligeiramente maior (3,2% vs 2,9%), indicando uma intenção de compra mais alta...",
  "model": "gpt-4o"
}
```

---

## Estrutura de Pastas

```
.
├── app/
│   ├── main.py                    # Entry point FastAPI
│   ├── api/
│   │   ├── __init__.py            # Router principal (prefixo /api/v1)
│   │   └── routes/
│   │       └── chat.py            # POST /api/v1/chat
│   ├── agent/
│   │   ├── agent.py               # LangGraph graph + run_agent()
│   │   └── tools/
│   │       └── bigquery_tools.py  # 5 tools com queries BigQuery
│   ├── core/
│   │   ├── config.py              # Settings via pydantic-settings
│   │   └── bigquery.py            # Cliente BigQuery (singleton)
│   └── schemas/
│       └── chat.py                # Pydantic models (request/response)
├── requirements.txt
├── .env.example
└── README.md
```
