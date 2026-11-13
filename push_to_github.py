"""Push verified Day commits and tags via GitHub API."""
import argparse
import base64
import getpass
import os
from pathlib import Path

import requests

USERNAME = "omkadam78"
REPO = "GenAI-Traning-Program"
BRANCH = "main"
API_BASE = f"https://api.github.com/repos/{USERNAME}/{REPO}"
ROOT = Path(__file__).resolve().parent

# Define all day stages in order
ALL_STAGES = [
    {
        "id": "day-03",
        "message": "day-03: parse downloaded PMFBY documents in data/raw/ and export records.json",
        "tag": None,
        "files": [
            ".gitignore",
            "app/fetch.py",
            "app/ingest.py",
            "data/records.json",
            "data/raw/manifest.json",
            "data/raw/pmfby_faq.html",
            "data/raw/revamped_ogs_final.pdf",
            "data/raw/revised_operational_guidelines.pdf",
        ],
    },
    {
        "id": "day-04",
        "message": "day-04: add FastAPI service, TF-IDF smart search, and pandas explore script",
        "tag": "week-1",
        "files": [
            "README.md",
            "requirements.txt",
            "app/smart_search.py",
            "app/main.py",
            "analysis/__init__.py",
            "analysis/explore.py",
        ],
    },
    {
        "id": "day-05",
        "message": "day-05: add LLM guide, 10 evaluation questions, and Checkpoint 1 tests",
        "tag": "checkpoint-1",
        "files": [
            "docs/how_llms_work.md",
            "docs/questions.md",
            "eval/questions.json",
            "tests/test_records.py",
            "tests/test_api.py",
        ],
    },
    {
        "id": "day-06",
        "message": "day-06: add LLM provider wrapper, POST /chat, prompt templates, and evaluation comparison",
        "tag": None,
        "files": [
            ".env.example",
            "README.md",
            "requirements.txt",
            "app/llm.py",
            "app/main.py",
            "prompts/system_prompt.txt",
            "prompts/task_v1_concise.txt",
            "prompts/task_v2_detailed.txt",
            "eval/prompt_compare.md",
            "tests/test_api.py",
            "push_to_github.py",
        ],
    },
]


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _create_blob(headers: dict[str, str], path: Path) -> str:
    content = base64.b64encode(path.read_bytes()).decode("ascii")
    resp = requests.post(
        f"{API_BASE}/git/blobs",
        headers=headers,
        json={"content": content, "encoding": "base64"},
        timeout=(10, 120),
    )
    resp.raise_for_status()
    return resp.json()["sha"]


def _upsert_tag(headers: dict[str, str], tag_name: str, commit_sha: str) -> None:
    resp = requests.post(
        f"{API_BASE}/git/refs",
        headers=headers,
        json={"ref": f"refs/tags/{tag_name}", "sha": commit_sha},
        timeout=30,
    )
    if resp.status_code == 422:
        resp = requests.patch(
            f"{API_BASE}/git/refs/tags/{tag_name}",
            headers=headers,
            json={"sha": commit_sha, "force": True},
            timeout=30,
        )
    resp.raise_for_status()


def validate_stages(stages: list[dict]) -> None:
    for stage in stages:
        for rel in stage["files"]:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(f"Missing expected file for push: {rel}")


def get_pending_stages(token: str, target_stage_id: str | None = None) -> list[dict]:
    headers = _headers(token)
    r = requests.get(f"{API_BASE}/commits?per_page=20", headers=headers, timeout=30)
    r.raise_for_status()
    existing_messages = [c["commit"]["message"].splitlines()[0] for c in r.json()]

    pending = []
    for stage in ALL_STAGES:
        if target_stage_id and stage["id"] != target_stage_id:
            continue
        if any(stage["message"] in msg for msg in existing_messages):
            continue
        pending.append(stage)
    return pending


def push_stages(token: str, stages: list[dict]) -> None:
    if not stages:
        print("No pending stages to push.")
        return

    validate_stages(stages)
    headers = _headers(token)

    ref_resp = requests.get(f"{API_BASE}/git/ref/heads/{BRANCH}", headers=headers, timeout=30)
    ref_resp.raise_for_status()
    parent_commit_sha = ref_resp.json()["object"]["sha"]

    commit_resp = requests.get(
        f"{API_BASE}/git/commits/{parent_commit_sha}", headers=headers, timeout=30
    )
    commit_resp.raise_for_status()
    base_tree_sha = commit_resp.json()["tree"]["sha"]

    tags_to_create: list[tuple[str, str]] = []
    for stage in stages:
        tree_entries = []
        for rel in stage["files"]:
            blob_sha = _create_blob(headers, ROOT / rel)
            tree_entries.append(
                {
                    "path": rel,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }
            )
            print(f"  uploaded blob: {rel}")

        tree_resp = requests.post(
            f"{API_BASE}/git/trees",
            headers=headers,
            json={"base_tree": base_tree_sha, "tree": tree_entries},
            timeout=60,
        )
        tree_resp.raise_for_status()
        base_tree_sha = tree_resp.json()["sha"]

        new_commit_resp = requests.post(
            f"{API_BASE}/git/commits",
            headers=headers,
            json={
                "message": stage["message"],
                "tree": base_tree_sha,
                "parents": [parent_commit_sha],
            },
            timeout=30,
        )
        new_commit_resp.raise_for_status()
        parent_commit_sha = new_commit_resp.json()["sha"]
        print(f"Created commit {parent_commit_sha[:7]}: {stage['message']}")

        if stage.get("tag"):
            tags_to_create.append((stage["tag"], parent_commit_sha))

    update_resp = requests.patch(
        f"{API_BASE}/git/refs/heads/{BRANCH}",
        headers=headers,
        json={"sha": parent_commit_sha, "force": False},
        timeout=30,
    )
    update_resp.raise_for_status()
    print(f"Updated branch {BRANCH} -> {parent_commit_sha[:7]}")

    for tag_name, sha in tags_to_create:
        _upsert_tag(headers, tag_name, sha)
        print(f"Pushed tag {tag_name} -> {sha[:7]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Push verified Day work to GitHub.")
    parser.add_argument("--stage", type=str, default=None, help="Stage ID to push (e.g. day-06).")
    parser.add_argument("--dry-run", action="store_true", help="Verify stage files without pushing.")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token and not args.dry_run:
        token = getpass.getpass("Enter your GitHub token: ")
    token = token.strip()

    if args.dry_run:
        stages = [s for s in ALL_STAGES if not args.stage or s["id"] == args.stage]
        validate_stages(stages)
        for stage in stages:
            tag_info = f" [tag: {stage['tag']}]" if stage.get("tag") else ""
            print(f"{stage['message']}{tag_info}")
            for rel in stage["files"]:
                size = (ROOT / rel).stat().st_size
                print(f"  - {rel} ({size} bytes)")
        return

    if not token:
        raise SystemExit("GitHub token is required.")

    pending = get_pending_stages(token, args.stage)
    print(f"Found {len(pending)} pending stage(s) to push.")
    push_stages(token, pending)


if __name__ == "__main__":
    main()
