#!/usr/bin/env python3
"""
Sync Home Assistant addon configs and docs from source repos into this app repository.

Usage:
    python3 sync_addons.py <addon-dir> [<addon-dir> ...]

Each <addon-dir> should be the root of an addon repository (the parent of hassio-apps).
The script finds config.yaml and README.md/DOCS.md in each addon and syncs them
into the corresponding subdirectory of this repository, adapting them for the
new app format.
"""

from __future__ import annotations

import argparse
import os
import sys
import re
import yaml
from pathlib import Path

# Fields valid in the old Supervisor add-on format that should be removed
# for the newer Apps format.
OLD_SUPERVISOR_FIELDS = {
    "startup",
    "boot",
}


def _strip_yaml_front_matter(content: str) -> str:
    """Remove YAML front matter markers (---) from the top of a config file."""
    lines = content.splitlines()
    while lines and lines[0].strip() == "---":
        lines.pop(0)
    while lines and lines[-1].strip() == "---":
        lines.pop()
    return "\n".join(lines)


def _adapt_config(raw_content: str, addon_dir: Path) -> str:
    """
    Adapt a Supervisor-style config.yaml to the new Apps format:
      - Remove Supervisor-only fields
      - Add image field
      - Update url to point to this repo
    Returns the adapted YAML as a string.
    """
    content = _strip_yaml_front_matter(raw_content)
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        return raw_content  # fallback: return original

    addon_name = data.get("slug", "unknown")

    # Remove Supervisor-only fields
    for key in OLD_SUPERVISOR_FIELDS:
        data.pop(key, None)

    # Ensure arch is a list and filter to supported platforms only
    if isinstance(data.get("arch"), str):
        data["arch"] = [data["arch"]]
    if isinstance(data.get("arch"), list):
        data["arch"] = [a for a in data["arch"] if a in ("aarch64", "amd64")]

    # Set slug to match the addon directory name (required for new Apps format)
    data["slug"] = addon_dir.name

    # Set the image field using the addon directory name
    data["image"] = f"docker.io/lebauce/hevea:{addon_dir.name}"

    # Clean up null values in options (Home Assistant treats them as unset)
    if "options" in data and isinstance(data["options"], dict):
        data["options"] = {k: v for k, v in data["options"].items() if v is not None}

    # Update url to point to this repo (using directory name)
    data["url"] = f"https://github.com/hevea-project/hevea-hassio-apps/tree/main/{addon_dir.name}"

    # Normalize schema keys: remove trailing ? from str? etc.
    if "schema" in data and isinstance(data["schema"], dict):
        for key, val in list(data["schema"].items()):
            if isinstance(val, str) and val.endswith("?"):
                # str? means optional — keep as-is for Home Assistant schema syntax
                pass
            elif isinstance(val, str) and val.startswith("match("):
                pass  # keep regex patterns
            elif isinstance(val, str) and val in ("str", "int", "float", "bool", "password"):
                pass  # keep type hints
            elif isinstance(val, list):
                pass  # keep list schemas
            else:
                pass

    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _find_config_file(addon_dir: Path) -> Path | None:
    """
    Find config.yaml in an addon directory.
    The access-point addon nests it one level deep.
    """
    direct = addon_dir / "config.yaml"
    if direct.is_file():
        return direct

    # Check one level deep (e.g. hassio-access-point/hassio-access-point/config.yaml)
    for subdir in addon_dir.iterdir():
        if subdir.is_dir():
            nested = subdir / "config.yaml"
            if nested.is_file():
                return nested

    return None


def _find_docs_file(addon_dir: Path) -> Path | None:
    """Find README.md or DOCS.md in an addon directory (recursive)."""
    for root, dirs, files in os.walk(addon_dir):
        if "DOCS.md" in files:
            return Path(root) / "DOCS.md"
        if "README.md" in files:
            return Path(root) / "README.md"
    return None


def _generate_minimal_docs(name: str, description: str) -> str:
    """Generate a minimal DOCS.md when no documentation exists in the source."""
    return f"# Home Assistant App: {name}\n\n{description}\n"


def sync_addon(addon_dir: Path, repo_root: Path) -> None:
    """Sync a single addon into the app repository."""
    addon_name = addon_dir.name
    addon_out = repo_root / addon_name

    # --- config.yaml ---
    config_src = _find_config_file(addon_dir)
    if config_src is None:
        print(f"  [WARN] No config.yaml found in {addon_dir}")
        return

    config_raw = config_src.read_text(encoding="utf-8")
    config_adapted = _adapt_config(config_raw, addon_dir)
    config_dst = addon_out / "config.yaml"
    config_dst.write_text(config_adapted, encoding="utf-8")
    print(f"  [OK] config.yaml -> {config_dst}")

    # --- DOCS.md ---
    docs_src = _find_docs_file(addon_dir)
    docs_dst = addon_out / "DOCS.md"

    if docs_src is not None:
        docs_content = docs_src.read_text(encoding="utf-8")
        if docs_content.strip():
            docs_dst.write_text(docs_content, encoding="utf-8")
            print(f"  [OK] docs ({docs_src.name}) -> {docs_dst}")
        else:
            # Empty doc file — generate minimal
            name_for_docs = config_adapted.splitlines()[0].replace("name: ", "").strip('"')
            desc_line = ""
            for line in config_adapted.splitlines():
                if line.startswith("description:"):
                    desc_line = line.split(":", 1)[1].strip().strip('"')
                    break
            docs_dst.write_text(_generate_minimal_docs(name_for_docs, desc_line), encoding="utf-8")
            print(f"  [GEN] Generated minimal DOCS.md -> {docs_dst}")
    else:
        # No docs at all — generate minimal
        name_for_docs = config_adapted.splitlines()[0].replace("name: ", "").strip('"')
        desc_line = ""
        for line in config_adapted.splitlines():
            if line.startswith("description:"):
                desc_line = line.split(":", 1)[1].strip().strip('"')
                break
        docs_dst.write_text(_generate_minimal_docs(name_for_docs, desc_line), encoding="utf-8")
        print(f"  [GEN] Generated minimal DOCS.md -> {docs_dst}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync Home Assistant addon configs and docs into the app repository."
    )
    parser.add_argument(
        "addons",
        nargs="+",
        help="Paths to addon directories to sync (or their parent containing the addon subdirs)",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Path to the app repository root (default: directory of this script)",
    )
    args = parser.parse_args()

    # Determine repo root
    if args.repo is not None:
        repo_root = args.repo.resolve()
    else:
        repo_root = Path(__file__).resolve().parent

    if not repo_root.is_dir():
        print(f"Error: repository root not found: {repo_root}", file=sys.stderr)
        sys.exit(1)

    # Resolve addon directories
    addon_paths: list[Path] = []
    for arg in args.addons:
        p = Path(arg).resolve()
        if p.is_dir():
            # If it contains a subdirectory that looks like an addon (has config.yaml),
            # use that subdirectory; otherwise use the directory itself.
            config = _find_config_file(p)
            if config and config.parent != p:
                # The config is nested; the addon dir is the parent
                addon_paths.append(config.parent.parent)
            else:
                addon_paths.append(p)
        else:
            print(f"Error: path not found: {arg}", file=sys.stderr)
            sys.exit(1)

    print(f"Syncing {len(addon_paths)} addon(s) into {repo_root}\n")

    for addon_dir in addon_paths:
        print(f"Syncing: {addon_dir.name}")
        sync_addon(addon_dir, repo_root)
        print()

    print("Done.")


if __name__ == "__main__":
    main()
