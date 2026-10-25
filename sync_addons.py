#!/usr/bin/env python3
"""
Sync Home Assistant addon configs and docs from source repos into this app repository.

Usage:
    python3 sync_addons.py <addon-dir> [<addon-dir> ...]
    python3 sync_addons.py <addon-dir>:<target-name> [<addon-dir>:<target-name> ...]

Each <addon-dir> should be the root of an addon repository (the parent of hassio-apps).
The script finds config.yaml and README.md/DOCS.md in each addon and syncs them
into the corresponding subdirectory of this repository, adapting them for the
new app format.

Use the <addon-dir>:<target-name> syntax to sync into a directory whose name
differs from the source directory (e.g. ../docker/gateway:hassio-gateway
syncs the gateway addon from the hevea mono-repo into hassio-gateway/).

The image field in the synced config.yaml is set from --image-template, where
'{addon}' is replaced with the target directory name. By default images are
published to GHCR as ghcr.io/hevea-project/<addon>.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import re
import yaml
from pathlib import Path

# Fields valid in the old Supervisor add-on format that should be removed
# for the newer Apps format.
OLD_SUPERVISOR_FIELDS = set()

# Default template for the image field in synced configs. '{addon}' is replaced
# with the addon directory name; other placeholders such as '{arch}' are passed
# through unchanged for Home Assistant to resolve per architecture.
DEFAULT_IMAGE_TEMPLATE = "ghcr.io/hevea-project/{addon}"

# Mapping of add-on slugs used in the hevea mono-repo to the directory names
# used in this apps repository. Applied to option values that reference other
# add-ons (app_name, openvpn_app_name, ap_app_name).
ADDON_SLUG_MAP = {
    "hevea_hassio_gateway": "hassio-gateway",
    "hevea_hassio_openvpn": "hassio-openvpn",
    "hevea-hassio-access-point": "hassio-access-point",
    "hevea_hassio_access_point": "hassio-access-point",
}


def _get_latest_git_tag(repo_path: Path) -> str | None:
    """Get the latest semver git tag (X.Y.Z) from a repository.

    Returns None if the path is not a git repo or has no semver tags.
    """
    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-version:refname"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        for tag in result.stdout.strip().splitlines():
            tag = tag.strip()
            # Match semver: X.Y.Z (no 'v' prefix, no suffixes)
            if re.match(r"^\d+\.\d+\.\d+$", tag):
                return tag
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def _strip_yaml_front_matter(content: str) -> str:
    """Remove YAML front matter markers (---) from the top of a config file."""
    lines = content.splitlines()
    while lines and lines[0].strip() == "---":
        lines.pop(0)
    while lines and lines[-1].strip() == "---":
        lines.pop()
    return "\n".join(lines)


def _adapt_config(raw_content: str, addon_dir: Path, target_name: str | None = None,
                  image_template: str = DEFAULT_IMAGE_TEMPLATE,
                  git_version: str | None = None) -> str:
    """
    Adapt a Supervisor-style config.yaml to the new Apps format:
      - Remove Supervisor-only fields
      - Set image from image_template
      - Update url to point to this repo
      - Set slug to target_name (defaults to addon directory name)
      - Set version from git_version if provided (overrides source config)
    Returns the adapted YAML as a string.
    """
    content = _strip_yaml_front_matter(raw_content)
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        return raw_content  # fallback: return original

    # Use target name if provided, otherwise the source directory name.
    # The target name is used for slug, url, and app_name (things that must
    # match the directory in this apps repo). The source directory name is
    # used for the image template, since images are named after the service
    # (e.g. ghcr.io/hevea-project/gateway, not ghcr.io/hevea-project/hassio-gateway).
    addon_name = target_name or addon_dir.name
    image_name = addon_dir.name

    # Remove Supervisor-only fields
    for key in OLD_SUPERVISOR_FIELDS:
        data.pop(key, None)

    # Override version with git tag if available (the tag is the source of truth)
    if git_version:
        data["version"] = git_version

    # Ensure arch is a list and filter to supported platforms only
    if isinstance(data.get("arch"), str):
        data["arch"] = [data["arch"]]
    if isinstance(data.get("arch"), list):
        data["arch"] = [a for a in data["arch"] if a in ("aarch64", "amd64")]

    # Set slug to match the target directory name (required for new Apps format)
    data["slug"] = addon_name

    # Set the image field from the template, substituting the source directory
    # name (the image is named after the service, not the apps-repo directory)
    data["image"] = image_template.replace("{addon}", image_name)

    # Clean up null values in options (Home Assistant treats them as unset)
    if "options" in data and isinstance(data["options"], dict):
        data["options"] = {k: v for k, v in data["options"].items() if v is not None}
        # Update add-on slug references in options to match this repository's
        # directory names. The gateway uses app_name as its own add-on slug
        # to read/write options via the Supervisor API; openvpn_app_name and
        # ap_app_name reference the sibling add-ons.
        # Remap explicitly set slugs to this repository's directory names.
        # Empty values are kept as-is: the gateway discovers the add-on
        # slugs on the Supervisor when they are not set.
        for opt_key in ("app_name", "openvpn_app_name", "ap_app_name"):
            if opt_key in data["options"] and isinstance(data["options"][opt_key], str):
                data["options"][opt_key] = ADDON_SLUG_MAP.get(
                    data["options"][opt_key], data["options"][opt_key]
                )

    # Update url to point to this repo (using target directory name)
    data["url"] = f"https://github.com/hevea-project/hassio-apps/tree/master/{addon_name}"

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


def sync_addon(addon_dir: Path, repo_root: Path, target_name: str | None = None,
               image_template: str = DEFAULT_IMAGE_TEMPLATE) -> None:
    """Sync a single addon into the app repository."""
    addon_name = target_name or addon_dir.name
    addon_out = repo_root / addon_name
    addon_out.mkdir(parents=True, exist_ok=True)

    # --- config.yaml ---
    config_src = _find_config_file(addon_dir)
    if config_src is None:
        print(f"  [WARN] No config.yaml found in {addon_dir}")
        return

    # Get the latest git tag from the source repo (tag = version, source of truth)
    git_version = _get_latest_git_tag(addon_dir)
    if git_version:
        print(f"  [INFO] Latest git tag: {git_version}")

    config_raw = config_src.read_text(encoding="utf-8")
    config_adapted = _adapt_config(config_raw, addon_dir, target_name, image_template, git_version)
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
        help="Paths to addon directories to sync. Use 'path:target-name' to sync "
        "into a directory whose name differs from the source (e.g. "
        "'../docker/gateway:hassio-gateway').",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Path to the app repository root (default: directory of this script)",
    )
    parser.add_argument(
        "--image-template",
        default=DEFAULT_IMAGE_TEMPLATE,
        help="Image name template for synced configs; '{addon}' is replaced with the "
        "source directory name (not the target name), other placeholders (e.g. "
        "'{arch}') are kept as-is (default: %(default)s)",
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

    # Resolve addon directories (support 'path:target-name' syntax)
    addon_specs: list[tuple[Path, str | None]] = []
    for arg in args.addons:
        target_name: str | None = None
        path_str = arg
        if ":" in arg:
            path_str, target_name = arg.rsplit(":", 1)
        p = Path(path_str).resolve()
        if p.is_dir():
            # If it contains a subdirectory that looks like an addon (has config.yaml),
            # use that subdirectory; otherwise use the directory itself.
            config = _find_config_file(p)
            if config and config.parent != p:
                # The config is nested; the addon dir is the parent
                addon_specs.append((config.parent.parent, target_name))
            else:
                addon_specs.append((p, target_name))
        else:
            print(f"Error: path not found: {path_str}", file=sys.stderr)
            sys.exit(1)

    print(f"Syncing {len(addon_specs)} addon(s) into {repo_root}\n")

    for addon_dir, target_name in addon_specs:
        display_name = target_name or addon_dir.name
        print(f"Syncing: {addon_dir.name} -> {display_name}")
        sync_addon(addon_dir, repo_root, target_name, args.image_template)
        print()

    print("Done.")


if __name__ == "__main__":
    main()
