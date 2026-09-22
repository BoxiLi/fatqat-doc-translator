import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import markdown
from pymdownx.slugs import slugify

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import translate
from site_config import translate_nav, translate_gallery, upstream_config
from inject_build import generate_config
import inject_build
from list_versions import release_versions


class TranslationTests(unittest.TestCase):
    def source(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "page.md"
        path.write_text(text, encoding="utf-8")
        return translate.parse_source(path, Path("guide/page.md"))

    def test_translated_headings_preserve_english_links_and_duplicate_ids(self):
        source = self.source(
            "# Overview\n\n## Draw `counts`\n\n## Draw `counts`\n\n[Result](#draw-counts)\n"
        )
        entries = {
            translate.segment_id(text): translate.Entry(
                translate.segment_id(text), text, zh, "machine"
            )
            for text, zh in [("Overview", "概述"), ("Draw `counts`", "绘制 `counts`")]
        }
        result, _ = translate.render_page(source, entries)
        html = markdown.markdown(
            result,
            extensions=["toc", "attr_list"],
            extension_configs={"toc": {"slugify": slugify(case="lower")}},
        )
        self.assertIn('id="draw-counts"', html)
        self.assertIn('id="draw-counts_1"', html)
        self.assertIn('href="#draw-counts"', html)
        self.assertIn("绘制", html)

    def test_code_and_explicit_anchor_are_preserved(self):
        text = "## Run { #run-example }\n\n```python\nprint('English')\n```\n"
        source = self.source(text)
        key = translate.segment_id("Run")
        result, _ = translate.render_page(
            source, {key: translate.Entry(key, "Run", "运行", "machine")}
        )
        self.assertIn("{ #run-example }", result)
        self.assertIn("```python\nprint('English')\n```", result)
        self.assertEqual(translate.render_page(source, {})[0], text)

    def test_navigation_follows_upstream_paths_and_structure(self):
        nav = [{"Guide": [{"Compiler": "guide/compiler.md"}, "guide/index.md"]}]
        self.assertEqual(
            translate_nav(nav, lambda x: {"Guide": "指南", "Compiler": "编译器"}[x]),
            [{"指南": [{"编译器": "guide/compiler.md"}, "guide/index.md"]}],
        )

    def test_new_gallery_categories_are_included(self):
        gallery = {
            "ui": {"en": {"open": "Open"}},
            "index": {"en": {"title": "Tutorials"}},
            "categories": {"new": {"en": {"title": "New"}}},
        }
        self.assertEqual(
            translate_gallery(gallery, lambda text: "zh:" + text)["categories"]["new"][
                "zh"
            ]["title"],
            "zh:New",
        )

    def test_canonical_url_has_no_extra_language_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "overlay").mkdir()
            (root / "overlay/mkdocs.zh.yml").write_text(
                "INHERIT: mkdocs.yml\n", encoding="utf-8"
            )
            (root / "UPSTREAM_REF").write_text("v1.2.3\n", encoding="utf-8")
            clone = root / "clone"
            (clone / "docs/mkdocs/tutorial-sources").mkdir(parents=True)
            (clone / "mkdocs.yml").write_text(
                "nav:\n  - Home: index.md\n", encoding="utf-8"
            )
            (clone / "docs/mkdocs/tutorial-sources/gallery.yml").write_text(
                "ui: {en: {open: Open}}\nindex: {en: {title: Tutorials}}\ncategories: {}\n",
                encoding="utf-8",
            )
            with patch.object(inject_build, "ROOT", root), patch.object(
                inject_build,
                "upstream_config",
                return_value={
                    "ref": "main",
                    "english_site": "https://fatqat.readthedocs.io/en/",
                },
            ), patch.object(translate, "load_database", return_value={}):
                generate_config(clone, "https://fatqat.readthedocs.io/zh_CN/v1.2.3/")
            import yaml

            config = yaml.safe_load(
                (clone / "mkdocs.zh.yml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                config["site_url"], "https://fatqat.readthedocs.io/zh_CN/v1.2.3/"
            )
            self.assertEqual(
                config["extra"]["alternate"][0]["link"],
                "https://fatqat.readthedocs.io/en/v1.2.3/",
            )

    def test_release_listing_ignores_nonversions_and_peeled_tag_duplicates(self):
        listing = (
            "abc refs/tags/v1.2.3\ndef refs/tags/v1.2.3^{}\nxyz refs/tags/scratch\n"
        )
        self.assertEqual(
            release_versions(listing, upstream_config()["release_pattern"]), ["v1.2.3"]
        )

    def test_complete_check_rejects_pending(self):
        pending = translate.Entry("id", "text", "", "pending")
        with patch.object(translate, "discover_sources", return_value=[]), patch.object(
            translate, "load_database", return_value={}
        ):
            self.assertEqual(translate.run_check(require_complete=True), 0)
        key = translate.segment_id("text")
        pending.id = key
        with patch.object(translate, "discover_sources", return_value=[]), patch.object(
            translate, "load_database", return_value={Path("fake.yml"): [pending]}
        ):
            self.assertEqual(translate.run_check(require_complete=True), 1)

    def test_reactivated_translation_is_not_marked_human_reviewed(self):
        source = self.source("# Overview\n")
        entry = translate.Entry(
            translate.segment_id("Overview"), "Overview", "概述", "retired"
        )
        with patch.object(
            translate, "discover_sources", return_value=[source]
        ), patch.object(
            translate, "load_database", return_value={Path("fake.yml"): [entry]}
        ), patch.object(
            translate, "save_database_file"
        ):
            translate.run_extract(dry_run=False)
        self.assertEqual(entry.status, "machine")


if __name__ == "__main__":
    unittest.main()
