"""Sobe a demo para um Hugging Face Space: space/ (raiz) + src/ + data/.

Uso (depois de `hf auth login`):
  python scripts/deploy_space.py --dry-run          # só lista o que seria enviado
  python scripts/deploy_space.py                    # envia para Martinsk123/delivery-agent
  python scripts/deploy_space.py --repo usuario/outro-nome

Nunca envia .env, chaves nem tokens: arquivos suspeitos são ignorados e, se um segredo aparecer
dentro de um arquivo que seria enviado, o deploy é abortado. As chaves (ex.: GROQ_API_KEY) são
criadas como *secrets* nas configurações do Space, não no código.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "Martinsk123/delivery-agent"

# (pasta local, pasta dentro do Space). "" = raiz do Space (app.py, README.md, requirements.txt).
SOURCES = [(ROOT / "space", ""), (ROOT / "src", "src"), (ROOT / "data", "data")]

SKIP_DIRS = {"__pycache__", ".venv", "venv", ".git", ".pytest_cache", ".ipynb_checkpoints"}
SKIP_SUFFIXES = (".pyc", ".pem", ".key", ".p12", ".pfx", ".log")
SECRET_RE = re.compile(r"(gsk_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|hf_[A-Za-z0-9]{30,})")


def skipped(path: Path) -> bool:
    name = path.name
    return (
        name == ".env"
        or name.startswith(".env.")
        or name.endswith(SKIP_SUFFIXES)
        or any(part in SKIP_DIRS or part.endswith(".egg-info") for part in path.parts)
    )


def collect() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for folder, dest in SOURCES:
        if not folder.is_dir():
            sys.exit(f"Pasta não encontrada: {folder}")
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            rel = path.relative_to(folder)
            if skipped(rel):
                continue
            files.append((path, f"{dest}/{rel.as_posix()}" if dest else rel.as_posix()))
    return files


def find_secrets(files: list[tuple[Path, str]]) -> list[str]:
    hits = []
    for path, dest in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if SECRET_RE.search(text):
            hits.append(dest)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="id do Space: usuario/nome")
    parser.add_argument("--dry-run", action="store_true", help="lista os arquivos e não envia nada")
    args = parser.parse_args()

    files = collect()
    for _, dest in files:
        print(f"  {dest}")
    print(f"{len(files)} arquivos -> https://huggingface.co/spaces/{args.repo}")

    leaked = find_secrets(files)
    if leaked:
        print("ABORTADO: parece haver chave/token em:", *leaked, sep="\n  ", file=sys.stderr)
        return 1
    if args.dry_run:
        return 0

    from huggingface_hub import CommitOperationAdd, HfApi

    api = HfApi()
    try:
        who = api.whoami()
    except Exception:
        print("Você não está logado. Rode:  hf auth login", file=sys.stderr)
        return 1
    namespaces = {who["name"], *(o["name"] for o in who.get("orgs", []))}
    owner = args.repo.split("/")[0]
    if owner not in namespaces:
        print(
            f"O Space '{args.repo}' não pertence a você. Logado como '{who['name']}'.\n"
            f"Use:  python scripts/deploy_space.py --repo {who['name']}/delivery-agent",
            file=sys.stderr,
        )
        return 1

    api.create_repo(args.repo, repo_type="space", space_sdk="gradio", exist_ok=True)
    api.create_commit(
        repo_id=args.repo,
        repo_type="space",
        operations=[CommitOperationAdd(path_in_repo=dest, path_or_fileobj=str(path)) for path, dest in files],
        commit_message="Deploy da demo (space/ + src/ + data/)",
    )
    print(f"Pronto: https://huggingface.co/spaces/{args.repo}")
    print("Opcional: crie o secret GROQ_API_KEY nas configurações do Space para usar a Groq.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
