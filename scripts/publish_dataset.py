"""Publica o dataset de evals no Hugging Face Hub (golden.jsonl + dataset card).

Uso (depois de `hf auth login`):
  python scripts/publish_dataset.py --dry-run      # valida e lista, não envia nada
  python scripts/publish_dataset.py                # cria/atualiza Martinsk123/delivery-agent-evals
  python scripts/publish_dataset.py --repo usuario/outro-nome

O dataset é público. O card (evals/datasets/dataset_card.md) vira o README.md do dataset.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "datasets" / "golden.jsonl"
CARD = ROOT / "evals" / "datasets" / "dataset_card.md"
DEFAULT_REPO = "Martinsk123/delivery-agent-evals"
REQUIRED = {"id", "categoria", "tenant", "pergunta"}


def validate() -> Counter:
    rows = []
    for n, line in enumerate(DATASET.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)  # JSON inválido aborta aqui
        missing = REQUIRED - row.keys()
        if missing:
            sys.exit(f"Linha {n} sem campos obrigatórios: {sorted(missing)}")
        rows.append(row)
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        sys.exit("Há ids repetidos no dataset.")
    return Counter(r["categoria"] for r in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="id do dataset: usuario/nome")
    parser.add_argument("--dry-run", action="store_true", help="valida e lista, sem enviar")
    args = parser.parse_args()

    counts = validate()
    print(f"{sum(counts.values())} casos: {dict(counts)}")
    # O card cita a quantidade de cada categoria; se o dataset mudar, o aviso lembra de atualizar.
    card = CARD.read_text(encoding="utf-8")
    for cat, n in counts.items():
        if f"| `{cat}` | {n} |" not in card:
            sys.exit(f"O card não bate com o dataset para '{cat}' ({n} casos). Atualize {CARD.name}.")
    print(f"  golden.jsonl  <- {DATASET.relative_to(ROOT)}")
    print(f"  README.md     <- {CARD.relative_to(ROOT)}")
    print(f"-> https://huggingface.co/datasets/{args.repo}")
    if args.dry_run:
        return 0

    from huggingface_hub import CommitOperationAdd, HfApi

    api = HfApi()
    try:
        who = api.whoami()
    except Exception:
        print("Você não está logado. Rode:  hf auth login", file=sys.stderr)
        return 1
    owner = args.repo.split("/")[0]
    if owner not in {who["name"], *(o["name"] for o in who.get("orgs", []))}:
        print(f"O dataset '{args.repo}' não pertence a você (logado como '{who['name']}').", file=sys.stderr)
        return 1

    api.create_repo(args.repo, repo_type="dataset", exist_ok=True)
    api.create_commit(
        repo_id=args.repo,
        repo_type="dataset",
        operations=[
            CommitOperationAdd(path_in_repo="golden.jsonl", path_or_fileobj=str(DATASET)),
            CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=str(CARD)),
        ],
        commit_message="Publica golden.jsonl e dataset card",
    )
    print(f"Pronto: https://huggingface.co/datasets/{args.repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
