"""Diagnostic de l'environnement : à lancer avec `make diagnose` et à copier en entier
quand quelque chose ne marche pas. N'utilise que la bibliothèque standard pour
l'environnement, afin de tourner même si les dépendances sont cassées.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "bin" / "python"
VENV_DBT = ROOT / ".venv" / "bin" / "dbt"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return "introuvable"
    except subprocess.TimeoutExpired:
        return f"bloqué après {timeout}s"
    code = p.returncode
    status = "OK" if code == 0 else (f"TUÉ par le système (signal {-code})" if code < 0 else f"code {code}")
    out = (p.stdout + p.stderr).strip().splitlines()
    tail = " | ".join(out[-4:])[:400]
    return f"{status} — {tail}" if tail else status


def section(title: str) -> None:
    print(f"\n=== {title} ===")


section("Système")
print("macOS :", platform.mac_ver()[0] or "n/a", "| arch :", platform.machine())
if sys.platform == "darwin":
    print("sw_vers :", run(["sw_vers", "-productVersion"]))
    print("RAM (octets) :", run(["sysctl", "-n", "hw.memsize"]))

section("Python utilisé pour ce diagnostic")
print("exécutable :", sys.executable, "| version :", platform.python_version())
print("VIRTUAL_ENV :", os.environ.get("VIRTUAL_ENV") or "aucun (venv non activé)")
print("CONDA_DEFAULT_ENV :", os.environ.get("CONDA_DEFAULT_ENV") or "aucun")
print("python3 dans le PATH :", shutil.which("python3"))
print("dbt dans le PATH :", shutil.which("dbt"))

section("Environnement du projet (.venv)")
if VENV_PY.exists():
    print(".venv/bin/python :", run([str(VENV_PY), "--version"]))
    for mod in ["duckdb", "pyarrow", "pandas", "dbt.version", "streamlit"]:
        code = f"import {mod} as m; print(getattr(m, '__version__', None) or getattr(m, 'installed', '?'))"
        print(f"  import {mod} :", run([str(VENV_PY), "-c", code]))
    print("  duckdb requête test :", run([str(VENV_PY), "-c", "import duckdb; print(duckdb.sql('select 42').fetchone())"]))
    print(".venv/bin/dbt --version :", run([str(VENV_DBT), "--version"]))
    print("dbt debug :", run([str(VENV_DBT), "debug", "--profiles-dir", "."], cwd=ROOT / "transform", timeout=180))
else:
    print("absent — crée-le avec : python3 -m venv .venv && make install")

section("API INStaD (NADA)")
try:
    sys.path.insert(0, str(ROOT))
    from ingestion import nada
    from ingestion.common import HttpClient, load_config

    site_root = load_config()["nada"]["site_root"].rstrip("/")
    client = HttpClient(retries=1, timeout=30)
    for url, verdict in nada.probe(client, site_root):
        print(f"{verdict:<40} {url}")
    try:
        r = client.session.get(f"{site_root}/index.php/catalog", timeout=30)
        print(f"page catalogue HTML : HTTP {r.status_code}, {len(r.text)} caractères")
        for marker in ["api/", "NADA", "nada_version", "export"]:
            idx = r.text.find(marker)
            if idx >= 0:
                print(f"  repère « {marker} » : …{r.text[max(0, idx - 60): idx + 80]!r}…")
    except Exception as err:  # noqa: BLE001
        print("page catalogue HTML : échec —", err)
except Exception as err:  # noqa: BLE001
    print("test impossible (dépendances absentes de ce Python ?) :", err)

print("\nCopie tout ce qui précède dans la conversation.")
