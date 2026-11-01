# Arquitetura

## Fluxo de uma mensagem

```mermaid
sequenceDiagram
    participant C as Cliente
    participant A as API (/chat)
    participant G as Guardrails
    participant S as Store (pgvector + RLS)
    participant L as LLM
    participant T as Ferramentas

    C->>A: mensagem + X-Tenant-ID
    A->>G: looks_like_injection?
    alt é ataque
        G-->>A: resposta padrão (0 tokens gastos)
    else ok
        G->>G: mask_pii (CPF, telefone, e-mail, cartão)
        A->>S: search(tenant_id, embedding, k)
        S-->>A: chunks só daquele restaurante
        A->>L: system prompt (regras + contexto + canary) + mensagem
        loop até MAX_STEPS
            L-->>A: tool_call?
            A->>T: execute(call, ToolContext(tenant_id))
            T->>S: consulta com o tenant da requisição
            T-->>L: resultado (JSON)
        end
        L-->>A: resposta final
        A->>G: canary apareceu na resposta?
    end
    A-->>C: resposta + fontes + métricas
```

## Componentes

| Módulo | Responsabilidade |
|---|---|
| `agent.py` | Orquestra o fluxo acima e mede latência, tokens e custo |
| `store.py` | Interface `VectorStore` com duas implementações: `InMemoryStore` e `PgVectorStore` |
| `orders.py` | Repositório de pedidos, também com implementação em memória e em Postgres |
| `tools.py` | Especificação das ferramentas (JSON Schema) e execução com `ToolContext` |
| `guardrails.py` | Regras baratas que rodam antes e depois do LLM |
| `llm/` | Interface única `LLM.chat(system, messages, tools)` e adaptadores por provedor |
| `embeddings.py` | Interface `Embedder` com baseline por hashing e modelo semântico local |
| `ingest.py` | Lê os Markdown de cada restaurante, quebra por seção e indexa |
| `container.py` | Monta tudo a partir das variáveis de ambiente |

## Por que interfaces para tudo

Cada peça externa (LLM, embeddings, banco) tem uma interface e pelo menos duas implementações.
Isso permite:

1. **Testes e CI sem custo**: tudo roda offline com `FakeLLM`, `HashEmbedder` e `InMemoryStore`.
2. **Comparação justa**: o mesmo dataset de evals roda em qualquer combinação, então dá para medir
   quanto um modelo maior ou um embedding melhor realmente agrega.
3. **Troca de provedor sem mudar código**: só o `.env`.
