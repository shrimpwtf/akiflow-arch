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
    ipc, wrap, e_var, t_var, x_var, close = m.groups()
    return (
        f'{ipc}.handle("tray.setTitle",{wrap}({e_var},{t_var})=>{{{x_var}.title={t_var},'
        f'{x_var}.updateTitleAndIcon({x_var}.title);'
        'try{const _d=require("path").join(require("os").homedir(),".cache","akiflow");'
        'require("fs").mkdirSync(_d,{recursive:!0});'
        f'require("fs").writeFileSync(require("path").join(_d,"tray-status.json"),'
        f'JSON.stringify({{title:{t_var}||"",hasEvent:!!{t_var},timestamp:Date.now()}}))'
        f'}}catch(_e){{}}}}{close})'
    )


# Header tweaks for the frameless main window. The renderer is a remote web app,
# so these are injected at runtime using stable element ids / the app's own classes:
#  - sync (refresh) and command-bar buttons move to the far left (refresh first)
#  - the app's rounded main panel is squared off, since the window itself is square
#  - the right side hosts Akiflow-styled window controls (the app only renders its
#    own controls on Windows), reusing the app's `.windowControls` classes so the
#    colors, sizes and hover states come from its stylesheet and theme
HEADER_CSS = (
    ".main-header{padding-left:calc(var(--aki-wc-w,124px) + 4px)!important}"
    "#syncIcon-container{position:absolute;left:6px;top:50%;transform:translateY(-50%);z-index:1}"
    ".main-header div:has(>div>#main-header-learn-command-bar)"
    "{position:absolute;left:42px;top:50%;transform:translateY(-50%);z-index:1}"
    ".header-outer{padding-right:var(--aki-wc-w,124px)}"
    "#main-app-container{border-radius:0!important}"
)

# window state values come from the app's own enum: 0 minimized, 1 normal, 2 maximized, 3 fullscreen
CONTROLS_JS = r"""(()=>{
const api=window.electronAPI;
if(!api||document.getElementById("aki-window-controls"))return;
const S=d=>'<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round">'+d+'</svg>';
const ICON={minimize:S('<path d="M1 5h8"/>'),maximize:S('<rect x="1.5" y="1.5" width="7" height="7" rx="1.2"/>'),
restore:S('<rect x="1.5" y="3" width="5.5" height="5.5" rx="1"/><path d="M3.5 3v-.6a.9.9 0 0 1 .9-.9h3.2a.9.9 0 0 1 .9.9v3.2a.9.9 0 0 1-.9.9H7"/>'),
close:S('<path d="M1.5 1.5l7 7M8.5 1.5l-7 7"/>')};
const mk=(cls,title,fn)=>{const b=document.createElement("button");b.className="windowControls-button "+cls+" flex items-center justify-center w-9 h-full rounded-md";b.title=title;b.tabIndex=-1;b.innerHTML=ICON[cls];b.onclick=fn;return b};
let state=1;
const bMin=mk("minimize","Minimize",()=>api.mainWindowMinimize());
const bMax=mk("maximize","Maximize",()=>(state===2||state===3)?api.mainWindowRestore():api.mainWindowMaximize());
const bClose=mk("close","Close",()=>api.mainWindowClose());
const setState=s=>{state=s;const m=s===2||s===3;bMax.innerHTML=m?ICON.restore:ICON.maximize;bMax.title=m?"Restore":"Maximize";bMax.classList.toggle("restore",m);bMax.classList.toggle("maximize",!m)};
document.addEventListener("mouseover",e=>{const t=e.target.closest&&e.target.closest('.main-header [data-tooltip-position="left"]');if(t)t.setAttribute("data-tooltip-position","right")},true);
const wrap=document.createElement("div");
wrap.id="aki-window-controls";
wrap.className="windowControls flex items-center gap-1 pl-2 pr-0.5 py-0.5 rounded-r-md select-none not-draggable";
wrap.append(bMin,bMax,bClose);
Object.assign(wrap.style,{position:"fixed",top:"0",right:"0",zIndex:"5002"});
const place=()=>{const h=document.querySelector(".header-outer"),r=h?h.getBoundingClientRect():{top:2,height:32};
wrap.style.top=r.top+"px";wrap.style.height=r.height+"px";
document.documentElement.style.setProperty("--aki-wc-w",wrap.offsetWidth+"px")};
document.body.appendChild(wrap);place();
addEventListener("resize",place);new ResizeObserver(place).observe(document.body);
try{api.mainWindowGetWindowState().then(setState)}catch(e){}
try{api.ipcListener("mainWindow.stateChanged",(e,s)=>setState(s))}catch(e){}
})()"""


def _window_chrome_repl(m):
    # Hide the menu bar (accelerators keep working) and, on every page load, inject
    # the header CSS and the Akiflow-styled window controls.
    return (
        'process.platform==="linux"&&((w)=>{'
        'w.setMenuBarVisibility(!1);'
        # The app only emits mainWindow.stateChanged for maximize/restore on Windows;
        # the injected controls need it to flip the maximize/restore icon.
        'const _s=()=>{try{w.webContents.send("mainWindow.stateChanged",'
        'w.isFullScreen()?3:w.isMaximized()?2:w.isMinimized()?0:1)}catch(_x){}};'
        # Wayland can still report the old state when the event fires, so re-check shortly after.
        '["maximize","unmaximize","minimize","restore","enter-full-screen","leave-full-screen"].forEach(_v=>w.on(_v,()=>{_s();setTimeout(_s,200)}));'
        'w.webContents.on("dom-ready",()=>{'
        f'w.webContents.insertCSS({json.dumps(HEADER_CSS)}).catch(()=>{{}});'
        f'w.webContents.executeJavaScript({json.dumps(CONTROLS_JS)}).catch(()=>{{}})'
        '})})(globalThis.mainWindow),'
        + m.group(0)
    )


KWIN_ENABLE_CMD = (
    '[ -d /usr/share/kwin/scripts/akiflow-popup ] && '
    '[ "$(kreadconfig6 --file kwinrc --group Plugins --key akiflow-popupEnabled)" != true ] && '
    '{ kwriteconfig6 --file kwinrc --group Plugins --key akiflow-popupEnabled true && '
    'qdbus6 org.kde.KWin /KWin reconfigure; }'
)


def _kwin_enable_js():
    # Turns on the packaged KWin script that places the tray popup next to the panel.
    # Done here because a running plasmashell keeps the old widget code after an update.
    return f'require("child_process").execFile("sh",["-c",{json.dumps(KWIN_ENABLE_CMD)}],()=>{{}});'


MAIN_PATCHES = [
    {
        "name": "Tray status JSON writer",
        # Handles both `ipcMain.handle("tray.setTitle",((e,t)=>{...}))` (<=2.72)
        # and `D.ipcMain.handle("tray.setTitle",(e,t)=>{...})` (>=2.83).
        "pattern": r'((?:\w+\.)?ipcMain)\.handle\("tray\.setTitle",(\(?)\((\w+),(\w+)\)=>\{(\w+)\.title=\4,\5\.updateTitleAndIcon\(\5\.title\)\}(\)?)\)',
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
            "(()=>{if(process.platform===\"linux\"){" + _kwin_enable_js() + "const _fs=require(\"fs\"),_tp=require(\"path\").join(require(\"os\").homedir(),"
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
            "globalThis.trayWindow.__akiBounds={x:_nx,y:_ny<_d.workArea.y?_pos.y+8:_ny,width:_b.width,height:_b.height}}"
            'globalThis.trayWindow._show("fromWidget")'
            "}catch(_e){}})}})()"
        ),
        "required": False,
    },
    {
        "name": "Tray popup honours widget position",
        # _show() calls _repositionTray() right after the watcher positions the
        # window, which used to overwrite it. Let the watcher's bounds win once.
        "pattern": r'(globalThis\.trayWindow\._repositionTray=\(\)=>\{)',
        "replacement": r'\1const _w=globalThis.trayWindow.__akiBounds;'
                       r'if(_w){globalThis.trayWindow.__akiBounds=null;globalThis.trayWindow.setBounds(_w);return}',
        "check_applied": "__akiBounds;if(",
        "required": False,
    },
    {
        "name": "Frameless main window",
        # Was frame:IS_LINUX (server-side titlebar). The app's own header becomes the
        # titlebar; window controls are injected by the "Hide menu bar" patch below.
        "pattern": r'show:(\w+),frame:(\w+)\.IS_LINUX,backgroundColor:"#ffffff"',
        "replacement": r'show:\1,frame:!1,roundedCorners:!1,backgroundColor:"#ffffff"',
        "check_applied": 'frame:!1,roundedCorners:!1,backgroundColor:"#ffffff"',
        "required": False,
    },
    {
        "name": "Hide menu bar, inject header CSS and window controls",
        "pattern": r'globalThis\.mainWindow\.loadURL\(',
        "replacement": _window_chrome_repl,
        "check_applied": 'aki-window-controls',
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

        main_content = read_file_from_asar(f, orig_data_offset, main_entry)
        renderer_content = read_file_from_asar(f, orig_data_offset, renderer_entry) if renderer_entry else None

    main_text = main_content.decode("utf-8")
    main_patched, main_count = apply_patches(main_text, MAIN_PATCHES, "main")

    if renderer_content is None:
        # Newer releases (>=2.74) load the renderer from a remote URL instead of
        # bundling it, so there is nothing to patch client-side.
        print("  publish/renderer/main.js not bundled (remote renderer), skipping renderer patches")
        renderer_patched, renderer_count = "", 0
    else:
        renderer_text = renderer_content.decode("utf-8")
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
    if renderer_count > 0 and renderer_entry:
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
