#!/usr/bin/env python3
"""
benchmark_tokens.py — measure SKILL.md tokens accurately and compare
"with skill" vs "without skill" for typical tasks.

Uses tiktoken (cl100k_base, GPT-4 tokenizer) as a public approximation of
Claude's tokenizer. Real Claude usage may differ by ±5%.

Run from repo root:
    python3 scripts/benchmark_tokens.py
"""

import os
import re
import sys
from pathlib import Path

try:
    import tiktoken
except ImportError:
    print("Install tiktoken: pip install tiktoken", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).parent.parent
enc = tiktoken.get_encoding("cl100k_base")


def tok(s: str) -> int:
    return len(enc.encode(s))


def measure_skills():
    """Return list of dicts with per-skill token measurements."""
    rows = []
    for skill_dir in sorted((ROOT / "skills").iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        fm, body = parts[1], parts[2]

        desc_match = re.search(
            r"^description:\s*(.+?)(?=\n[a-z][a-z-]*:|\n---|\Z)",
            fm, re.MULTILINE | re.DOTALL
        )
        desc = desc_match.group(1).strip() if desc_match else ""

        rows.append({
            "skill": skill_dir.name,
            "fm_tokens": tok(fm),
            "desc_tokens": tok(desc),
            "body_tokens": tok(body),
        })
    return rows


# Realistic "without skill" baselines per skill, in tokens.
# These are estimates based on what Claude would generate ad-hoc for a
# typical task per service, given common API knowledge in training data.
#
# Format: (typical_task_response_tokens, retry_probability)
# Retry probability is 0-1 (how often Claude needs a second attempt for
# this API on a given task).
WITHOUT_SKILL_BASELINE = {
    # Well-known APIs Claude usually gets right first try
    "trello":         (700, 0.20),    # REST, well-known
    "slack":          (800, 0.20),    # Web API, well-known
    "heroku":         (900, 0.30),    # Platform API v3 less common
    "aws-s3":         (600, 0.10),    # AWS CLI very well-known
    "firebase":       (900, 0.35),    # multi-product, varies
    "rspec":          (500, 0.15),    # Rails dev knows
    "react-native":   (650, 0.20),    # RN dev knows
    "k6":             (1000, 0.40),   # script generation needs care
    "brakeman":       (500, 0.20),    # static tool
    "bundler-audit":  (500, 0.20),    # static tool
    "rails-security": (700, 0.25),    # combined tool
    # Less-common APIs Claude often retries
    "azure-devops":   (1500, 0.50),   # Server quirks, WIQL syntax
    "sentry":         (900, 0.35),    # multi-org confusing
    "postgres":       (700, 0.20),    # SQL standard
    "maestro":        (1100, 0.45),   # YAML schema needs lookup
    "fastlane":       (1400, 0.55),   # Ruby DSL + signing complex
    "shopify":        (1200, 0.40),   # GraphQL queries
    "xlsx-testcases": (2500, 0.70),   # custom workflow, no public template
}


def without_skill_cost(skill_name: str) -> int:
    """Effective tokens for one ad-hoc task, including retry probability."""
    base, retry_prob = WITHOUT_SKILL_BASELINE.get(skill_name, (1000, 0.30))
    # Retry costs ~50% of base (partial regeneration)
    return round(base + base * retry_prob * 0.5)


def main():
    rows = measure_skills()

    total_fm = sum(r["fm_tokens"] for r in rows)
    total_desc = sum(r["desc_tokens"] for r in rows)
    total_body = sum(r["body_tokens"] for r in rows)

    print("=" * 78)
    print("CLAUDE-TEAM-TOOLKIT TOKEN BENCHMARK (tiktoken cl100k_base)")
    print("=" * 78)
    print()
    print(f"{'Skill':<20} {'FM':>6} {'Desc':>6} {'Body':>7} {'W/O 1×':>8} {'Save 1×':>9}")
    print("-" * 78)

    for r in rows:
        wo = without_skill_cost(r["skill"])
        with_cost = r["body_tokens"] + 200  # body load + small completion
        save_1x = wo - with_cost
        print(
            f"{r['skill']:<20} "
            f"{r['fm_tokens']:>6} "
            f"{r['desc_tokens']:>6} "
            f"{r['body_tokens']:>7} "
            f"{wo:>8} "
            f"{save_1x:>+9}"
        )

    print("-" * 78)
    print(f"{'TOTAL':<20} {total_fm:>6} {total_desc:>6} {total_body:>7}")
    print()
    print(f"Always-loaded base cost (every session, all 15 frontmatters): {total_fm} tokens")
    print(f"Description-only subset: {total_desc} tokens")
    print(f"Sum of all bodies (max if all 15 invoked): {total_body} tokens")
    print()

    # Scenario comparisons
    print("=" * 78)
    print("SCENARIOS — with vs without toolkit")
    print("=" * 78)
    print()

    # Average values
    avg_body = total_body // len(rows)
    avg_wo = sum(without_skill_cost(r["skill"]) for r in rows) // len(rows)
    completion_per_call = 200

    scenarios = [
        ("1 skill × 1 invocation", 1, 1),
        ("3 skills × 4 invocations", 3, 4),
        ("5 skills × 5 invocations", 5, 5),
        ("1 skill × 5 invocations (heavy reuse)", 1, 5),
    ]

    print(f"Avg body per skill: {avg_body} tokens")
    print(f"Avg without-skill task cost: {avg_wo} tokens")
    print(f"Completion overhead per invocation: {completion_per_call} tokens")
    print()
    print(f"{'Scenario':<40} {'Without':>9} {'With':>8} {'Save':>10} {'Save%':>7}")
    print("-" * 78)

    for name, n_skills, invokes in scenarios:
        without = invokes * n_skills * avg_wo
        with_cost = (
            total_fm                          # always-loaded
            + n_skills * avg_body              # bodies loaded once each
            + n_skills * invokes * completion_per_call  # per-call completion
        )
        save = without - with_cost
        pct = round(save * 100 / without) if without else 0
        sign = "+" if save > 0 else ""
        print(
            f"{name:<40} "
            f"{without:>9} "
            f"{with_cost:>8} "
            f"{sign}{save:>+9,} "
            f"{pct:>+5}%"
        )

    print()
    print("Notes:")
    print("- 'Without' = Claude generates from training-data knowledge each task.")
    print("- 'With'    = SKILL.md loaded once per skill per session, then small")
    print("              completions for each invocation.")
    print("- Always-loaded cost is paid even if no toolkit skill is invoked.")
    print("- Methodology: tiktoken cl100k_base ≈ Claude tokenizer (±5% variance).")
    print("- Without-skill baselines are estimates per API complexity & retry rate.")
    print()


if __name__ == "__main__":
    main()
