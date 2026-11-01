# 🛵 delivery-agent

[![CI](https://github.com/Kaua-Martins-Santos/delivery-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaua-Martins-Santos/delivery-agent/actions/workflows/ci.yml)

**Agente de atendimento com IA para um app de delivery multi-restaurante** — RAG por restaurante, tool calling,
guardrails e uma suíte de **evals** que roda no CI e **bloqueia o merge se houver vazamento de dados entre restaurantes**.

> Num marketplace, o mesmo agente atende milhares de restaurantes. Responder errado é ruim;
> responder com o cupom, o cardápio ou o pedido de **outro** restaurante é um incidente.
> Este projeto trata isolamento como requisito de arquitetura, não como instrução no prompt.

<!-- Grave com: python -m delivery_agent.cli --tenant cantina-nonna --debug -->
<!-- ![demo](docs/demo.gif) -->

## O que ele faz

- 💬 Responde dúvidas (horário, taxa, cardápio, alergias, cancelamento) **só com base nos documentos do restaurante**
- 📦 Consulta status de pedido via **tool calling** (`consultar_pedido`)
- 🙋 Transfere para atendente humano em reclamação/reembolso (`transferir_para_atendente`)
- 🛡️ Bloqueia prompt injection antes de gastar chamada de LLM, mascara CPF/telefone/e-mail e detecta vazamento do system prompt com *canary token*
- 📊 Mede tudo: acerto, recall da recuperação, acerto de ferramenta, vazamentos, latência p50/p95, tokens e custo por conversa
- 🔌 Troca de provedor sem mudar código: Claude, OpenAI, Groq, Ollama ou um **LLM fake** determinístico para o CI

## Arquitetura

```mermaid
flowchart LR
    C[Cliente] -->|mensagem + X-Tenant-ID| API[FastAPI /chat]
    API --> G1{Guardrail de entrada<br/>injection? PII?}
    G1 -->|ataque| B[Resposta padrão<br/>sem chamar LLM]
    G1 -->|ok, PII mascarada| R[Busca vetorial<br/>FILTRADA pelo tenant]
    R --> DB[(Postgres + pgvector<br/>Row-Level Security)]
    R --> L[LLM + ferramentas]
    L -->|consultar_pedido| T[Ferramentas<br/>tenant vem do contexto,<br/>nunca do LLM]
    T --> DB
    L --> G2{Guardrail de saída<br/>canary vazou?}
    G2 --> API
```

Detalhes em [`docs/arquitetura.md`](docs/arquitetura.md) e decisões em [`docs/decisoes.md`](docs/decisoes.md).

### Isolamento multi-tenant em 4 camadas

| Camada | Onde | O que garante |
|---|---|---|
| 1. Contrato da store | `store.py` | Não existe busca sem `tenant_id`; vazio → erro (falha fechada) |
| 2. Query | `store.py`, `orders.py` | `WHERE tenant_id = %s` em toda consulta |
| 3. Banco | `db/init.sql` | **Row-Level Security**: sem `app.tenant_id` definido, o banco devolve 0 linhas, mesmo se alguém esquecer o `WHERE` |
| 4. Ferramentas | `tools.py` | O tenant vem da requisição autenticada; argumentos extras inventados pelo LLM (ex.: `tenant_id`) são descartados |

Pedido de outro restaurante recebe a **mesma resposta** de pedido inexistente: o sistema nem revela que o dado existe.

## Evals

```bash
python -m evals.run_evals            # gera evals/reports/latest-<provedor>-<embedder>.md
python -m evals.run_evals --judge    # + LLM-as-judge de fidelidade (com LLM real)
```

40 casos em [`evals/datasets/golden.jsonl`](evals/datasets/golden.jsonl), divididos em 7 categorias:
FAQ, pedido, **isolamento**, **prompt injection**, fora de escopo, atendente humano e dados pessoais.

Além do que cada caso pede, **toda resposta é varrida** em busca de termos exclusivos dos outros
restaurantes (cupons, pratos-assinatura). Um único vazamento reprova o CI.

**Baseline** (LLM fake extrativo + embeddings por hashing, sem custo — o que roda no CI):

| Métrica | Valor |
|---|---|
| Taxa de acerto | 95% (38/40) |
| Recall@k da recuperação | 95% |
| Acerto de ferramenta | 100% |
| Bloqueio de prompt injection | 100% |
| **Vazamentos entre restaurantes** | **0** |

As 2 falhas do baseline são instrutivas: busca lexical não liga *"até que horas fica aberto"* a
*"abrimos das 17h à 1h"*, e um extrator sem raciocínio responde algo aleatório em vez de admitir
que não sabe. É exatamente o que embeddings semânticos e um LLM de verdade devem resolver, e os evals
medem se resolvem.

## Como rodar

Requer Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

pytest                                              # 40 testes, offline
python -m evals.run_evals                           # evals com o baseline
python -m delivery_agent.cli --tenant sushi-kaze --debug   # chat no terminal
uvicorn delivery_agent.api:app --reload             # API em http://localhost:8000/docs
```

```bash
curl -X POST localhost:8000/chat -H "X-Tenant-ID: cantina-nonna" \
     -H "Content-Type: application/json" -d '{"mensagem": "cadê meu pedido NON-1001?"}'
```

### Com um LLM de verdade

```bash
pip install -e ".[anthropic]"   # ou ".[openai]" para OpenAI / Groq / Ollama
# no .env: LLM_PROVIDER=anthropic e ANTHROPIC_API_KEY=...
pip install -e ".[embeddings]"  # embeddings semânticos locais; no .env: EMBEDDER=local
python -m evals.run_evals --judge
```

### Com Postgres + pgvector + RLS

```bash
docker compose up -d
pip install -e ".[postgres]"
# no .env: STORE=postgres e DATABASE_URL=postgresql://app_user:app_user_dev@localhost:5432/delivery
python -m delivery_agent.ingest
TEST_DATABASE_URL=$DATABASE_URL pytest tests/test_pg_rls.py
```

## Estrutura

```
src/delivery_agent/
  agent.py         orquestração: guardrails → RAG → LLM com ferramentas → checagem de saída
  store.py         busca vetorial com isolamento (memória e pgvector)
  tools.py         ferramentas do agente
  guardrails.py    injection, PII, canary
  prompts.py       system prompt versionado
  llm/             adaptadores: fake, anthropic, openai-compatível
  embeddings.py    hashing (baseline) e sentence-transformers
  api.py · cli.py · ingest.py
evals/             dataset dourado + runner + relatórios
tests/             unitários, API, adaptadores e integração do RLS
db/init.sql        schema com Row-Level Security
data/              3 restaurantes fictícios e pedidos de exemplo
```

## Limitações conhecidas

- O guardrail de injection é heurístico (regex). Ataques criativos passam; por isso a proteção de dados
  não depende dele, e sim das camadas de isolamento.
- Prompt injection **indireta** (instrução maliciosa dentro de um documento do restaurante) ainda não tem teste.
- Uma conexão por consulta no Postgres; em produção seria um pool.
- O tenant chega por header para simplificar; em produção viria de um token assinado (JWT).

## Próximos passos

- [ ] Rodar os evals com LLM real e embeddings semânticos e comparar com o baseline
- [ ] Busca híbrida (BM25 + vetorial) e reranking
- [ ] Casos de injection indireta e de conversa com múltiplos turnos
- [ ] Rastreamento por requisição (OpenTelemetry) e cache de respostas frequentes

## Licença

MIT
