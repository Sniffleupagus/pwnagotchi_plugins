import logging
import os, time, sys
import html
import json

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import *
from pwnagotchi.ui.view import BLACK
from PIL import ImageFont, ImageDraw
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.utils as utils

try:
    sys.path.append(os.path.dirname(__file__))
    from Touch_UI import Touch_Button as Button
except Exception:
    pass

# Widget may or may not be exported via the * import depending on pwnagotchi version.
# Define a safe fallback so our custom classes always have a base.
try:
    Widget  # noqa: F821 — check if it landed in scope from components import *
except NameError:
    class Widget(object):
        def __init__(self, xy, color):
            self.xy = xy
            self.color = color
        def draw(self, canvas, drawer):
            pass

from textwrap import TextWrapper
from flask import abort, jsonify, request as flask_request
from flask import render_template_string


# ── Custom shape widgets ────────────────────────────────────────────────────

class CustomLine(Widget):
    """A line defined by x0,y0,x1,y1 with configurable width."""
    def __init__(self, xy, color=0xFF, width=1):
        super().__init__(xy, color)
        self.width = width

    def draw(self, canvas, drawer):
        if len(self.xy) == 4:
            drawer.line(self.xy, fill=self.color, width=self.width)


class CustomRect(Widget):
    """A rectangle defined by x0,y0,x1,y1."""
    def __init__(self, xy, color=0xFF, fill=None, width=1):
        super().__init__(xy, color)
        self.fill = fill
        self.width = width

    def draw(self, canvas, drawer):
        if len(self.xy) == 4:
            drawer.rectangle(self.xy, outline=self.color, fill=self.fill, width=self.width)


class CustomEllipse(Widget):
    """An ellipse/circle defined by bounding box x0,y0,x1,y1."""
    def __init__(self, xy, color=0xFF, fill=None, width=1):
        super().__init__(xy, color)
        self.fill = fill
        self.width = width

    def draw(self, canvas, drawer):
        if len(self.xy) == 4:
            drawer.ellipse(self.xy, outline=self.color, fill=self.fill, width=self.width)


class Tweak_View(plugins.Plugin):
    __author__ = 'Sniffleupagus, BraedenP232'
    __version__ = '2.0.0'
    __license__ = 'GPL3'
    __description__ = 'Mobile-friendly UI layout editor with live preview, drag-to-position, Line/Rect/Ellipse support, export/import/reset.'

    #
    # Respects to NurseJackass/Sniffleupagus for the original tweak_view plugin as we all know and love, 
    # which inspired this rewrite with a less "ugly interface" and maybe some guardrails. :)
    # 
    
    def __init__(self):
        self._agent = None
        self._start = time.time()
        self._logger = logging.getLogger(__name__)
        self._tweaks = {}
        self._untweak = {}
        self._already_updated = []
        self._custom_shapes = {}   # key -> {'type': ..., 'props': {...}}

        self.myFonts = {
            "Small": fonts.Small,
            "BoldSmall": fonts.BoldSmall,
            "Medium": fonts.Medium,
            "Bold": fonts.Bold,
            "BoldBig": fonts.BoldBig,
            "Huge": fonts.Huge
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _parse_xy(self, value):
        """Parse 'x0,y0' or 'x0,y0,x1,y1' into a list of ints."""
        return [int(float(v.strip())) for v in str(value).split(",")]

    def _xy_str(self, xy_list):
        return ",".join(str(v) for v in xy_list)

    def get_ui_state(self):
        """Get current UI state as JSON for AJAX requests."""
        if not self._agent:
            return {"error": "Agent not available"}

        view = self._agent.view()
        state = {}

        for element_name, element in view._state._state.items():
            if not isinstance(element, Widget):
                continue

            elem_data = {
                "type": type(element).__name__,
                "properties": {}
            }

            is_line = isinstance(element, Line) or isinstance(element, CustomLine)
            is_shape = isinstance(element, (CustomRect, CustomEllipse))

            for key in dir(element):
                if key.startswith("__") or key in ["draw", "value"]:
                    continue
                try:
                    val = getattr(element, key)
                    if callable(val):
                        continue
                    if key == "xy":
                        elem_data["properties"][key] = ",".join(map(str, val))
                    elif key in ["font", "text_font", "alt_font", "label_font"]:
                        font_name = "Unknown"
                        for name, font in self.myFonts.items():
                            if val == font:
                                font_name = name
                                break
                        elem_data["properties"][key] = font_name
                    elif type(val) in (int, str, float, bool):
                        elem_data["properties"][key] = val
                    elif type(val) in (list, tuple):
                        elem_data["properties"][key] = ",".join(map(str, val))
                except Exception:
                    pass

            # For Lines, show a friendly breakdown of the 4-point xy
            if is_line or is_shape:
                xy = elem_data["properties"].get("xy", "0,0,0,0")
                parts = [v.strip() for v in xy.split(",")]
                while len(parts) < 4:
                    parts.append("0")
                elem_data["properties"]["xy"] = ",".join(parts[:4])
                elem_data["is_line_or_shape"] = True

            state[element_name] = elem_data

        # Add custom shapes added via this plugin
        for name, shape in self._custom_shapes.items():
            state[name] = {
                "type": shape["type"],
                "properties": dict(shape["props"]),
                "is_line_or_shape": True,
                "is_custom": True
            }

        return state

    def get_ui_dimensions(self):
        try:
            if self._ui:
                return {"width": self._ui.width(), "height": self._ui.height()}
        except Exception:
            pass
        return {"width": 250, "height": 122}

    def _add_shape_to_view(self, name, shape_type, props):
        """Add or update a custom shape widget in the view state."""
        xy_raw = props.get("xy", "0,0,10,10")
        xy = self._parse_xy(xy_raw)
        while len(xy) < 4:
            xy.append(0)

        color = int(props.get("color", 0xFF))
        fill_raw = props.get("fill", None)
        fill = int(fill_raw) if fill_raw not in (None, "", "None", "null") else None
        width = int(props.get("width", 1))

        if shape_type == "CustomLine":
            widget = CustomLine(xy=xy, color=color, width=width)
        elif shape_type == "CustomRect":
            widget = CustomRect(xy=xy, color=color, fill=fill, width=width)
        elif shape_type == "CustomEllipse":
            widget = CustomEllipse(xy=xy, color=color, fill=fill, width=width)
        else:
            return False

        self._ui._state.add_element(name, widget)
        return True

    def get_template(self):
        return r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>tweak_view // pwnagotchi</title>
    <meta name="csrf_token" content="{{ csrf_token() }}">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Exo+2:wght@300;600;800&display=swap');
        :root {
            --bg: #080c0e; --panel: #0d1417; --border: #1a2a2a;
            --accent: #00e5ff; --accent2: #39ff14; --warn: #ff6b35;
            --danger: #ff2255; --muted: #3a5555; --text: #b0d4d4;
            --text-dim: #557070; --font-mono: 'Share Tech Mono', monospace;
            --font-ui: 'Exo 2', sans-serif;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: var(--font-mono); background: var(--bg); color: var(--text);
               height: 100dvh; overflow: hidden; display: flex; flex-direction: column; }
        .topbar { display: flex; align-items: center; justify-content: space-between;
                  padding: 0 16px; height: 48px; background: var(--panel);
                  border-bottom: 1px solid var(--accent); flex-shrink: 0; gap: 8px;
                  position: relative; z-index: 200; }
        .topbar-title { font-family: var(--font-ui); font-weight: 800; font-size: 15px;
                        color: var(--accent); letter-spacing: 2px; text-transform: uppercase;
                        white-space: nowrap; flex-shrink: 0; }
        .topbar-title span { color: var(--accent2); }
        .topbar-actions { display: flex; gap: 6px; align-items: center; flex-wrap: nowrap; }
        .layout { display: flex; flex: 1; overflow: hidden; }
        .sidebar { width: 220px; flex-shrink: 0; background: var(--panel);
                   border-right: 1px solid var(--border); display: flex;
                   flex-direction: column; overflow: hidden; transition: transform 0.25s ease; }
        .sidebar-header { padding: 10px 12px 8px; border-bottom: 1px solid var(--border); }
        .search-box { width: 100%; background: var(--bg); border: 1px solid var(--muted);
                      color: var(--text); font-family: var(--font-mono); font-size: 12px;
                      padding: 6px 10px; border-radius: 3px; outline: none; margin-bottom: 6px; }
        .search-box:focus { border-color: var(--accent); }
        .search-box::placeholder { color: var(--text-dim); }
        .add-shape-row { display: flex; gap: 4px; }
        .add-shape-row select { flex: 1; background: var(--bg); border: 1px solid var(--muted);
                                color: var(--text); font-family: var(--font-mono); font-size: 11px;
                                padding: 4px 6px; border-radius: 3px; outline: none; }
        .add-shape-row select:focus { border-color: var(--accent); }
        .add-shape-row select option { background: var(--panel); }
        .element-list { flex: 1; overflow-y: auto; list-style: none; padding: 6px; }
        .element-list::-webkit-scrollbar { width: 4px; }
        .element-list::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 2px; }
        .element-item { padding: 7px 10px; margin-bottom: 3px; border: 1px solid transparent;
                        border-radius: 3px; cursor: pointer; transition: all 0.15s; font-size: 12px; }
        .element-item:hover { background: rgba(0,229,255,0.06); border-color: var(--muted); }
        .element-item.active { background: rgba(0,229,255,0.1); border-color: var(--accent); color: var(--accent); }
        .element-item .el-name { font-weight: bold; font-size: 12px; }
        .element-item .el-type { font-size: 10px; color: var(--text-dim); }
        .element-item .el-custom { font-size: 9px; color: var(--accent2); }
        .modified-badge { display: inline-block; background: var(--warn); color: #000;
                          font-size: 9px; padding: 1px 4px; border-radius: 2px; margin-left: 4px;
                          font-family: var(--font-ui); font-weight: 700; }
        .center { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .preview-wrap { flex: 1; display: flex; align-items: center; justify-content: center;
                        padding: 20px; background:
                            repeating-linear-gradient(0deg, transparent, transparent 19px, rgba(0,229,255,0.04) 20px),
                            repeating-linear-gradient(90deg, transparent, transparent 19px, rgba(0,229,255,0.04) 20px);
                        position: relative; overflow: auto; }
        .preview-frame { position: relative; display: inline-block; border: 1px solid var(--accent);
                         box-shadow: 0 0 24px rgba(0,229,255,0.15), inset 0 0 8px rgba(0,0,0,0.5);
                         border-radius: 2px; }
        #preview-img { display: block; image-rendering: pixelated; image-rendering: crisp-edges; }
        #overlay-canvas { position: absolute; top: 0; left: 0; pointer-events: none; }
        .preview-status { position: absolute; bottom: 8px; right: 12px; font-size: 10px;
                          color: var(--text-dim); display: flex; align-items: center; gap: 6px; }
        .pulse { width: 6px; height: 6px; border-radius: 50%; background: var(--accent2);
                 animation: pulse 2s ease-in-out infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }
        .props-panel { width: 280px; flex-shrink: 0; background: var(--panel);
                       border-left: 1px solid var(--border); display: flex;
                       flex-direction: column; overflow: hidden; }
        .props-header { padding: 12px 14px; border-bottom: 1px solid var(--border);
                        font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 1px; }
        .props-header .el-label { font-family: var(--font-ui); font-weight: 600; font-size: 14px;
                                  color: var(--accent); text-transform: none; letter-spacing: 0; margin-top: 2px; }
        .props-body { flex: 1; overflow-y: auto; padding: 12px; }
        .props-body::-webkit-scrollbar { width: 4px; }
        .props-body::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 2px; }
        .prop-row { margin-bottom: 12px; }
        .prop-label { font-size: 10px; color: var(--text-dim); text-transform: uppercase;
                      letter-spacing: 1px; margin-bottom: 4px; }
        .prop-input { width: 100%; background: var(--bg); border: 1px solid var(--muted);
                      color: var(--text); font-family: var(--font-mono); font-size: 12px;
                      padding: 6px 8px; border-radius: 3px; outline: none; transition: border-color 0.2s; }
        .prop-input:focus { border-color: var(--accent); }
        select.prop-input option { background: var(--panel); }
        .xy-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .xy-col label { font-size: 10px; color: var(--text-dim); display: block; margin-bottom: 3px; }
        .nudge-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3px; margin-top: 4px; }
        .nudge-btn { background: var(--bg); border: 1px solid var(--muted); color: var(--text);
                     font-family: var(--font-mono); font-size: 11px; padding: 5px 0; border-radius: 2px;
                     cursor: pointer; transition: all 0.15s; text-align: center; }
        .nudge-btn:hover { border-color: var(--accent); color: var(--accent); }
        .nudge-btn:active { background: var(--accent); color: #000; }
        .btn { font-family: var(--font-mono); font-size: 12px; padding: 7px 14px;
               border: 1px solid var(--muted); border-radius: 3px; cursor: pointer;
               transition: all 0.15s; white-space: nowrap; background: transparent; color: var(--text); }
        .btn:hover { border-color: var(--accent); color: var(--accent); }
        .btn:active { background: rgba(0,229,255,0.15); }
        .btn-primary { border-color: var(--accent); color: var(--accent); }
        .btn-primary:hover { background: var(--accent); color: #000; }
        .btn-success { border-color: var(--accent2); color: var(--accent2); }
        .btn-success:hover { background: var(--accent2); color: #000; }
        .btn-warn { border-color: var(--warn); color: var(--warn); }
        .btn-warn:hover { background: var(--warn); color: #000; }
        .btn-danger { border-color: var(--danger); color: var(--danger); }
        .btn-danger:hover { background: var(--danger); color: #fff; }
        .btn-sm { font-size: 11px; padding: 5px 10px; }
        .props-footer { padding: 10px 12px; border-top: 1px solid var(--border);
                        display: flex; gap: 6px; flex-wrap: wrap; }
        .statsbar { display: flex; gap: 16px; padding: 0 12px; align-items: center; }
        .stat { font-size: 11px; color: var(--text-dim); }
        .stat span { color: var(--accent); font-weight: bold; }
        #toast-container { position: fixed; bottom: 20px; right: 20px; display: flex;
                           flex-direction: column; gap: 8px; z-index: 9999; }
        .toast { font-family: var(--font-mono); font-size: 12px; padding: 10px 16px; border-radius: 3px;
                 border: 1px solid var(--accent); background: var(--panel); color: var(--accent);
                 animation: toastIn 0.25s ease, toastOut 0.3s ease 2.7s forwards;
                 min-width: 200px; max-width: 320px; }
        .toast.error { border-color: var(--danger); color: var(--danger); }
        .toast.warn { border-color: var(--warn); color: var(--warn); }
        @keyframes toastIn { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes toastOut { from { opacity: 1; } to { opacity: 0; pointer-events: none; } }
        @media (max-width: 900px) {
            .sidebar, .props-panel { position: fixed; top: 48px; bottom: 0; z-index: 500; transition: transform 0.25s ease; }
            .sidebar { left: 0; width: 80vw; max-width: 300px; transform: translateX(-110%); border-right: 1px solid var(--accent); }
            .sidebar.open { transform: translateX(0); }
            .props-panel { right: 0; width: 80vw; max-width: 300px; transform: translateX(110%); border-left: 1px solid var(--accent); }
            .props-panel.open { transform: translateX(0); }
            .scrim { display: block !important; }
        }
        .scrim { display: none; position: fixed; inset: 0; top: 48px; background: rgba(0,0,0,0.6); z-index: 499; }
        .loading-msg { color: var(--text-dim); font-size: 12px; padding: 20px; text-align: center; }
        .toggle-label { font-size: 11px; color: var(--text-dim); display: flex; align-items: center;
                        gap: 6px; cursor: pointer; user-select: none; }
        .toggle-box { width: 30px; height: 16px; border: 1px solid var(--muted); border-radius: 8px;
                      position: relative; background: var(--bg); transition: all 0.2s; flex-shrink: 0; }
        .toggle-box::after { content: ''; position: absolute; width: 10px; height: 10px; border-radius: 50%;
                             background: var(--muted); top: 2px; left: 2px; transition: all 0.2s; }
        .toggle-input { display: none; }
        .toggle-input:checked + .toggle-box { border-color: var(--accent2); background: rgba(57,255,20,0.1); }
        .toggle-input:checked + .toggle-box::after { background: var(--accent2); left: 16px; }
        #import-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8);
                          z-index: 9000; align-items: center; justify-content: center; }
        #import-overlay.open { display: flex; }
        .import-box { background: var(--panel); border: 1px solid var(--accent); border-radius: 4px;
                      padding: 20px; width: min(90vw, 460px); }
        .import-box h3 { font-family: var(--font-ui); font-weight: 600; color: var(--accent); margin-bottom: 12px; }
        #import-textarea { width: 100%; height: 160px; background: var(--bg); border: 1px solid var(--muted);
                           color: var(--text); font-family: var(--font-mono); font-size: 11px; padding: 8px;
                           border-radius: 3px; resize: vertical; outline: none; }
        #import-textarea:focus { border-color: var(--accent); }
        .import-actions { display: flex; gap: 8px; margin-top: 10px; justify-content: flex-end; }
        .section-label { font-size: 9px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 1px;
                         padding: 4px 10px 2px; border-top: 1px solid var(--border); margin-top: 4px; }
    </style>
</head>
<body>
<div class="scrim" id="scrim" onclick="closeAllPanels()"></div>
<div id="import-overlay">
    <div class="import-box">
        <h3>// IMPORT CONFIG</h3>
        <p style="font-size:11px;color:var(--text-dim);margin-bottom:10px;">Paste exported JSON below:</p>
        <textarea id="import-textarea" placeholder='{"VSS.element.xy": "10,20", ...}'></textarea>
        <div class="import-actions">
            <button class="btn btn-sm" onclick="closeImport()">Cancel</button>
            <button class="btn btn-sm btn-primary" onclick="doImport()">Apply Import</button>
        </div>
    </div>
</div>

<div class="topbar">
    <div style="display:flex;align-items:center;gap:10px;min-width:0;">
        <button class="btn btn-sm" id="sidebar-toggle" onclick="toggleSidebar()" style="display:none;padding:5px 10px;font-size:14px;">☰</button>
        <div class="topbar-title">tweak<span>_view</span></div>
    </div>
    <div class="statsbar" id="statsbar">
        <div class="stat">elements: <span id="stat-total">0</span></div>
        <div class="stat">modified: <span id="stat-mod">0</span></div>
    </div>
    <div class="topbar-actions">
        <label class="toggle-label">
            <input type="checkbox" class="toggle-input" id="auto-refresh" checked>
            <div class="toggle-box"></div>
            <span style="display:none;" id="ar-label">auto</span>
        </label>
        <button class="btn btn-sm btn-primary" onclick="refreshPreview()">↺ refresh</button>
        <button class="btn btn-sm" onclick="exportConfig()">↓ export</button>
        <button class="btn btn-sm" onclick="openImport()">↑ import</button>
        <button class="btn btn-sm btn-danger" onclick="resetAll()">✕ reset</button>
        <button class="btn btn-sm" id="props-toggle" onclick="toggleProps()" style="display:none;">⚙ props</button>
    </div>
</div>

<div class="layout">
    <div class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <input type="text" class="search-box" id="search" placeholder="filter elements...">
            <div class="add-shape-row">
                <select id="new-shape-type">
                    <option value="CustomLine">Line</option>
                    <option value="CustomRect">Rectangle</option>
                    <option value="CustomEllipse">Ellipse</option>
                </select>
                <button class="btn btn-sm btn-success" onclick="addShape()">+ add</button>
            </div>
        </div>
        <ul class="element-list" id="el-list">
            <li class="loading-msg">loading...</li>
        </ul>
    </div>

    <div class="center">
        <div class="preview-wrap" id="preview-wrap">
            <div class="preview-frame" id="preview-frame">
                <img id="preview-img" src="/ui?t=0" alt="pwnagotchi UI">
                <canvas id="overlay-canvas"></canvas>
            </div>
        </div>
        <div class="preview-status">
            <div class="pulse"></div>
            <span id="last-refresh">--</span>
        </div>
    </div>

    <div class="props-panel" id="props-panel">
        <div class="props-header">
            Properties
            <div class="el-label" id="props-title">—</div>
        </div>
        <div class="props-body" id="props-body">
            <p class="loading-msg">select an element</p>
        </div>
        <div class="props-footer" id="props-footer" style="display:none;">
            <button class="btn btn-sm btn-success" onclick="applyChanges()">▶ apply</button>
            <button class="btn btn-sm" onclick="revertElement()">↩ revert</button>
            <button class="btn btn-sm btn-danger" id="delete-btn" onclick="deleteElement()" style="display:none;">✕ delete</button>
        </div>
    </div>
</div>

<div id="toast-container"></div>

<script>
const CSRF = document.querySelector('meta[name="csrf_token"]').content;
let uiState = {};
let currentEl = null;
let modifiedEls = new Set();
let previewScale = 1;
let refreshTimer = null;
const FONT_LIST = ["Small","BoldSmall","Medium","Bold","BoldBig","Huge"];
const SHAPE_TYPES = ["CustomLine","CustomRect","CustomEllipse"];

// ── MOBILE ────────────────────────────────────────────────────────────────────
function setupMobileNav() {
    const mobile = window.innerWidth <= 900;
    document.getElementById('sidebar-toggle').style.display = mobile ? 'block' : 'none';
    document.getElementById('props-toggle').style.display = mobile ? 'block' : 'none';
    document.getElementById('ar-label').style.display = mobile ? 'none' : 'inline';
}
window.addEventListener('resize', setupMobileNav);
setupMobileNav();

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('props-panel').classList.remove('open');
}
function toggleProps() {
    document.getElementById('props-panel').classList.toggle('open');
    document.getElementById('sidebar').classList.remove('open');
}
function closeAllPanels() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('props-panel').classList.remove('open');
}

// ── DATA ──────────────────────────────────────────────────────────────────────
async function fetchState() {
    try {
        const r = await fetch('/plugins/tweak_view/api/state');
        uiState = await r.json();
        renderList();
        updateStats();
    } catch(e) {
        toast('Failed to load UI state', 'error');
    }
}

function updateStats() {
    document.getElementById('stat-total').textContent = Object.keys(uiState).length;
    document.getElementById('stat-mod').textContent = modifiedEls.size;
}

// ── ELEMENT LIST ──────────────────────────────────────────────────────────────
function renderList() {
    const q = document.getElementById('search').value.toLowerCase();
    const ul = document.getElementById('el-list');
    ul.innerHTML = '';

    const builtins = [], custom = [];
    for (const [name, data] of Object.entries(uiState)) {
        if (!q || name.toLowerCase().includes(q)) {
            (data.is_custom ? custom : builtins).push([name, data]);
        }
    }

    builtins.sort(([a],[b]) => a.localeCompare(b));
    custom.sort(([a],[b]) => a.localeCompare(b));

    if (!builtins.length && !custom.length) {
        ul.innerHTML = '<li class="loading-msg">no elements found</li>';
        return;
    }

    for (const [name, data] of builtins) {
        ul.appendChild(makeListItem(name, data));
    }

    if (custom.length) {
        const lbl = document.createElement('li');
        lbl.className = 'section-label';
        lbl.textContent = '── custom shapes';
        ul.appendChild(lbl);
        for (const [name, data] of custom) {
            ul.appendChild(makeListItem(name, data));
        }
    }
}

function makeListItem(name, data) {
    const li = document.createElement('li');
    li.className = 'element-item' + (currentEl === name ? ' active' : '');
    const mod = modifiedEls.has(name) ? '<span class="modified-badge">MOD</span>' : '';
    const custom = data.is_custom ? '<span class="el-custom">★ custom</span>' : '';
    li.innerHTML = `<div class="el-name">${name}${mod}</div><div class="el-type">${data.type}</div>${custom}`;
    li.onclick = () => selectElement(name);
    return li;
}

document.getElementById('search').addEventListener('input', renderList);

// ── ADD SHAPE ─────────────────────────────────────────────────────────────────
async function addShape() {
    const type = document.getElementById('new-shape-type').value;
    const name = prompt(`Name for new ${type}:`, `custom_${type.toLowerCase().replace('custom','')}_${Date.now().toString(36)}`);
    if (!name || !name.trim()) return;
    const cleanName = name.trim().replace(/[^a-zA-Z0-9_]/g, '_');

    const defaultXY = type === 'CustomLine' ? '10,60,240,60' : '10,10,100,50';
    try {
        const r = await fetch('/plugins/tweak_view/api/add_shape', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':CSRF},
            body: JSON.stringify({ name: cleanName, type, props: { xy: defaultXY, color: 255, width: 1 } })
        });
        const res = await r.json();
        if (r.ok && res.success) {
            toast(`${type} "${cleanName}" added ✓`);
            await fetchState();
            selectElement(cleanName);
            setTimeout(refreshPreview, 400);
        } else {
            toast(res.error || 'add failed', 'error');
        }
    } catch(e) {
        toast('network error', 'error');
    }
}

// ── SELECT ELEMENT ────────────────────────────────────────────────────────────
function selectElement(name) {
    currentEl = name;
    renderList();
    renderProperties();
    drawOverlay(name);
    if (window.innerWidth <= 900) {
        closeAllPanels();
        setTimeout(() => toggleProps(), 50);
    }
}

// ── OVERLAY ───────────────────────────────────────────────────────────────────
function drawOverlay(name) {
    const canvas = document.getElementById('overlay-canvas');
    const img = document.getElementById('preview-img');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    canvas.style.width = img.width + 'px';
    canvas.style.height = img.height + 'px';
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!name || !uiState[name]) return;
    const props = uiState[name].properties;
    if (!props || !props.xy) return;

    const parts = props.xy.split(',').map(v => parseFloat(v.trim()));
    const isShape = uiState[name].is_line_or_shape;
    ctx.strokeStyle = '#00e5ff';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 2]);

    if (isShape && parts.length === 4) {
        const [x0, y0, x1, y1] = parts;
        const type = uiState[name].type;
        if (type === 'CustomEllipse') {
            // draw ellipse bounding box
            ctx.strokeRect(x0, y0, x1-x0, y1-y0);
        } else {
            ctx.strokeRect(x0, y0, x1-x0, y1-y0);
        }
        // Corner dots
        ctx.setLineDash([]);
        ctx.fillStyle = '#00e5ff';
        [[x0,y0],[x1,y0],[x0,y1],[x1,y1]].forEach(([cx,cy]) => {
            ctx.beginPath(); ctx.arc(cx, cy, 3, 0, Math.PI*2); ctx.fill();
        });
    } else {
        const [x, y] = parts;
        ctx.beginPath();
        ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height);
        ctx.moveTo(0, y); ctx.lineTo(canvas.width, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#00e5ff';
        ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2); ctx.fill();
    }
}

// ── PROPERTIES ────────────────────────────────────────────────────────────────
function renderProperties() {
    const title = document.getElementById('props-title');
    const body = document.getElementById('props-body');
    const footer = document.getElementById('props-footer');
    const deleteBtn = document.getElementById('delete-btn');

    if (!currentEl || !uiState[currentEl]) {
        title.textContent = '—';
        body.innerHTML = '<p class="loading-msg">select an element</p>';
        footer.style.display = 'none';
        return;
    }

    title.textContent = currentEl;
    footer.style.display = 'flex';
    deleteBtn.style.display = uiState[currentEl].is_custom ? 'block' : 'none';

    const props = uiState[currentEl].properties;
    const isLineOrShape = uiState[currentEl].is_line_or_shape;
    let h = '';
    const skip = [];

    for (const [key, value] of Object.entries(props)) {
        if (key.startsWith('_')) continue;

        h += `<div class="prop-row"><div class="prop-label">${key}</div>`;

        if (key === 'xy' && isLineOrShape) {
            // 4-point control: x0,y0,x1,y1
            const p = String(value).split(',');
            while (p.length < 4) p.push('0');
            h += `
            <div class="xy-grid">
                <div class="xy-col">
                    <label>X0 (start)</label>
                    <input type="number" class="prop-input" id="xy_x0" value="${p[0].trim()}" oninput="liveShape()">
                    <div class="nudge-row">
                        <button class="nudge-btn" onclick="nudgeShape('x0',-10)">-10</button>
                        <button class="nudge-btn" onclick="nudgeShape('x0',-1)">-1</button>
                        <button class="nudge-btn" onclick="nudgeShape('x0',1)">+1</button>
                        <button class="nudge-btn" onclick="nudgeShape('x0',10)">+10</button>
                    </div>
                </div>
                <div class="xy-col">
                    <label>Y0 (start)</label>
                    <input type="number" class="prop-input" id="xy_y0" value="${p[1].trim()}" oninput="liveShape()">
                    <div class="nudge-row">
                        <button class="nudge-btn" onclick="nudgeShape('y0',-10)">-10</button>
                        <button class="nudge-btn" onclick="nudgeShape('y0',-1)">-1</button>
                        <button class="nudge-btn" onclick="nudgeShape('y0',1)">+1</button>
                        <button class="nudge-btn" onclick="nudgeShape('y0',10)">+10</button>
                    </div>
                </div>
                <div class="xy-col">
                    <label>X1 (end)</label>
                    <input type="number" class="prop-input" id="xy_x1" value="${p[2].trim()}" oninput="liveShape()">
                    <div class="nudge-row">
                        <button class="nudge-btn" onclick="nudgeShape('x1',-10)">-10</button>
                        <button class="nudge-btn" onclick="nudgeShape('x1',-1)">-1</button>
                        <button class="nudge-btn" onclick="nudgeShape('x1',1)">+1</button>
                        <button class="nudge-btn" onclick="nudgeShape('x1',10)">+10</button>
                    </div>
                </div>
                <div class="xy-col">
                    <label>Y1 (end)</label>
                    <input type="number" class="prop-input" id="xy_y1" value="${p[3].trim()}" oninput="liveShape()">
                    <div class="nudge-row">
                        <button class="nudge-btn" onclick="nudgeShape('y1',-10)">-10</button>
                        <button class="nudge-btn" onclick="nudgeShape('y1',-1)">-1</button>
                        <button class="nudge-btn" onclick="nudgeShape('y1',1)">+1</button>
                        <button class="nudge-btn" onclick="nudgeShape('y1',10)">+10</button>
                    </div>
                </div>
            </div>`;
        } else if (key === 'xy') {
            const p = String(value).split(',');
            h += `
            <div class="xy-grid">
                <div class="xy-col">
                    <label>X</label>
                    <input type="number" class="prop-input" id="xy_x" value="${(p[0]||'0').trim()}" oninput="liveXY()">
                    <div class="nudge-row">
                        <button class="nudge-btn" onclick="nudge('x',-10)">-10</button>
                        <button class="nudge-btn" onclick="nudge('x',-1)">-1</button>
                        <button class="nudge-btn" onclick="nudge('x',1)">+1</button>
                        <button class="nudge-btn" onclick="nudge('x',10)">+10</button>
                    </div>
                </div>
                <div class="xy-col">
                    <label>Y</label>
                    <input type="number" class="prop-input" id="xy_y" value="${(p[1]||'0').trim()}" oninput="liveXY()">
                    <div class="nudge-row">
                        <button class="nudge-btn" onclick="nudge('y',-10)">-10</button>
                        <button class="nudge-btn" onclick="nudge('y',-1)">-1</button>
                        <button class="nudge-btn" onclick="nudge('y',1)">+1</button>
                        <button class="nudge-btn" onclick="nudge('y',10)">+10</button>
                    </div>
                </div>
            </div>`;
        } else if (key.includes('font')) {
            h += `<select class="prop-input" id="prop_${key}" onchange="setProp('${key}',this.value)">`;
            for (const f of FONT_LIST) h += `<option ${f===value?'selected':''}>${f}</option>`;
            h += `</select>`;
        } else {
            const t = typeof value === 'number' ? 'number' : 'text';
            h += `<input type="${t}" class="prop-input" id="prop_${key}" value="${value}" oninput="setProp('${key}',this.value)">`;
        }
        h += `</div>`;
    }

    body.innerHTML = h || '<p class="loading-msg">no editable properties</p>';
}

function setProp(key, value) {
    if (!currentEl) return;
    uiState[currentEl].properties[key] = value;
    modifiedEls.add(currentEl);
    updateStats();
    renderList();
}

function liveXY() {
    const x = document.getElementById('xy_x')?.value;
    const y = document.getElementById('xy_y')?.value;
    if (x === undefined || y === undefined) return;
    setProp('xy', `${x},${y}`);
    drawOverlay(currentEl);
}

function liveShape() {
    const x0 = document.getElementById('xy_x0')?.value ?? '0';
    const y0 = document.getElementById('xy_y0')?.value ?? '0';
    const x1 = document.getElementById('xy_x1')?.value ?? '0';
    const y1 = document.getElementById('xy_y1')?.value ?? '0';
    setProp('xy', `${x0},${y0},${x1},${y1}`);
    drawOverlay(currentEl);
}

function nudge(axis, amount) {
    const el = document.getElementById(`xy_${axis}`);
    if (!el) return;
    el.value = parseInt(el.value || '0') + amount;
    liveXY(); applyChanges();
}

function nudgeShape(axis, amount) {
    const el = document.getElementById(`xy_${axis}`);
    if (!el) return;
    el.value = parseInt(el.value || '0') + amount;
    liveShape(); applyChanges();
}

// ── APPLY / REVERT / DELETE ───────────────────────────────────────────────────
async function applyChanges() {
    if (!currentEl) return;
    try {
        const r = await fetch('/plugins/tweak_view/api/update', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':CSRF},
            body: JSON.stringify({ element: currentEl, properties: uiState[currentEl].properties,
                                   is_custom: !!uiState[currentEl].is_custom,
                                   shape_type: uiState[currentEl].type })
        });
        const res = await r.json();
        if (r.ok && res.success) {
            toast('applied ✓');
            setTimeout(refreshPreview, 400);
        } else {
            toast(res.error || 'apply failed', 'error');
        }
    } catch(e) { toast('network error', 'error'); }
}

async function revertElement() {
    if (!currentEl) return;
    if (!confirm(`Revert all changes to "${currentEl}"?`)) return;
    try {
        const r = await fetch('/plugins/tweak_view/api/revert', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':CSRF},
            body: JSON.stringify({ element: currentEl })
        });
        const res = await r.json();
        if (r.ok && res.success) {
            toast('reverted');
            modifiedEls.delete(currentEl);
            await fetchState();
            setTimeout(refreshPreview, 400);
        } else {
            toast('revert failed', 'error');
        }
    } catch(e) { toast('network error', 'error'); }
}

async function deleteElement() {
    if (!currentEl) return;
    if (!confirm(`Delete custom shape "${currentEl}"? This cannot be undone.`)) return;
    try {
        const r = await fetch('/plugins/tweak_view/api/delete_shape', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':CSRF},
            body: JSON.stringify({ name: currentEl })
        });
        const res = await r.json();
        if (r.ok && res.success) {
            toast(`"${currentEl}" deleted`);
            currentEl = null;
            await fetchState();
            renderProperties();
            setTimeout(refreshPreview, 400);
        } else {
            toast(res.error || 'delete failed', 'error');
        }
    } catch(e) { toast('network error', 'error'); }
}

// ── EXPORT / IMPORT / RESET ───────────────────────────────────────────────────
async function exportConfig() {
    try {
        const r = await fetch('/plugins/tweak_view/api/export');
        const data = await r.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'tweak_view.json'; a.click();
        URL.revokeObjectURL(url);
        toast('config exported ✓');
    } catch(e) { toast('export failed', 'error'); }
}

function openImport() {
    document.getElementById('import-textarea').value = '';
    document.getElementById('import-overlay').classList.add('open');
}
function closeImport() { document.getElementById('import-overlay').classList.remove('open'); }

async function doImport() {
    const raw = document.getElementById('import-textarea').value.trim();
    if (!raw) { toast('paste JSON first', 'warn'); return; }
    let parsed; try { parsed = JSON.parse(raw); } catch(e) { toast('invalid JSON', 'error'); return; }
    try {
        const r = await fetch('/plugins/tweak_view/api/import', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':CSRF},
            body: JSON.stringify(parsed)
        });
        const res = await r.json();
        if (r.ok && res.success) {
            toast(`imported ${res.count} tweaks ✓`);
            closeImport(); modifiedEls.clear();
            await fetchState(); setTimeout(refreshPreview, 500);
        } else { toast(res.error || 'import failed', 'error'); }
    } catch(e) { toast('network error', 'error'); }
}

async function resetAll() {
    if (!confirm('Reset ALL tweaks and custom shapes? Cannot be undone.')) return;
    try {
        const r = await fetch('/plugins/tweak_view/api/reset', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':CSRF},
            body: JSON.stringify({})
        });
        const res = await r.json();
        if (r.ok && res.success) {
            toast('all tweaks reset ✓');
            modifiedEls.clear(); currentEl = null;
            await fetchState(); renderProperties(); setTimeout(refreshPreview, 500);
        } else { toast(res.error || 'reset failed', 'error'); }
    } catch(e) { toast('network error', 'error'); }
}

// ── PREVIEW ───────────────────────────────────────────────────────────────────
function refreshPreview() {
    const img = document.getElementById('preview-img');
    const newImg = new Image();
    newImg.onload = () => {
        img.src = newImg.src;
        const canvas = document.getElementById('overlay-canvas');
        canvas.style.width = img.offsetWidth + 'px';
        canvas.style.height = img.offsetHeight + 'px';
        drawOverlay(currentEl);
        document.getElementById('last-refresh').textContent = new Date().toLocaleTimeString();
    };
    newImg.src = `/ui?t=${Date.now()}`;
}

function scalePreview() {
    const wrap = document.getElementById('preview-wrap');
    const img = document.getElementById('preview-img');
    const wW = wrap.clientWidth - 40;
    const wH = wrap.clientHeight - 40;
    const iW = img.naturalWidth || 250;
    const iH = img.naturalHeight || 122;
    const s = Math.min(Math.floor(wW / iW), Math.floor(wH / iH), 6) || 2;
    img.width = iW * s; img.height = iH * s; previewScale = s;
    const canvas = document.getElementById('overlay-canvas');
    canvas.width = iW; canvas.height = iH;
    canvas.style.width = img.width + 'px'; canvas.style.height = img.height + 'px';
    drawOverlay(currentEl);
}

document.getElementById('preview-img').onload = scalePreview;
window.addEventListener('resize', scalePreview);

function startAutoRefresh() { stopAutoRefresh(); refreshTimer = setInterval(refreshPreview, 5000); }
function stopAutoRefresh() { if (refreshTimer) clearInterval(refreshTimer); }
document.getElementById('auto-refresh').addEventListener('change', function() {
    this.checked ? startAutoRefresh() : stopAutoRefresh();
    toast(this.checked ? 'auto-refresh on' : 'auto-refresh off');
});

// ── TOAST ─────────────────────────────────────────────────────────────────────
function toast(msg, type='') {
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = '> ' + msg;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => el.remove(), 3100);
}

// ── INIT ──────────────────────────────────────────────────────────────────────
refreshPreview();
fetchState();
startAutoRefresh();
</script>
</body>
</html>
"""

    def on_webhook(self, path, request):
        try:
            if not self._agent and hasattr(self, '_ui') and self._ui:
                try:
                    self._agent = self._ui._agent
                except Exception:
                    pass

            if path is None:
                path = ""

            # ── API ROUTES ──────────────────────────────────────────────────

            if path == "api/state":
                return jsonify(self.get_ui_state())

            elif path == "api/export":
                data = dict(self._tweaks)
                # Include custom shapes
                data["__custom_shapes__"] = self._custom_shapes
                return jsonify(data)

            elif path == "api/import" and request.method == "POST":
                data = request.get_json()
                if not isinstance(data, dict):
                    return jsonify({"success": False, "error": "Expected JSON object"}), 400

                count = 0
                # Restore custom shapes if present
                if "__custom_shapes__" in data:
                    for name, shape in data.pop("__custom_shapes__").items():
                        self._custom_shapes[name] = shape
                        self._add_shape_to_view(name, shape["type"], shape["props"])
                        count += 1

                for tag, value in data.items():
                    if tag.startswith("VSS.") and tag.count(".") == 2:
                        self._tweaks[tag] = value
                        count += 1

                try:
                    self._save()
                    self._already_updated = []
                    self.update_elements(self._ui)
                    return jsonify({"success": True, "count": count})
                except Exception as err:
                    self._logger.error(f"Import error: {err}")
                    return jsonify({"success": False, "error": str(err)}), 500

            elif path == "api/add_shape" and request.method == "POST":
                data = request.get_json()
                name = data.get("name", "").strip()
                shape_type = data.get("type", "CustomLine")
                props = data.get("props", {})

                if not name:
                    return jsonify({"success": False, "error": "Name required"}), 400
                if shape_type not in ("CustomLine", "CustomRect", "CustomEllipse"):
                    return jsonify({"success": False, "error": "Unknown shape type"}), 400

                self._custom_shapes[name] = {"type": shape_type, "props": props}
                self._add_shape_to_view(name, shape_type, props)
                self._save()

                if hasattr(self._ui, 'update'):
                    self._ui.update(force=True)

                return jsonify({"success": True})

            elif path == "api/delete_shape" and request.method == "POST":
                data = request.get_json()
                name = data.get("name", "")

                if name not in self._custom_shapes:
                    return jsonify({"success": False, "error": "Custom shape not found"}), 404

                del self._custom_shapes[name]
                # Remove from tweaks too
                for k in list(self._tweaks.keys()):
                    if k.startswith(f"VSS.{name}."):
                        del self._tweaks[k]

                try:
                    self._ui._state.remove_element(name)
                except Exception:
                    pass

                self._save()
                if hasattr(self._ui, 'update'):
                    self._ui.update(force=True)

                return jsonify({"success": True})

            elif path == "api/reset" and request.method == "POST":
                try:
                    for tag, orig in self._untweak.items():
                        try:
                            vss, element, key = tag.split(".")
                            if element in self._ui._state._state:
                                setattr(self._ui._state._state[element], key, orig)
                        except Exception as err:
                            self._logger.warning(f"Reset restore failed for {tag}: {err}")

                    # Remove custom shapes from view
                    for name in list(self._custom_shapes.keys()):
                        try:
                            self._ui._state.remove_element(name)
                        except Exception:
                            pass

                    self._tweaks = {}
                    self._untweak = {}
                    self._already_updated = []
                    self._custom_shapes = {}
                    self._save()

                    return jsonify({"success": True})
                except Exception as err:
                    self._logger.error(f"Reset error: {err}")
                    return jsonify({"success": False, "error": str(err)}), 500

            elif path == "api/update" and request.method == "POST":
                data = request.get_json()
                element = data.get('element')
                properties = data.get('properties', {})
                is_custom = data.get('is_custom', False)
                shape_type = data.get('shape_type', 'CustomLine')

                # Update custom shape props in memory
                if is_custom and element in self._custom_shapes:
                    self._custom_shapes[element]["props"].update(properties)
                    # Re-add the widget to view with updated props
                    try:
                        self._ui._state.remove_element(element)
                    except Exception:
                        pass
                    self._add_shape_to_view(element, shape_type, self._custom_shapes[element]["props"])
                else:
                    for key, value in properties.items():
                        if key == 'color':
                            continue
                        tag = f"VSS.{element}.{key}"
                        self._tweaks[tag] = value

                try:
                    self._save()
                    self._already_updated = []
                    self.update_elements(self._ui)

                    if hasattr(self._ui, 'update'):
                        self._ui.update(force=True)

                    return jsonify({"success": True})
                except Exception as err:
                    self._logger.error(f"Update error: {err}")
                    return jsonify({"success": False, "error": str(err)}), 500

            elif path == "api/revert" and request.method == "POST":
                data = request.get_json()
                element = data.get('element')

                keys_to_remove = [k for k in self._tweaks if k.startswith(f"VSS.{element}.")]
                for key in keys_to_remove:
                    if key in self._untweak:
                        try:
                            vss, elem, prop = key.split(".")
                            if elem in self._ui._state._state:
                                setattr(self._ui._state._state[elem], prop, self._untweak[key])
                        except Exception:
                            pass
                    del self._tweaks[key]

                self._save()
                return jsonify({"success": True})

            if request.method == "GET" and (path == "" or path == "/"):
                import time as _time
                return render_template_string(self.get_template(), timestamp=int(_time.time()))

            abort(404)

        except Exception as err:
            self._logger.warning("webhook err: %s" % repr(err))
            return jsonify({"error": str(err)}), 500

    # ── Plugin lifecycle ──────────────────────────────────────────────────────

    def _save(self):
        data = dict(self._tweaks)
        data["__custom_shapes__"] = self._custom_shapes
        with open(self._conf_file, "w") as f:
            f.write(json.dumps(data, indent=4))

    def on_loaded(self):
        self._start = time.time()
        self._state = 0

    def on_ready(self, agent):
        logging.info("tweak_view 3.0 ready")
        self._agent = agent

    def on_unload(self, ui):
        try:
            for tag, value in self._untweak.items():
                vss, element, key = tag.split(".")
                if element in ui._state._state and hasattr(ui._state._state[element], key):
                    setattr(ui._state._state[element], key, value)
        except Exception as err:
            self._logger.warning("ui unload: %s" % repr(err))

    def on_ui_setup(self, ui):
        self._ui = ui

        self.myFonts = {
            "Small": fonts.Small,
            "BoldSmall": fonts.BoldSmall,
            "Medium": fonts.Medium,
            "Bold": fonts.Bold,
            "BoldBig": fonts.BoldBig,
            "Huge": fonts.Huge
        }

        just_once = True
        for p in [6,7,8,9,10,11,12,14,16,18,20,24,25,28,30,35,42,48,52,54,60,69,72,80,90,100,120]:
            try:
                self.myFonts["Deja %s" % p] = ImageFont.truetype('DejaVuSansMono', p)
                self.myFonts["DejaB %s" % p] = ImageFont.truetype('DejaVuSansMono-Bold', p)
                self.myFonts["DejaO %s" % p] = ImageFont.truetype('DejaVuSansMono-Oblique', p)
            except Exception as e:
                if just_once:
                    logging.warning("Missing some fonts: %s" % repr(e))
                    just_once = False

        self._conf_file = self.options.get("filename", "/etc/pwnagotchi/tweak_view.json")

        try:
            if os.path.isfile(self._conf_file):
                with open(self._conf_file, 'r') as f:
                    saved = json.load(f)

                # Split out custom shapes from tweaks
                self._custom_shapes = saved.pop("__custom_shapes__", {})
                self._tweaks = saved

            self._already_updated = []
            self._logger.info("tweak_view 3.0 ready.")
        except Exception as err:
            self._logger.warning("tweak_view loading failed: %s" % repr(err))

        # Restore custom shapes into the view
        for name, shape in self._custom_shapes.items():
            try:
                self._add_shape_to_view(name, shape["type"], shape["props"])
            except Exception as err:
                self._logger.warning(f"Could not restore shape {name}: {err}")

        try:
            self.update_elements(ui)
        except Exception as err:
            self._logger.warning("ui setup: %s" % repr(err))

    def on_ui_update(self, ui):
        self.update_elements(ui)

    def update_elements(self, ui):
        try:
            state = ui._state._state

            for tag, value in self._tweaks.items():
                try:
                    vss, element, key = tag.split(".")
                except ValueError:
                    continue

                try:
                    if element in state and key in dir(state[element]):
                        if tag not in self._untweak:
                            self._untweak[tag] = getattr(ui._state._state[element], key)

                        if key == "xy":
                            parts = [int(float(x.strip())) for x in str(value).split(",")]
                            elem = ui._state._state[element]

                            # Determine if this element uses 4-point xy (Line/shape) or 2-point
                            current_xy = getattr(elem, 'xy', None)
                            is_4pt = (current_xy is not None and len(current_xy) == 4) or \
                                     isinstance(elem, (Line, CustomLine, CustomRect, CustomEllipse))

                            if is_4pt:
                                while len(parts) < 4:
                                    parts.append(0)
                                # Handle negative values relative to canvas size
                                if parts[0] < 0: parts[0] = ui.width() + parts[0]
                                if parts[1] < 0: parts[1] = ui.height() + parts[1]
                                if parts[2] < 0: parts[2] = ui.width() + parts[2]
                                if parts[3] < 0: parts[3] = ui.height() + parts[3]
                                elem.xy = parts
                            else:
                                if parts[0] < 0: parts[0] = ui.width() + parts[0]
                                if parts[1] < 0: parts[1] = ui.height() + parts[1]
                                elem.xy = parts[:2]

                        elif key in ["font", "text_font", "alt_font", "label_font"]:
                            if value in self.myFonts:
                                setattr(ui._state._state[element], key, self.myFonts[value])
                        elif key in ["bgcolor", "color", "label"]:
                            setattr(ui._state._state[element], key, value)
                        elif key == "label_spacing":
                            ui._state._state[element].label_spacing = int(value)
                        elif key == "max_length":
                            uie = ui._state._state[element]
                            uie.max_length = int(value)
                            uie.wrapper = TextWrapper(width=int(value), replace_whitespace=False) if uie.wrap else None
                        elif key == "width":
                            ui._state._state[element].width = int(value)
                    elif element not in state:
                        self._logger.debug(f"Element {element} not in state")
                except Exception as err:
                    self._logger.warning("tweak failed for key %s: %s" % (tag, repr(err)))

        except Exception as err:
            self._logger.warning("ui update: %s" % repr(err))
