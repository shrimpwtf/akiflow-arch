#!/usr/bin/env python3
"""
Patch Akiflow's app.asar for Linux integration.

Patches applied:
  1. (main process) Write tray title to ~/.cache/akiflow/tray-status.json
  2. (main process) Watch ~/.cache/akiflow/toggle-tray to toggle tray window
  3. (renderer) Remove IS_MAC gate so tray title updates fire on Linux too

Usage:
    python3 patch-main.py [--dry-run]
"""

import struct
import json
import hashlib
import shutil
import sys
import os
import re
from pathlib import Path

if (Path.cwd() / "app.asar").exists():
    ASAR_PATH = Path.cwd() / "app.asar"
else:
    ASAR_PATH = Path(__file__).parent / "src" / "app" / "resources" / "app.asar"
BACKUP_PATH = ASAR_PATH.with_suffix(".asar.bak")


# ── Patches for publish/main.js ──────────────────────────────────────────
#
# Patterns use regex with capture groups so minified variable names (which
# change each release) don't cause patch failures.

def _tray_writer_repl(m):
    e_var, t_var, x_var = m.group(1), m.group(2), m.group(3)
    return (
        f'ipcMain.handle("tray.setTitle",(({e_var},{t_var})=>{{{x_var}.title={t_var},'
        f'{x_var}.updateTitleAndIcon({x_var}.title);'
        'try{const _d=require("path").join(require("os").homedir(),".cache","akiflow");'
        'require("fs").mkdirSync(_d,{recursive:!0});'
        f'require("fs").writeFileSync(require("path").join(_d,"tray-status.json"),'
        f'JSON.stringify({{title:{t_var}||"",hasEvent:!!{t_var},timestamp:Date.now()}}))'
        '}catch(_e){}}))'
    )


MAIN_PATCHES = [
    {
        "name": "Tray status JSON writer",
        "pattern": r'ipcMain\.handle\("tray\.setTitle",\(\((\w+),(\w+)\)=>\{(\w+)\.title=\2,\3\.updateTitleAndIcon\(\3\.title\)\}\)\)',
        "replacement": _tray_writer_repl,
        "check_applied": "tray-status.json",
        "required": True,
    },
    {
        "name": "Tray window toggle watcher",
        # Uses process.platform instead of a minified IS_LINUX variable.
        # Uses require('electron').screen instead of a minified electron var.
        "original": 'globalThis.tray.setToolTip("Akiflow")',
        "replacement": (
            'globalThis.tray.setToolTip("Akiflow"),'
            "(()=>{if(process.platform===\"linux\"){const _fs=require(\"fs\"),_tp=require(\"path\").join(require(\"os\").homedir(),"
            '".cache","akiflow","toggle-tray");'
            "try{_fs.mkdirSync(require(\"path\").dirname(_tp),{recursive:!0})}catch(_e){}"
            "_fs.watchFile(_tp,{interval:500},()=>{"
            "try{if(!globalThis.trayWindow||globalThis.trayWindow.isDestroyed())return;"
            "if(globalThis.trayWindow.isVisible()){globalThis.trayWindow._hide(\"fromWidget\");return}"
            "let _pos;try{_pos=JSON.parse(_fs.readFileSync(_tp,\"utf8\"))}catch(_e){}"
            "if(_pos&&_pos.x!=null&&_pos.y!=null){"
            "const _b=globalThis.trayWindow.getBounds(),"
            "_d=require(\"electron\").screen.getDisplayNearestPoint({x:_pos.x,y:_pos.y}),"
            "_nx=Math.max(_d.workArea.x,Math.min(_pos.x-Math.floor(_b.width/2),_d.workArea.x+_d.workArea.width-_b.width)),"
            "_ny=_pos.y-_b.height-8;"
            "globalThis.trayWindow.setBounds({x:_nx,y:_ny<_d.workArea.y?_pos.y+8:_ny,width:_b.width,height:_b.height})}"
            'globalThis.trayWindow._show("fromWidget")'
            "}catch(_e){}})}})()"
        ),
        "required": False,
    },
]


# ── Patches for publish/renderer/main.js ─────────────────────────────────

RENDERER_PATCHES = [
    {
        "name": "Remove IS_MAC gate on tray title init",
        # Matches: X.IS_MAC&&!X.IS_WEB&&(Y.store.sub(Z.atoms.trayTile,...))
        "pattern": r'(\w+)\.IS_MAC&&!\1\.IS_WEB&&(\(\w+\.store\.sub\(\w+\.atoms\.trayTile,\w+\.setTitle\),setTimeout\(\w+\.setTitle,1e3\)\))',
        "replacement": r'(\1.IS_MAC||\1.IS_LINUX)&&!\1.IS_WEB&&\2',
        "check_applied": "IS_LINUX)&&!",
        "required": True,
    },
    {
        "name": "Remove IS_MAC gate on trayTile atom",
        # Matches: trayTile=FUNC((e=>{if(!X.IS_MAC||X.IS_WEB)return null
        "pattern": r'(trayTile=\w+\(\(e=>\{if\()!(\w+)\.IS_MAC\|\|\2\.IS_WEB(\)return null)',
        "replacement": r'\1!(\2.IS_MAC||\2.IS_LINUX)||\2.IS_WEB\3',
        "check_applied": "IS_LINUX)||",
        "required": True,
    },
    {
        "name": "Increase tray title truncation from 15 to 30 chars",
        "original": 't=e.length>15?e.slice(0,15).join("")+"...":e.join("")',
        "replacement": 't=e.length>30?e.slice(0,30).join("")+"...":e.join("")',
        "required": False,
    },
]


# ── Asar helpers ──────────────────────────────────────────────────────────

def read_asar_header(f):
    raw = f.read(16)
    if len(raw) < 16:
        raise ValueError("File too small to be a valid asar archive")
    pickle_size, header_size, pickle_str_size, json_size = struct.unpack("<IIII", raw)
    header_json = f.read(json_size).decode("utf-8")
    header = json.loads(header_json)
    data_offset = 8 + header_size
    return header, data_offset, json_size


def collect_packed_files(node, path_parts=None):
    if path_parts is None:
        path_parts = []
    results = []
    if "files" in node:
        for name, entry in node["files"].items():
            child_path = path_parts + [name]
            if "files" in entry:
                results.extend(collect_packed_files(entry, child_path))
            elif not entry.get("unpacked", False):
                results.append((tuple(child_path), entry))
    results.sort(key=lambda x: int(x[1]["offset"]))
    return results


def set_entry(header, path_parts, new_entry):
    node = header
    for part in path_parts[:-1]:
        node = node["files"][part]
    node["files"][path_parts[-1]] = new_entry


def compute_integrity(data):
    sha = hashlib.sha256(data).hexdigest()
    block_size = 4 * 1024 * 1024
    blocks = []
    for i in range(0, max(len(data), 1), block_size):
        chunk = data[i : i + block_size]
        if chunk:
            blocks.append(hashlib.sha256(chunk).hexdigest())
    if not blocks:
        blocks.append(sha)
    return {"algorithm": "SHA256", "hash": sha, "blockSize": block_size, "blocks": blocks}


def build_asar(header_dict):
    header_json = json.dumps(header_dict, separators=(",", ":"), ensure_ascii=False)
    json_bytes = header_json.encode("utf-8")
    json_size = len(json_bytes)
    pickle_size = 4
    header_size = 4 + 4 + json_size
    preamble = struct.pack("<IIII", pickle_size, header_size, 4 + json_size, json_size)
    data_offset = 8 + header_size
    return preamble + json_bytes, data_offset


def read_file_from_asar(f, data_offset, entry):
    f.seek(data_offset + int(entry["offset"]))
    return f.read(entry["size"])


def find_entry(packed_files, path_tuple):
    for pp, entry in packed_files:
        if pp == path_tuple:
            return entry
    return None


def apply_patches(text, patches, file_label):
    patched = text
    applied = 0
    for i, p in enumerate(patches, 1):
        name = p["name"]
        required = p["required"]
        is_regex = "pattern" in p

        if is_regex:
            pattern = p["pattern"]
            replacement = p["replacement"]
            check = p.get("check_applied", "")

            if check and check in patched:
                print(f"  [{file_label} patch {i}] {name}: already applied")
                continue

            m = re.search(pattern, patched)
            if m is None:
                if required:
                    print(f"ERROR: Could not find target for '{name}' in {file_label}")
                    print(f"  Pattern: {pattern[:100]}")
                    sys.exit(1)
                else:
                    print(f"  [{file_label} patch {i}] {name}: target not found (optional, skipping)")
                    continue

            new_text = re.sub(pattern, replacement, patched, count=1)
            if new_text == patched:
                print(f"  [{file_label} patch {i}] {name}: no change after substitution (unexpected)")
            else:
                patched = new_text
                applied += 1
                print(f"  [{file_label} patch {i}] {name}: APPLIED")
        else:
            orig = p["original"]
            repl = p["replacement"]
            if repl in patched:
                print(f"  [{file_label} patch {i}] {name}: already applied")
            elif orig in patched:
                patched = patched.replace(orig, repl, 1)
                applied += 1
                print(f"  [{file_label} patch {i}] {name}: APPLIED")
            elif required:
                print(f"ERROR: Could not find target for '{name}' in {file_label}")
                print(f"  Expected: {orig[:80]}...")
                sys.exit(1)
            else:
                print(f"  [{file_label} patch {i}] {name}: target not found (optional, skipping)")

    return patched, applied


def patch():
    dry_run = "--dry-run" in sys.argv

    if not ASAR_PATH.exists():
        print(f"ERROR: asar not found at {ASAR_PATH}")
        sys.exit(1)

    print(f"Reading {ASAR_PATH} ...")
    with open(ASAR_PATH, "rb") as f:
        header, orig_data_offset, _ = read_asar_header(f)
        packed_files = collect_packed_files(header)
        print(f"  Found {len(packed_files)} packed files")

        main_path = ("publish", "main.js")
        renderer_path = ("publish", "renderer", "main.js")

        main_entry = find_entry(packed_files, main_path)
        renderer_entry = find_entry(packed_files, renderer_path)

        if not main_entry:
            print("ERROR: publish/main.js not found"); sys.exit(1)
        if not renderer_entry:
            print("ERROR: publish/renderer/main.js not found"); sys.exit(1)

        main_content = read_file_from_asar(f, orig_data_offset, main_entry)
        renderer_content = read_file_from_asar(f, orig_data_offset, renderer_entry)

    main_text = main_content.decode("utf-8")
    renderer_text = renderer_content.decode("utf-8")

    main_patched, main_count = apply_patches(main_text, MAIN_PATCHES, "main")
    renderer_patched, renderer_count = apply_patches(renderer_text, RENDERER_PATCHES, "renderer")

    total_applied = main_count + renderer_count
    if total_applied == 0:
        print("All patches already applied! Nothing to do.")
        sys.exit(0)

    main_bytes = main_patched.encode("utf-8")
    renderer_bytes = renderer_patched.encode("utf-8")

    patched_files = {}
    if main_count > 0:
        patched_files[main_path] = main_bytes
        print(f"  main.js: {main_entry['size']} -> {len(main_bytes)} bytes")
    if renderer_count > 0:
        patched_files[renderer_path] = renderer_bytes
        print(f"  renderer/main.js: {renderer_entry['size']} -> {len(renderer_bytes)} bytes")

    if dry_run:
        print(f"\n[DRY RUN] {total_applied} patches would be applied. No files modified.")
        sys.exit(0)

    print("Rebuilding asar ...")

    orig_map = {}
    for pp, entry in packed_files:
        orig_map[pp] = (orig_data_offset + int(entry["offset"]), entry["size"])

    with open(ASAR_PATH, "rb") as f:
        header, _, _ = read_asar_header(f)
    packed_files = collect_packed_files(header)

    new_offset = 0
    file_order = []
    for pp, entry in packed_files:
        if pp in patched_files:
            new_content = patched_files[pp]
            new_entry = {
                "size": len(new_content),
                "integrity": compute_integrity(new_content),
                "offset": str(new_offset),
            }
            set_entry(header, list(pp), new_entry)
            file_order.append((pp, True))
            new_offset += len(new_content)
        else:
            entry["offset"] = str(new_offset)
            file_order.append((pp, False))
            new_offset += entry["size"]

    header_bytes, new_data_offset = build_asar(header)

    if not BACKUP_PATH.exists():
        print(f"  Backing up to {BACKUP_PATH}")
        shutil.copy2(ASAR_PATH, BACKUP_PATH)

    tmp_path = ASAR_PATH.with_suffix(".asar.tmp")
    with open(ASAR_PATH, "rb") as src, open(tmp_path, "wb") as dst:
        dst.write(header_bytes)
        for pp, is_patched in file_order:
            if is_patched:
                dst.write(patched_files[pp])
            else:
                abs_offset, size = orig_map[pp]
                src.seek(abs_offset)
                remaining = size
                while remaining > 0:
                    chunk = src.read(min(remaining, 8 * 1024 * 1024))
                    if not chunk:
                        break
                    dst.write(chunk)
                    remaining -= len(chunk)

    tmp_size = os.path.getsize(tmp_path)
    orig_size = os.path.getsize(ASAR_PATH)
    size_diff = sum(len(v) - orig_map[k][1] for k, v in patched_files.items())
    expected_size = orig_size + (len(header_bytes) - orig_data_offset) + size_diff

    print(f"  Original: {orig_size}, New: {tmp_size}, Expected: {expected_size}")
    if tmp_size != expected_size:
        print("ERROR: Size mismatch!")
        sys.exit(1)

    os.replace(tmp_path, ASAR_PATH)
    print(f"\nDone! {total_applied} patches applied to {ASAR_PATH}")
    if BACKUP_PATH.exists():
        print(f"Backup at {BACKUP_PATH}")


if __name__ == "__main__":
    patch()
