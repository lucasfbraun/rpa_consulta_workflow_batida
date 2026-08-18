from __future__ import annotations

import json
import re
import shutil
import socket
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return cleaned[:70] or "etapa"


@dataclass
class ExecutionReporter:
    root: Path | None
    command: str
    keep_runs: int = 1
    run_id: str | None = None
    run_dir: Path | None = None
    data: dict = field(default_factory=dict)
    step_number: int = 0

    @classmethod
    def from_settings(cls, settings: Settings, command: str) -> "ExecutionReporter":
        return cls(
            settings.monitor_output_dir if settings.monitor_enabled else None,
            command,
            settings.monitor_keep_runs,
        )

    @property
    def enabled(self) -> bool:
        return self.root is not None

    def start(self) -> None:
        if self.root is None:
            return
        self.run_id = str(uuid.uuid4())
        self.run_dir = self.root / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.data = {
            "id": self.run_id,
            "command": self.command,
            "machine": socket.gethostname(),
            "status": "running",
            "started_at": _now(),
            "finished_at": None,
            "error": None,
            "steps": [],
        }
        self._save()
        print(f"Monitoramento local: execução {self.run_id}")

    def step(
        self,
        name: str,
        *,
        status: str = "success",
        message: str | None = None,
        screenshot: bytes | None = None,
    ) -> None:
        if self.run_dir is None:
            return
        self.step_number += 1
        screenshot_path = None
        if screenshot:
            filename = f"{self.step_number:03d}-{_safe_name(name)}.png"
            (self.run_dir / filename).write_bytes(screenshot)
            screenshot_path = f"runs/{self.run_id}/{filename}"
        self.data["steps"].append(
            {
                "number": self.step_number,
                "name": name,
                "status": status,
                "message": message,
                "occurred_at": _now(),
                "screenshot": screenshot_path,
            }
        )
        self._save()

    def capture(
        self,
        page,
        name: str,
        *,
        status: str = "success",
        message: str | None = None,
    ) -> None:
        screenshot = None
        try:
            screenshot = page.screenshot(type="png", full_page=True)
        except Exception as exc:  # O relatório nunca deve derrubar o RPA.
            message = (
                f"{message or ''} Screenshot indisponível: {exc.__class__.__name__}"
            ).strip()
        self.step(name, status=status, message=message, screenshot=screenshot)

    def finish(self, status: str, error: str | None = None) -> None:
        if not self.data:
            return
        self.data.update(status=status, error=error, finished_at=_now())
        self._save()
        if self.root:
            print(f"Relatório HTML: {(self.root / 'index.html').resolve()}")

    def _save(self) -> None:
        if self.run_dir is None or self.root is None:
            return
        (self.run_dir / "run.json").write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            self._prune_old_runs()
            rebuild_report(self.root)
        except OSError as exc:
            print(f"Aviso: relatório indisponível ({exc}).", file=sys.stderr)

    def _prune_old_runs(self) -> None:
        if self.root is None:
            return
        runs_root = (self.root / "runs").resolve()
        candidates: list[tuple[str, Path]] = []
        for run_file in runs_root.glob("*/run.json"):
            try:
                data = json.loads(run_file.read_text(encoding="utf-8"))
                candidates.append((data.get("started_at", ""), run_file.parent))
            except (OSError, json.JSONDecodeError):
                continue
        candidates.sort(key=lambda item: item[0], reverse=True)
        for _, directory in candidates[self.keep_runs :]:
            resolved = directory.resolve()
            if resolved.parent == runs_root:
                shutil.rmtree(resolved)


def rebuild_report(root: Path) -> Path:
    runs = []
    for path in (root / "runs").glob("*/run.json"):
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    runs.sort(key=lambda item: item.get("started_at", ""), reverse=True)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / "index.html"
    destination.write_text(_render_html(runs), encoding="utf-8")
    return destination


def _render_html(runs: list[dict]) -> str:
    payload = json.dumps(runs, ensure_ascii=False).replace("</", "<\\/")
    return _HTML.replace("__RPA_DATA__", payload)


_HTML = r'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor local do RPA</title><style>
:root{--bg:#07110f;--panel:#0e1d19;--panel2:#142720;--line:#28473d;--text:#eef9f4;--muted:#91aaa1;--green:#4de2a2;--red:#ff6b6b;--yellow:#f7c95c}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#12352b,var(--bg) 34rem);color:var(--text);font:15px/1.5 system-ui,sans-serif}header,main{max-width:1450px;margin:auto;padding:30px}header{display:flex;justify-content:space-between;align-items:end}h1{font-size:clamp(30px,5vw,52px);margin:4px 0;letter-spacing:-.04em}.eyebrow{color:var(--green);font-size:12px;font-weight:800;letter-spacing:.16em}.muted,.meta{color:var(--muted)}
.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}.summary article,.run,.card{background:var(--panel);border:1px solid var(--line);border-radius:14px}.summary article{padding:17px}.summary span{display:block;color:var(--muted);font-size:11px;text-transform:uppercase}.summary strong{font-size:28px}.layout{display:grid;grid-template-columns:minmax(300px,390px) 1fr;border:1px solid var(--line);border-radius:18px;overflow:hidden;min-height:620px}aside{padding:18px;border-right:1px solid var(--line)}button{color:inherit;font:inherit;cursor:pointer}.run{display:block;width:100%;padding:13px;margin:8px 0;text-align:left}.run.active{border-color:var(--green);background:var(--panel2)}.row{display:flex;justify-content:space-between;gap:12px}.meta{font-size:12px;margin-top:5px}.badge{padding:3px 8px;border-radius:99px;font-size:10px;text-transform:uppercase}.completed,.success{color:var(--green);background:#123c2e}.failed{color:var(--red);background:#431e20}.running,.info{color:var(--yellow);background:#40351b}
.detail{padding:32px;min-width:0}.head{border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:22px}.step{display:grid;grid-template-columns:24px 1fr;gap:12px;padding-bottom:22px}.dot{width:17px;height:17px;border-radius:50%;background:var(--green);margin-top:4px}.step.failed .dot{background:var(--red)}.card{padding:14px;min-width:0}.shot{display:block;margin-top:12px;padding:0;border:1px solid var(--line);border-radius:9px;overflow:hidden;background:#000}.shot img{display:block;width:100%;max-height:360px;object-fit:cover;object-position:top}dialog{max-width:96vw;border:1px solid var(--line);padding:0;background:#000}dialog::backdrop{background:#000d}dialog img{display:block;max-width:94vw;max-height:94vh}@media(max-width:800px){.summary{grid-template-columns:1fr 1fr}.layout{grid-template-columns:1fr}aside{border-right:0;border-bottom:1px solid var(--line)}header,main{padding:18px}}
</style></head><body><header><div><p class="eyebrow">PONTO → ERP</p><h1>Monitor de execuções</h1><p class="muted">Atualize a página durante o RPA para acompanhar novas etapas.</p></div><div id="updated"></div></header><main><section class="summary"><article><span>Execuções</span><strong id="total">0</strong></article><article><span>Concluídas</span><strong id="completed">0</strong></article><article><span>Falhas</span><strong id="failed">0</strong></article><article><span>Em andamento</span><strong id="running">0</strong></article></section><section class="layout"><aside><h2>Histórico</h2><div id="runs"></div></aside><section class="detail" id="detail"><p class="muted">Selecione uma execução.</p></section></section></main><dialog id="viewer"><img id="large" alt="Screenshot ampliado"></dialog>
<script>const DATA=__RPA_DATA__;let selected=DATA[0]?.id;const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const fmt=v=>v?new Date(v).toLocaleString('pt-BR'):'—';const label=v=>({running:'Em andamento',completed:'Concluída',failed:'Falhou',success:'Sucesso',info:'Info'}[v]||v);function draw(){total.textContent=DATA.length;completed.textContent=DATA.filter(x=>x.status==='completed').length;failed.textContent=DATA.filter(x=>x.status==='failed').length;running.textContent=DATA.filter(x=>x.status==='running').length;updated.textContent='Gerado '+new Date().toLocaleTimeString('pt-BR');runs.innerHTML=DATA.map(r=>`<button class="run ${r.id===selected?'active':''}" data-id="${r.id}"><div class="row"><strong>${esc(r.command)}</strong><span class="badge ${r.status}">${label(r.status)}</span></div><div class="meta">${esc(r.machine)} · ${fmt(r.started_at)}</div><div class="meta">${r.steps.length} etapas · ${r.steps.filter(s=>s.screenshot).length} imagens</div></button>`).join('')||'<p class="muted">Nenhuma execução.</p>';document.querySelectorAll('.run').forEach(b=>b.onclick=()=>{selected=b.dataset.id;draw()});const r=DATA.find(x=>x.id===selected);if(!r)return;detail.innerHTML=`<div class="head"><p class="eyebrow">${esc(r.id)}</p><div class="row"><h2>${esc(r.command)}</h2><span class="badge ${r.status}">${label(r.status)}</span></div><p class="muted">${esc(r.machine)} · ${fmt(r.started_at)}</p>${r.error?`<p>${esc(r.error)}</p>`:''}</div>${r.steps.map(s=>`<article class="step ${s.status}"><span class="dot"></span><div class="card"><div class="row"><strong>${String(s.number).padStart(2,'0')} · ${esc(s.name)}</strong><time>${fmt(s.occurred_at)}</time></div>${s.message?`<p class="muted">${esc(s.message)}</p>`:''}${s.screenshot?`<button class="shot" data-src="${s.screenshot}"><img loading="lazy" src="${s.screenshot}" alt="${esc(s.name)}"></button>`:''}</div></article>`).join('')||'<p class="muted">Aguardando etapas…</p>'}`;document.querySelectorAll('.shot').forEach(b=>b.onclick=()=>{large.src=b.dataset.src;viewer.showModal()})}viewer.onclick=e=>{if(e.target===viewer)viewer.close()};draw();</script></body></html>'''
