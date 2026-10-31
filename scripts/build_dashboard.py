"""Refresh the analysis data embedded in outputs/dashboard/RIFDAN_Dashboard.html.

The dashboard is a self-contained HTML file holding the interface, the Plotly library and the data.
This script replaces only the embedded data block with the current contents of outputs/dashboard_data.json
and leaves the rest of the file unchanged. The file is rewritten only when the data actually differs.

Usage (from the project root): python scripts/build_dashboard.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "outputs" / "dashboard" / "RIFDAN_Dashboard.html"
DATA = ROOT / "outputs" / "dashboard_data.json"

html = HTML.read_text(encoding="utf-8")
data_text = DATA.read_text(encoding="utf-8")
assert "UserID" not in data_text, "dashboard_data.json must not contain individual identifiers"
json.loads(data_text)

marker = "const D="
start = html.index(marker, html.index("</main></div>")) + len(marker)
_, length = json.JSONDecoder().raw_decode(html[start:])
block = data_text.replace("</", "<\\/")  # keep the JSON safe inside a <script> element

if html[start:start + length] == block:
    print("dashboard data already up to date:", HTML.relative_to(ROOT))
else:
    HTML.write_text(html[:start] + block + html[start + length:], encoding="utf-8", newline="\n")
    print("dashboard data refreshed:", HTML.relative_to(ROOT))
