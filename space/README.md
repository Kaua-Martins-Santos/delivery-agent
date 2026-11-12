---
title: delivery-agent
emoji: 🛵
colorFrom: red
colorTo: yellow
sdk: gradio
sdk_version: 6.31.0
python_version: "3.11"
app_file: app.py
pinned: false
license: mit
short_description: Agente multi-tenant para delivery com RAG, tools e guardrails
---

# 🛵 delivery-agent

Demo do [delivery-agent](https://github.com/Kaua-Martins-Santos/delivery-agent): um agente de
atendimento para delivery que atende **vários restaurantes** com uma única base, sem vazar dados
de um para o outro.

Escolha um restaurante, converse e olhe o painel **Por dentro**: fontes recuperadas, se o guardrail
bloqueou e qual ferramenta foi chamada. Os botões de exemplo mostram uma pergunta normal, um status
de pedido, um prompt injection e uma tentativa de pegar o cupom de **outro** restaurante.

## Configuração

Por padrão roda **grátis em CPU**: `LLM_PROVIDER=fake` (LLM extrativo, sem custo) e
`EMBEDDER=e5` (intfloat/multilingual-e5-small).

Para usar um LLM de verdade, crie o secret **`GROQ_API_KEY`** nas configurações do Space. O app passa
a usar a Groq pelo adaptador OpenAI-compatível, sem mudar o código do agente. O modelo padrão é
`llama-3.3-70b-versatile`; troque com a variável `GROQ_MODEL`.
