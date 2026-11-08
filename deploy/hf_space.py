"""Deploy the API to a Hugging Face Space (Docker SDK, free CPU tier).

Usage (from the repo root):
    pip install huggingface_hub
    set HF_TOKEN=hf_...            (a token with "write" access)
    python deploy/hf_space.py --space your-username/udyam-api
    python deploy/hf_space.py --space your-username/udyam-api --dry-run   # stage only

What it does:
  1. Stages exactly what the Docker image needs: apps/api (no venv, caches or
     tests), data/, scripts/seed_db.py, the Dockerfile at the Space root and
     the Space README (its YAML header tells HF to build with Docker on :8000).
  2. Creates the Space if it doesn't exist (Docker SDK).
  3. Uploads with the Hub API, which stores the KYC PNGs as large files
     (a plain `git push` of binary files is rejected by the Hub).
  4. Optionally sets the Space's secrets from --env-file (KEY=VALUE lines).

The GitHub Action .github/workflows/deploy-api.yml runs this on every push.
"""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "tests", ".storage", ".mypy_cache"}
SKIP_FILES = {".env"}


def stage(dest: Path) -> None:
    def ignore(_dir: str, names: list[str]) -> set[str]:
        return {n for n in names if n in SKIP_DIRS or n in SKIP_FILES or n.endswith(".pyc")}

    shutil.copytree(ROOT / "apps" / "api", dest / "apps" / "api", ignore=ignore)
    shutil.copytree(ROOT / "data", dest / "data", ignore=ignore)
    (dest / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "seed_db.py", dest / "scripts" / "seed_db.py")
    shutil.copy2(ROOT / "apps" / "api" / "Dockerfile", dest / "Dockerfile")
    shutil.copy2(ROOT / "deploy" / "huggingface" / "README.md", dest / "README.md")


def read_env_file(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if value.strip():
                out[key.strip()] = value.strip()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space", required=True, help="owner/space-name, e.g. debanjan/udyam-api")
    ap.add_argument("--env-file", type=Path, help="KEY=VALUE file to set as Space secrets")
    ap.add_argument("--dry-run", action="store_true", help="stage files and list them; upload nothing")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="udyam-space-") as tmp:
        dest = Path(tmp)
        stage(dest)
        files = [p for p in dest.rglob("*") if p.is_file()]
        size = sum(p.stat().st_size for p in files) / 2**20
        print(f"Staged {len(files)} files ({size:.1f} MB) for {args.space}")
        if args.dry_run:
            for p in sorted(files)[:40]:
                print("  ", p.relative_to(dest))
            return

        token = os.environ.get("HF_TOKEN")
        if not token:
            sys.exit("Set HF_TOKEN to a Hugging Face token with write access.")
        from huggingface_hub import HfApi

        api = HfApi(token=token)
        api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)
        if args.env_file:
            for key, value in read_env_file(args.env_file).items():
                api.add_space_secret(args.space, key, value)
            print(f"Set secrets from {args.env_file}")
        api.upload_folder(
            repo_id=args.space,
            repo_type="space",
            folder_path=str(dest),
            commit_message="Deploy Udyam Digital API",
            delete_patterns=["apps/**", "data/**", "scripts/**"],
        )
    owner, name = args.space.split("/", 1)
    print(f"Uploaded. Build logs: https://huggingface.co/spaces/{args.space}")
    print(f"API (once built):    https://{owner}-{name}.hf.space/docs".replace("_", "-").lower())


if __name__ == "__main__":
    main()
