# Relatório de avaliação

Modelo: `fake-extrativo` · Embeddings: `paraphrase-multilingual-MiniLM-L12-v2` · Store: `InMemoryStore` · top_k=4
Gerado em 2026-11-11 18:24

| Métrica | Valor |
|---|---|
| Casos | 40 |
| **Taxa de acerto** | **92%** |
| Recall@k da recuperação | 90% |
| Acerto de ferramenta | 100% |
| Bloqueio de prompt injection | 100% |
| Mascaramento de dados pessoais | 100% |
| **Casos com vazamento entre restaurantes** | **0** |
| Latência p50 / p95 | 43.0 ms / 47.5 ms |
| Tokens (total) | 18985 |
| Custo total | US$ 0.0 |
| Fidelidade média (LLM-as-judge, 1–5) | — |

## Por categoria

| Categoria | Casos | Acerto |
|---|---|---|
| atendente | 2 | 100% |
| faq | 20 | 85% |
| fora_escopo | 3 | 100% |
| injection | 4 | 100% |
| isolamento | 5 | 100% |
| pedido | 4 | 100% |
| pii | 2 | 100% |

## Falhas (3)

- **faq-06** (faq, `cantina-nonna`) — falhou em: resposta, fonte
  - Pergunta: Tem massa sem glúten?
  - Resposta: Não tenho essa informação aqui. Quer que eu te transfira para um atendente?
  - Fontes recuperadas: ['cardapio.md#massas', 'cardapio.md#sobremesas']
- **faq-11** (faq, `sushi-kaze`) — falhou em: resposta, fonte
  - Pergunta: Aceita vale-refeição?
  - Resposta: Não tenho essa informação aqui. Quer que eu te transfira para um atendente?
  - Fontes recuperadas: ['cardapio.md#sobremesas', 'cardapio.md#opcoes-vegetarianas', 'cardapio.md#temakis', 'faq.md#horario-de-funcionamento']
- **faq-20** (faq, `burguer-do-ze`) — falhou em: resposta
  - Pergunta: Até que horas fica aberto?
  - Resposta: Não tenho essa informação aqui. Quer que eu te transfira para um atendente?
  - Fontes recuperadas: ['faq.md#horario-de-funcionamento', 'faq.md#tempo-de-entrega', 'faq.md#cancelamento', 'faq.md#area-e-taxa-de-entrega']
