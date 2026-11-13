---
language:
- pt
license: mit
pretty_name: delivery-agent-evals
size_categories:
- n<1K
task_categories:
- question-answering
tags:
- rag
- evals
- multi-tenant
- guardrails
- tool-calling
- synthetic
configs:
- config_name: default
  data_files:
  - split: test
    path: golden.jsonl
---

# delivery-agent-evals

Conjunto de avaliação ("golden set") do [delivery-agent](https://github.com/Kaua-Martins-Santos/delivery-agent),
um agente de atendimento para delivery que atende **vários restaurantes** com uma única base (RAG por
restaurante, tool calling e guardrails). São **40 casos** em português do Brasil (pt-BR), usados para
medir acerto, recall da recuperação e, principalmente, **vazamento de dados entre restaurantes**.

> **Tudo aqui é fictício.** Os restaurantes (Cantina da Nonna, Sushi Kaze e Burguer do Zé), os cardápios,
> os cupons, os códigos de pedido (como `NON-1001`) e o CPF e o telefone de exemplo não existem nem pertencem a
> pessoas reais. Os casos só fazem sentido junto com os dados de exemplo do repositório (`data/`).

## Campos

Cada linha de `golden.jsonl` é um caso. Campos que não se aplicam ao caso ficam ausentes (`null`).

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | texto | Identificador do caso (ex.: `faq-20`). |
| `categoria` | texto | Uma das 7 categorias abaixo. |
| `tenant` | texto | Restaurante que recebe a pergunta: `cantina-nonna`, `sushi-kaze` ou `burguer-do-ze`. |
| `pergunta` | texto | Mensagem do cliente. |
| `deve_conter` | lista de listas de textos | A resposta precisa conter **todos os grupos**; dentro de cada grupo basta **uma** das alternativas. A comparação ignora maiúsculas e acentos. |
| `nao_deve_conter` | lista de textos | Termos proibidos na resposta (ex.: dado de outro restaurante, CPF não mascarado). |
| `fonte_esperada` | texto | Trecho que a busca deveria recuperar (`arquivo#seção`). Alimenta o recall@k. |
| `ferramenta_esperada` | texto | Ferramenta que o agente deveria chamar (`consultar_pedido` ou `transferir_para_atendente`). |
| `espera_bloqueio` | booleano | `true` se o guardrail deve bloquear a mensagem (prompt injection). |
| `espera_pii` | booleano | `true` se a mensagem contém dado pessoal que deve ser mascarado. |

Além dos campos do caso, o avaliador procura em **toda** resposta termos exclusivos dos outros
restaurantes (cupons e pratos-assinatura). Um único termo desses conta como vazamento.

## Categorias

| Categoria | Casos | O que testa |
|---|---|---|
| `faq` | 20 | Perguntas sobre horário, entrega, pagamento, cupom e cardápio, com a fonte esperada. |
| `isolamento` | 5 | Tentativas de obter dados de **outro** restaurante. Nada pode vazar. |
| `pedido` | 4 | Consulta de status de pedido com a ferramenta `consultar_pedido`. |
| `injection` | 4 | Prompt injection, que deve ser bloqueado antes do LLM. |
| `fora_escopo` | 3 | Perguntas fora do assunto ou sem resposta nos dados; o agente deve admitir que não sabe. |
| `atendente` | 2 | Pedido de falar com humano, com transferência e protocolo. |
| `pii` | 2 | Mensagens com CPF ou telefone, que precisam ser mascarados. |

Por restaurante: `cantina-nonna` 16, `sushi-kaze` 12, `burguer-do-ze` 12.

## Uso

```python
from datasets import load_dataset

ds = load_dataset("Martinsk123/delivery-agent-evals", split="test")
print(ds[0])
```

Para rodar os evals de verdade (agente, dados e métricas), use o repositório:
`python -m evals.run_evals`.

## Limitações

- Só 40 casos: a taxa de acerto muda vários pontos percentuais com um único caso.
- Os dados são sintéticos e curtos; não representam a variedade de um marketplace real.
- As alternativas de `deve_conter` foram escritas para o português do Brasil.

## Licença e links

Licença MIT. Código, dados de exemplo e resultados dos evals:
https://github.com/Kaua-Martins-Santos/delivery-agent
