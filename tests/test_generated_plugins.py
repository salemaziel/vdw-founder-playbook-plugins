from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_plugins", ROOT / "scripts" / "generate_plugins.py"
)
assert SPEC and SPEC.loader
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)

MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


class GeneratedPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = {
            name: GENERATOR.read_skill_metadata(name) for name in GENERATOR.SKILLS
        }

    def test_generated_output_is_current(self) -> None:
        self.assertEqual(GENERATOR.check_generated(self.metadata), [])

    def test_marketplaces_have_identical_plugin_names(self) -> None:
        claude = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text()
        )
        codex = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
        )
        expected = GENERATOR.SKILLS
        self.assertEqual([plugin["name"] for plugin in claude["plugins"]], expected)
        self.assertEqual([plugin["name"] for plugin in codex["plugins"]], expected)
        self.assertEqual(claude["name"], GENERATOR.MARKETPLACE_NAME)
        self.assertEqual(codex["name"], GENERATOR.MARKETPLACE_NAME)

        for name, claude_entry, codex_entry in zip(
            expected, claude["plugins"], codex["plugins"], strict=True
        ):
            self.assertEqual(claude_entry["source"], f"./plugins/{name}")
            self.assertEqual(
                codex_entry["source"],
                {"source": "local", "path": f"./plugins/{name}"},
            )
            self.assertEqual(
                codex_entry["policy"],
                {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            )
            self.assertEqual(codex_entry["category"], "Business")

    def test_hermes_bundle_has_all_grouped_skills(self) -> None:
        grouping = json.loads((ROOT / "skills.sh.json").read_text())
        self.assertEqual(
            grouping,
            {
                "groupings": [
                    {
                        "title": "VDW Founder Playbook",
                        "skills": GENERATOR.SKILLS,
                    }
                ]
            },
        )
        self.assertEqual(
            {path.name for path in (ROOT / "skills").iterdir() if path.is_dir()},
            set(GENERATOR.SKILLS),
        )
        for name in GENERATOR.SKILLS:
            self.assertEqual(
                GENERATOR.tree_signature(ROOT / name),
                GENERATOR.tree_signature(ROOT / "skills" / name),
            )

    def test_plugin_manifests_match_directory_and_skill_names(self) -> None:
        for name in GENERATOR.SKILLS:
            plugin_root = ROOT / "plugins" / name
            claude = json.loads(
                (plugin_root / ".claude-plugin" / "plugin.json").read_text()
            )
            codex = json.loads(
                (plugin_root / ".codex-plugin" / "plugin.json").read_text()
            )
            skill = GENERATOR.read_skill_metadata(name)

            self.assertEqual(claude["name"], name)
            self.assertEqual(codex["name"], name)
            self.assertEqual(claude["version"], GENERATOR.VERSION)
            self.assertEqual(codex["version"], GENERATOR.VERSION)
            self.assertEqual(claude["description"], skill["description"])
            self.assertEqual(codex["description"], skill["description"])
            self.assertEqual(codex["skills"], "./skills/")
            self.assertEqual(codex["interface"]["category"], "Business")
            self.assertTrue(
                all(
                    len(prompt) <= 128
                    for prompt in codex["interface"]["defaultPrompt"]
                )
            )

    def test_generated_skill_links_resolve(self) -> None:
        for name in GENERATOR.SKILLS:
            skill_root = ROOT / "plugins" / name / "skills" / name
            for markdown in skill_root.rglob("*.md"):
                for target in MARKDOWN_LINK_RE.findall(markdown.read_text()):
                    target = target.strip().split("#", 1)[0]
                    if not target or "://" in target or target.startswith(("#", "mailto:")):
                        continue
                    resolved = (markdown.parent / target).resolve()
                    self.assertTrue(
                        resolved.exists(),
                        f"broken link in {markdown.relative_to(ROOT)}: {target}",
                    )


if __name__ == "__main__":
    unittest.main()
