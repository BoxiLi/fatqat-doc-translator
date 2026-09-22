"""Translate navigation and gallery strings from the pinned upstream config."""

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def upstream_config():
    return yaml.safe_load((ROOT / "upstream.yml").read_text(encoding="utf-8"))


def read_config(path):
    # Only read nav here: upstream's other YAML values include Python/!ENV tags.
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def nav_strings(nav):
    for item in nav:
        if isinstance(item, dict):
            for label, target in item.items():
                yield label
                if isinstance(target, list):
                    yield from nav_strings(target)


def gallery_strings(gallery):
    for section in ("ui", "index"):
        yield from gallery[section]["en"].values()
    for category in gallery["categories"].values():
        yield from category["en"].values()


def source_strings(root):
    config = root / "mkdocs.yml"
    if not config.exists():
        return []
    gallery = yaml.safe_load(
        (root / "tutorial-sources/gallery.yml").read_text(encoding="utf-8")
    )
    return list(
        dict.fromkeys(
            [*nav_strings(read_config(config)["nav"]), *gallery_strings(gallery)]
        )
    )


def translate_nav(nav, lookup):
    result = []
    for item in nav:
        if isinstance(item, dict):
            result.append(
                {
                    lookup(label): (
                        translate_nav(target, lookup)
                        if isinstance(target, list)
                        else target
                    )
                    for label, target in item.items()
                }
            )
        else:
            result.append(item)
    return result


def translate_gallery(gallery, lookup):
    result = {
        key: {"zh": {k: lookup(v) for k, v in gallery[key]["en"].items()}}
        for key in ("ui", "index")
    }
    result["categories"] = {
        key: {"zh": {k: lookup(v) for k, v in value["en"].items()}}
        for key, value in gallery["categories"].items()
    }
    return result
