#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from urllib.parse import quote

# --- Config defaults ---
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/Rockywell/Images/main/Isaac"
DEFAULT_OUT = "isaac_images.json"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}  # set to {".png"} if you want only PNG

NUM_PREFIX = re.compile(r"^\d+_?")  # strips "3_" in "3_Bosses" → "Bosses"


def clean_segment(name: str) -> str:
    """Remove leading number + optional underscore from a folder name."""
    return NUM_PREFIX.sub("", name)


def url_join(base: str, segments):
    """Join URL with percent-encoding on each path segment."""
    encoded = [quote(str(seg), safe="") for seg in segments if str(seg)]
    if not encoded:
        return base.rstrip("/")
    return base.rstrip("/") + "/" + "/".join(encoded)


def build_tree(fs_path: str, logical_segments, base_url: str):
    """
    Recursively walk fs_path, creating a nested dict:
    - Directories become nested objects (numbers stripped from their names).
    - Files (images) become "Display Name": "URL".
    logical_segments: list of already-cleaned folder names to use in the URL.
    """
    out = {}
    try:
        with os.scandir(fs_path) as it:
            entries = sorted(list(it), key=lambda e: (not e.is_dir(), e.name.lower()))
    except FileNotFoundError:
        print(f"ERROR: folder not found: {fs_path}", file=sys.stderr)
        return out

    for entry in entries:
        name = entry.name
        if name.startswith("."):
            continue  # skip hidden files/folders like .DS_Store and ._*

        if entry.is_dir():
            cleaned = clean_segment(name)
            sub = build_tree(
                os.path.join(fs_path, name),
                logical_segments + [cleaned],
                base_url,
            )
            if sub:  # only include non-empty folders
                out[cleaned] = sub
        elif entry.is_file():
            ext = os.path.splitext(name)[1].lower()
            if ext in IMAGE_EXTS:
                display_key = os.path.splitext(name)[0]  # filename w/o extension
                # URL uses cleaned folder segments + original filename (encoded)
                url = url_join(base_url, logical_segments + [name])
                out[display_key] = url
    return out


def choose_folder_interactive():
    """Try a folder picker; fall back to input() if Tk isn't available."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        path = filedialog.askdirectory(title="Select Isaac images root folder")
        root.destroy()
        return path or ""
    except Exception:
        try:
            return input("Enter the root folder path: ").strip()
        except EOFError:
            return ""


def main():
    p = argparse.ArgumentParser(
        description="Recursively build JSON mapping of Isaac images with number-stripped folder names and GitHub raw URLs."
    )
    p.add_argument(
        "-r", "--root",
        help="Root folder to scan. If omitted, a folder picker/input prompt will be used."
    )
    p.add_argument(
        "-b", "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL prefix (default: {DEFAULT_BASE_URL})"
    )
    p.add_argument(
        "-o", "--output",
        default=DEFAULT_OUT,
        help=f"Output JSON file path (default: {DEFAULT_OUT})"
    )
    p.add_argument(
        "--only-png",
        action="store_true",
        help="Limit to .png files only."
    )
    args = p.parse_args()

    if args.only_png:
        global IMAGE_EXTS
        IMAGE_EXTS = {".png"}

    root_path = args.root or choose_folder_interactive()
    if not root_path:
        print("No root folder provided.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(root_path):
        print(f"Not a directory: {root_path}", file=sys.stderr)
        sys.exit(1)

    # Build top-level by listing immediate children of root
    top = {}
    with os.scandir(root_path) as it:
        entries = sorted(list(it), key=lambda e: (not e.is_dir(), e.name.lower()))
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            cleaned = clean_segment(entry.name)
            subtree = build_tree(
                os.path.join(root_path, entry.name),
                [cleaned],                     # logical path starts at cleaned top folder
                args.base_url,
            )
            if subtree:
                top[cleaned] = subtree
        elif entry.is_file():
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in IMAGE_EXTS:
                display_key = os.path.splitext(entry.name)[0]
                url = url_join(args.base_url, [entry.name])  # top-level file under base
                top[display_key] = url

    # Write JSON with stable ordering, UTF-8, and no ASCII-escaping
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(top, f, ensure_ascii=False, indent=2)

    print(f"Wrote JSON to: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
