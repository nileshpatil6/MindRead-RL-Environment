"""
Bulk secret generation script — generates additional secrets via Groq LLM.
Run this before the hackathon to top up the secrets vault.

Usage:
    python scripts/generate_secrets.py --count 10 --category factual --difficulty 0.5
    python scripts/generate_secrets.py --count 50 --all-categories
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.secret_generator import generate_secret

SECRETS_PATH = Path(__file__).parent.parent / "server" / "data" / "secrets.json"

CATEGORY_CONFIGS = [
    ("factual", 0.3, "tech startup"),
    ("factual", 0.7, "enterprise software"),
    ("belief", 0.55, "tech company"),
    ("belief", 0.65, "consulting firm"),
    ("goal", 0.6, "startup"),
    ("goal", 0.65, "tech company"),
    ("second_order", 0.85, "venture-backed startup"),
    ("second_order", 0.9, "enterprise"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--category", default=None,
                        choices=["factual", "belief", "goal", "second_order"])
    parser.add_argument("--difficulty", type=float, default=0.5)
    parser.add_argument("--domain", default="tech startup")
    parser.add_argument("--all-categories", action="store_true")
    args = parser.parse_args()

    existing = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    print(f"Existing secrets: {len(existing)}")

    new_secrets = []

    if args.all_categories:
        configs = CATEGORY_CONFIGS * (args.count // len(CATEGORY_CONFIGS) + 1)
        configs = configs[:args.count]
    else:
        configs = [(args.category or "factual", args.difficulty, args.domain)] * args.count

    for i, (cat, diff, domain) in enumerate(configs):
        print(f"Generating {i+1}/{len(configs)}: category={cat} difficulty={diff} domain={domain} ...", end=" ", flush=True)
        try:
            secret = generate_secret(category=cat, difficulty=diff, domain=domain)
            new_secrets.append(secret)
            print(f"OK — {secret['id']}")
            time.sleep(2.5)  # Groq rate limit: 30 req/min
        except Exception as e:
            print(f"FAILED: {e}")

    all_secrets = existing + new_secrets
    SECRETS_PATH.write_text(json.dumps(all_secrets, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. Total secrets: {len(all_secrets)} (+{len(new_secrets)} new)")


if __name__ == "__main__":
    main()
