#!/usr/bin/env python3
"""Generate native plugin and Hermes skill bundles from upstream skill folders."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"
HERMES_SKILLS_DIR = ROOT / "skills"
VERSION = "0.1.0"
REPOSITORY = "https://github.com/salemaziel/vdw-founder-playbook-plugins"
MARKETPLACE_NAME = "vdw-founder-playbook"
PUBLISHER = {
    "name": "Via Del Web",
    "email": "claude@viadelweb.cloud",
}

SKILLS = [
    "diagnose",
    "mom-test",
    "four-steps",
    "lean-startup",
    "obviously-awesome",
    "crossing-the-chasm",
    "blue-ocean-strategy",
    "monetizing-innovation",
    "spin-selling",
    "100m-offers",
    "100m-leads",
    "money-models",
    "influence",
    "traction",
    "storybrand",
    "made-to-stick",
]

DISPLAY_NAMES = {
    "diagnose": "Founder Diagnose",
    "mom-test": "The Mom Test",
    "four-steps": "The Four Steps to the Epiphany",
    "lean-startup": "The Lean Startup",
    "obviously-awesome": "Obviously Awesome",
    "crossing-the-chasm": "Crossing the Chasm",
    "blue-ocean-strategy": "Blue Ocean Strategy",
    "monetizing-innovation": "Monetizing Innovation",
    "spin-selling": "SPIN Selling",
    "100m-offers": "$100M Offers",
    "100m-leads": "$100M Leads",
    "money-models": "$100M Money Models",
    "influence": "Influence",
    "traction": "Traction",
    "storybrand": "Building a StoryBrand",
    "made-to-stick": "Made to Stick",
}

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")


def parse_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return json.loads(value)
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def read_skill_metadata(skill_name: str) -> dict[str, str]:
    skill_md = ROOT / skill_name / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"missing source skill: {skill_md}")
    match = FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"missing YAML frontmatter: {skill_md}")

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        field = FIELD_RE.match(line)
        if field:
            metadata[field.group(1)] = parse_scalar(field.group(2))

    if metadata.get("name") != skill_name:
        raise ValueError(
            f"skill name mismatch in {skill_md}: {metadata.get('name')!r}"
        )
    if not metadata.get("description"):
        raise ValueError(f"missing skill description: {skill_md}")
    return metadata


def short_description(description: str, limit: int = 160) -> str:
    if len(description) <= limit:
        return description
    return description[: limit - 1].rstrip() + "…"


def claude_manifest(name: str, description: str) -> dict[str, object]:
    return {
        "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
        "name": name,
        "displayName": DISPLAY_NAMES[name],
        "version": VERSION,
        "description": description,
        "author": PUBLISHER,
        "homepage": f"{REPOSITORY}/tree/main/plugins/{name}",
        "repository": REPOSITORY,
        "license": "MIT",
        "keywords": ["founder", "business", name],
    }


def codex_manifest(name: str, description: str) -> dict[str, object]:
    display_name = DISPLAY_NAMES[name]
    return {
        "name": name,
        "version": VERSION,
        "description": description,
        "author": {**PUBLISHER, "url": "https://github.com/salemaziel"},
        "homepage": f"{REPOSITORY}/tree/main/plugins/{name}",
        "repository": REPOSITORY,
        "license": "MIT",
        "keywords": ["founder", "business", name],
        "skills": "./skills/",
        "interface": {
            "displayName": display_name,
            "shortDescription": short_description(description),
            "longDescription": description,
            "developerName": "Via Del Web",
            "category": "Business",
            "capabilities": ["Interactive"],
            "defaultPrompt": [
                f"Use {display_name} to help with my startup.",
                f"Apply {display_name} to this business problem.",
            ],
        },
    }


def claude_marketplace(metadata: dict[str, dict[str, str]]) -> dict[str, object]:
    return {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": MARKETPLACE_NAME,
        "description": "Founder playbooks packaged as independent Via Del Web plugins.",
        "owner": PUBLISHER,
        "plugins": [
            {
                "name": name,
                "source": f"./plugins/{name}",
                "description": metadata[name]["description"],
                "version": VERSION,
            }
            for name in SKILLS
        ],
    }


def codex_marketplace(metadata: dict[str, dict[str, str]]) -> dict[str, object]:
    return {
        "name": MARKETPLACE_NAME,
        "interface": {"displayName": "VDW Founder Playbook"},
        "plugins": [
            {
                "name": name,
                "source": {
                    "source": "local",
                    "path": f"./plugins/{name}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Business",
            }
            for name in SKILLS
        ],
    }


def hermes_groupings() -> dict[str, object]:
    return {
        "groupings": [
            {
                "title": "VDW Founder Playbook",
                "skills": SKILLS,
            }
        ]
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def expected_payloads(
    metadata: dict[str, dict[str, str]],
) -> dict[Path, dict[str, object]]:
    payloads: dict[Path, dict[str, object]] = {
        ROOT / ".claude-plugin" / "marketplace.json": claude_marketplace(metadata),
        ROOT / ".agents" / "plugins" / "marketplace.json": codex_marketplace(metadata),
        ROOT / "skills.sh.json": hermes_groupings(),
    }
    for name in SKILLS:
        description = metadata[name]["description"]
        plugin_root = PLUGINS_DIR / name
        payloads[plugin_root / ".claude-plugin" / "plugin.json"] = claude_manifest(
            name, description
        )
        payloads[plugin_root / ".codex-plugin" / "plugin.json"] = codex_manifest(
            name, description
        )
    return payloads


def tree_signature(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def check_generated(metadata: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []
    expected_names = set(SKILLS)
    actual_names = (
        {path.name for path in PLUGINS_DIR.iterdir() if path.is_dir()}
        if PLUGINS_DIR.is_dir()
        else set()
    )
    if actual_names != expected_names:
        errors.append(
            "plugin directory set differs: "
            f"expected={sorted(expected_names)} actual={sorted(actual_names)}"
        )

    actual_hermes_names = (
        {path.name for path in HERMES_SKILLS_DIR.iterdir() if path.is_dir()}
        if HERMES_SKILLS_DIR.is_dir()
        else set()
    )
    if actual_hermes_names != expected_names:
        errors.append(
            "Hermes skill directory set differs: "
            f"expected={sorted(expected_names)} actual={sorted(actual_hermes_names)}"
        )

    for path, expected in expected_payloads(metadata).items():
        if not path.is_file():
            errors.append(f"missing generated JSON: {path.relative_to(ROOT)}")
            continue
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f"invalid JSON in {path.relative_to(ROOT)}: {error}")
            continue
        if actual != expected:
            errors.append(f"generated JSON drift: {path.relative_to(ROOT)}")

    for name in SKILLS:
        source = ROOT / name
        generated_plugin = PLUGINS_DIR / name / "skills" / name
        generated_hermes = HERMES_SKILLS_DIR / name
        if tree_signature(source) != tree_signature(generated_plugin):
            errors.append(f"generated skill drift: plugins/{name}/skills/{name}")
        if tree_signature(source) != tree_signature(generated_hermes):
            errors.append(f"generated Hermes skill drift: skills/{name}")
    return errors


def generate(metadata: dict[str, dict[str, str]]) -> None:
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    HERMES_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for name in SKILLS:
        source = ROOT / name
        plugin_root = PLUGINS_DIR / name
        generated_targets = [
            plugin_root / "skills" / name,
            HERMES_SKILLS_DIR / name,
        ]
        for generated_skill in generated_targets:
            if generated_skill.exists():
                shutil.rmtree(generated_skill)
            generated_skill.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, generated_skill)

    for path, payload in expected_payloads(metadata).items():
        write_json(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when committed plugin output differs from the source skills",
    )
    args = parser.parse_args()

    try:
        metadata = {name: read_skill_metadata(name) for name in SKILLS}
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.check:
        errors = check_generated(metadata)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(
            "Generated plugin and Hermes skill trees are current "
            f"({len(SKILLS)} skills)."
        )
        return 0

    generate(metadata)
    print(
        f"Generated {len(SKILLS)} Claude Code/Codex CLI plugins "
        "and Hermes Agent skills."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
