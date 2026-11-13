"""Calibra o MIN_SCORE de cada embedder usando os evals (LLM fake, sem custo).

Para cada limite mostra: recall@k (medido DEPOIS do filtro, como em agent.py), taxa de acerto
e a média de trechos enviados ao LLM por pergunta.

Uso:
  python scripts/calibra_min_score.py                 # hash e e5
  python scripts/calibra_min_score.py --embedder hash
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
os.environ["LLM_PROVIDER"] = "fake"  # calibrar nunca deve gastar tokens

from delivery_agent.config import Settings  # noqa: E402
from delivery_agent.container import build_agent  # noqa: E402
from evals.run_evals import DEFAULT_DATASET, evaluate_case, load_cases, rate  # noqa: E402

GRIDS = {
    "hash": [round(0.05 + 0.05 * i, 2) for i in range(8)],   # 0.05 .. 0.40
    "e5": [round(0.70 + 0.02 * i, 2) for i in range(12)],    # 0.70 .. 0.92
}


def calibrate(embedder: str) -> list[dict]:
    os.environ["EMBEDDER"] = embedder
    base = Settings.from_env()
    agent = build_agent(base)
    cases = load_cases(DEFAULT_DATASET)
    rows = []
    for limit in GRIDS[embedder]:
        agent.settings = dataclasses.replace(base, min_score=limit)
        results, chunks = [], []
        for case in cases:
            r = agent.run(case["tenant"], case["pergunta"])
            results.append(evaluate_case(case, r, agent.restaurants))
            chunks.append(len(r.sources))
        recall = [c.checks["fonte"] for c in results if c.checks["fonte"] is not None]
        rows.append(
            {
                "limite": limit,
                "recall": rate(recall),
                "acerto": rate([c.passou for c in results]),
                "trechos": round(sum(chunks) / len(chunks), 2),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", choices=list(GRIDS), action="append")
    args = parser.parse_args()
    for emb in args.embedder or list(GRIDS):
        print(f"\n== EMBEDDER={emb} ==")
        print("limite | recall@k | acerto | trechos/pergunta")
        rows = calibrate(emb)
        for r in rows:
            print(f"{r['limite']:>6} | {r['recall']:>8.1%} | {r['acerto']:>6.1%} | {r['trechos']:>5}")
        best = max(r["recall"] for r in rows)
        # Maior limite que ainda mantém o recall máximo (e o melhor acerto entre eles) = menos trechos.
        ok = [r for r in rows if r["recall"] == best]
        top_acerto = max(r["acerto"] for r in ok)
        pick = max((r for r in ok if r["acerto"] == top_acerto), key=lambda r: r["limite"])
        print(f"-> sugestão: MIN_SCORE={pick['limite']} (recall {pick['recall']:.1%}, {pick['trechos']} trechos)")


if __name__ == "__main__":
    main()
