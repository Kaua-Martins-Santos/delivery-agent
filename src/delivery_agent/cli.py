"""Chat no terminal (bom para gravar o GIF de demo).

Uso: python -m delivery_agent.cli --tenant cantina-nonna
"""

from __future__ import annotations

import argparse

from .container import build_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Converse com o agente de um restaurante")
    parser.add_argument("--tenant", default="cantina-nonna")
    parser.add_argument("--debug", action="store_true", help="mostra fontes, ferramentas e métricas")
    args = parser.parse_args()

    agent = build_agent()
    nome = agent.restaurants[args.tenant].nome
    print(f"Atendimento {nome} — modelo: {agent.llm.model}. Digite 'sair' para encerrar.\n")
    history: list[dict[str, str]] = []
    while True:
        try:
            msg = input("você > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"sair", "exit", "quit"}:
            break
        if not msg:
            continue
        r = agent.run(args.tenant, msg, history)
        print(f"{nome} > {r.answer}")
        if args.debug:
            tools = ", ".join(t["name"] for t in r.tool_calls) or "-"
            print(f"   fontes={r.sources} ferramentas={tools} bloqueio={r.blocked} "
                  f"latência={r.latency_ms}ms tokens={r.input_tokens}/{r.output_tokens}")
        print()
        history += [{"role": "user", "content": msg}, {"role": "assistant", "content": r.answer}]
        history = history[-10:]


if __name__ == "__main__":
    main()
