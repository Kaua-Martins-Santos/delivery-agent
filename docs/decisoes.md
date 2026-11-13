# Decisões técnicas

Registro curto do porquê de cada escolha (formato inspirado em ADRs).

## 1. Isolamento por arquitetura, não por prompt

**Contexto:** dizer ao modelo "não fale de outros restaurantes" não impede vazamento. Um prompt
injection ou um erro do modelo basta.

**Decisão:** o modelo nunca *recebe* dados de outro restaurante. A busca é filtrada pelo tenant,
o banco aplica Row-Level Security e as ferramentas recebem o tenant do contexto da requisição,
descartando qualquer `tenant_id` que o modelo tente passar.

**Consequência:** mesmo um modelo totalmente manipulado não tem acesso ao dado. Os evals verificam
isso varrendo todas as respostas atrás de termos exclusivos dos outros restaurantes.

## 2. RLS com falha fechada

`current_setting('app.tenant_id', true)` devolve `NULL` quando a variável não foi definida, e
`tenant_id = NULL` nunca é verdadeiro. Esquecer de definir o tenant resulta em **zero linhas**, não
em todas. A aplicação conecta com um usuário sem `SUPERUSER` e sem `BYPASSRLS`, porque superusuários
ignoram RLS. O `set_config(..., true)` vale só para a transação, o que é seguro com pool de conexões.

## 3. Evals como gate do CI

Evals que ninguém roda não protegem nada. O CI falha se houver **qualquer** vazamento ou se o
acerto cair abaixo de 85%. Mudança de prompt, de modelo ou de chunking passa pelo mesmo crivo
que mudança de código.

## 4. LLM fake como baseline, não só como mock

O `FakeLLM` copia as frases do contexto mais parecidas com a pergunta. Além de deixar o CI
gratuito e determinístico, ele é um **baseline extrativo**: se um LLM real não superar esse número,
o custo dele não está se pagando.

## 5. Guardrail de entrada antes do LLM

Bloquear injection óbvia com regex custa microssegundos e zero tokens. É uma camada de economia
e redução de ruído, **não** de segurança: a segurança está nas decisões 1 e 2.

## 6. Chunk por seção do Markdown

FAQs de restaurante são curtas e cada seção responde uma pergunta. Quebrar por seção (`## `)
mantém a resposta inteira num chunk só e deixa a fonte citável (`faq.md#cancelamento`), o que
permite medir recall da recuperação nos evals.

## 7. Vetores de 384 dimensões

O baseline por hashing e o modelo `paraphrase-multilingual-MiniLM-L12-v2` geram 384 dimensões.
Assim a mesma coluna `vector(384)` serve para os dois, e o modelo é pequeno o bastante para rodar
em CPU, sem custo.

## 8. MIN_SCORE calibrado por embedder

**Contexto:** cada modelo de embedding tem sua escala de similaridade. Com o e5 todos os trechos
pontuam entre 0,84 e 0,89, então o `MIN_SCORE=0.12` herdado do hash não filtrava nada: o LLM
recebia sempre `top_k` trechos, inclusive irrelevantes (mais tokens e mais ruído).

**Método:** `scripts/calibra_min_score.py` roda os 40 casos com LLM fake para vários limites. O
recall@k é medido **depois** do filtro (`r.sources` em `agent.py` só contém os trechos aprovados),
então um limite alto demais derruba o recall de verdade, e a medida é honesta.

| Embedder | Limite | recall@k | acerto | trechos/pergunta |
|---|---|---|---|---|
| hash | 0.05 | 95% | 95% | 2.77 |
| hash | **0.10** | **95%** | **95%** | **1.77** |
| hash | 0.15 | 90% | 92,5% | 1.18 |
| e5 | 0.80 | 100% | 95% | 3.50 |
| e5 | **0.82** | **100%** | **95%** | **2.95** |
| e5 | 0.84 | 95% | 95% | 1.88 |
| e5 | 0.86 | 85% | 90% | 0.95 |

**Decisão:** o maior limite que mantém o recall máximo: **hash/local 0.10** e **e5 0.82**. Ficam
como padrão em `config.py`; a variável `MIN_SCORE` do `.env` continua sobrescrevendo.

**Ressalva:** o conjunto tem só 40 casos, então a calibração é grosseira (o e5 cai de 100% para
95% já em 0.84). Por isso escolhi o limite na borda segura, e não o que maximiza economia.
O `local` (MiniLM) usa o mesmo valor do hash por falta de medição própria.
