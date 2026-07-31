// 세특 마킹 도구 로컬 서버 (무의존, Node http). 브라우저 마킹 ↔ 디스크 JSON 다리.
//
// 이 서버는 렌더하지 않는다. 모델을 직접 부르지도, API 키를 쓰지도 않는다.
// 렌더 주체 = 감시자(watch_done.sh) + 구독제 에이전트. 서버는 에이전트가 out/drafts_v3b/ 에
// 써 놓은 초안을 읽어 화면에 넘겨줄 뿐이다.
//
// 쓰기: out/marks/  ·  읽기: out/drafts_v3b/
import http from "node:http";
import { readFile, writeFile, readdir, mkdir, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(__dirname);
const MARKS = path.join(ROOT, "out", "marks");
const DRAFTS = path.join(ROOT, "out", "drafts_v3b");
const VALIDATOR = path.join(__dirname, "validate_draft.py");
const PYTHON = process.env.PYTHON || "python3";
const PORT = Number(process.env.PORT || 7333);
const HAKBUN = /^\d{4,6}$/;                 // 경로 탈출(../) 차단용 화이트리스트

await mkdir(MARKS, { recursive: true });
await mkdir(DRAFTS, { recursive: true });

const send = (res, code, body, type = "application/json") => {
  res.writeHead(code, { "Content-Type": type + "; charset=utf-8", "Cache-Control": "no-store" });
  res.end(body);
};
const json = (res, code, obj) => send(res, code, JSON.stringify(obj, null, 1));
const fail = (res, code, message) => json(res, code, { error: message });
const readBody = (req) => new Promise((resolve, reject) => {
  let d = "", n = 0;
  req.on("data", c => { n += c.length; if (n > 2_000_000) { reject(new Error("body too large")); req.destroy(); return; } d += c; });
  req.on("end", () => resolve(d));
  req.on("error", reject);
});
const serveFile = async (res, file, type) => {
  try { send(res, 200, await readFile(path.join(__dirname, file)), type); }
  catch { send(res, 404, "not found", "text/plain"); }
};
const readJson = async (f) => { try { return JSON.parse(await readFile(f, "utf-8")); } catch { return null; } };

/* ── 검증기 ────────────────────────────────────────────────────────────────
   바이트·종결·금지어·레벨 게이트 판정은 validate_draft.py 하나가 단일 출처다.
   브라우저에서 재구현하지 않는다 — 바이트 상한도 여기서 받아 쓴다(값 자체는 프로젝트의
   draft-rules.json 에서 온다. 스킬·서버·UI 어디에도 숫자를 박지 않는다). */
const runPython = (args) => new Promise((resolve, reject) => {
  const p = spawn(PYTHON, args, { cwd: ROOT });
  let out = "", err = "";
  p.stdout.on("data", d => (out += d));
  p.stderr.on("data", d => (err += d));
  p.on("error", reject);
  p.on("close", code => (code === 0 ? resolve(out) : reject(new Error(err.trim() || `exit ${code}`))));
});
const validate = async (text, level) =>
  JSON.parse(await runPython([VALIDATOR, "--text", String(text ?? ""), ...(level ? ["--level", level] : [])]));
// 검증기가 죽어도 화면은 떠야 한다 — 실패는 null 로 흘리고 UI가 '검증기 사용 불가'를 표시한다.
const validateSoft = async (text, level) => { try { return await validate(text, level); } catch { return null; } };

let _limits = null;                          // {byte_max, byte_short} — 첫 요청에서 한 번만
async function limits() {
  if (_limits) return _limits;
  const r = await validateSoft("확인함");
  if (r) _limits = { byte_max: r.byte_max, byte_short: r.byte_short };
  return _limits;
}

const mtime = async (f) => { try { return (await stat(f)).mtimeMs; } catch { return null; } };

/* 대기열 = pending.py 단일 출처. 화면이 "이 초안이 지금 마킹의 결과인가"를 스스로 계산하면
   감시자와 판정이 갈라진다(그러면 화면은 '초안 나옴'인데 감시자는 계속 다시 그린다).
   폴링이 2.5초라 1초만 캐시해도 파이썬 기동 비용이 사라진다. */
const PENDING = path.join(__dirname, "pending.py");
let _pend = { at: 0, list: [] };
async function pendingList() {
  if (Date.now() - _pend.at < 1000) return _pend.list;
  try {
    const out = await runPython([PENDING]);
    _pend = { at: Date.now(), list: out.split("\n").map(s => s.trim()).filter(Boolean) };
  } catch { _pend = { at: Date.now(), list: _pend.list }; }
  return _pend.list;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const p = url.pathname;
  try {
    if (p === "/" || p === "/mark.html") return serveFile(res, "mark.html", "text/html");
    // review.html 은 인라인 초안 패널 이전 화면이라 스킬에 싣지 않는다(mark.html 주석 참조).
    // 라우트는 남기되, 파일이 없으면 맨 404 대신 **무엇을 쓰면 되는지** 알려 준다.
    if (p === "/review" || p === "/review.html") {
      if (existsSync(path.join(__dirname, "review.html")))
        return serveFile(res, "review.html", "text/html");
      return send(res, 404,
        "<meta charset=utf-8><h2>전체 훑기 화면(review.html)은 이 스킬에 포함되지 않습니다</h2>" +
        "<p>마킹한 학생의 사람 Tier-2 검수는 <a href='/'>마킹 화면</a>의 되짚기 패널 + [확정]/[다시]로 합니다.</p>" +
        "<p>위임(하이라이트 0) 학생의 옆줄 대조표는 <code>make_review_table.py</code> 로 만드십시오.</p>",
        "text/html");
    }
    if (p === "/students.json") return serveFile(res, "students.json", "application/json");

    // 화면이 알아야 할 서버 설정 — 바이트 상한을 UI가 하드코딩하지 않게 내려준다.
    if (p === "/config") return json(res, 200, { limits: await limits(), watch_cmd: "bash tool/watch_done.sh" });

    if (p === "/context") {
      const cp = path.join(MARKS, "_context.json");
      if (req.method === "POST") { await writeFile(cp, await readBody(req)); return json(res, 200, { ok: true }); }
      return send(res, 200, existsSync(cp) ? await readFile(cp) : JSON.stringify({ context: "" }));
    }

    if (p === "/save" && req.method === "POST") {
      const obj = JSON.parse(await readBody(req));
      if (!HAKBUN.test(String(obj.hakbun ?? ""))) return fail(res, 400, "학번 형식 오류");
      await writeFile(path.join(MARKS, `${obj.hakbun}.json`), JSON.stringify(obj, null, 1));
      return json(res, 200, { ok: true, hakbun: obj.hakbun, done: !!obj.done, approved: !!obj.approved });
    }

    if (p === "/marks") {
      const files = (await readdir(MARKS)).filter(f => f.endsWith(".json") && !f.startsWith("_"));
      const out = {};
      for (const f of files) {
        const m = await readJson(path.join(MARKS, f));
        if (m) out[f.replace(".json", "")] = m;
      }
      return json(res, 200, out);
    }

    if (p === "/drafts") {
      const files = existsSync(DRAFTS) ? (await readdir(DRAFTS)).filter(f => f.endsWith(".json")) : [];
      const out = {};
      for (const f of files) {
        const d = await readJson(path.join(DRAFTS, f));
        if (d) out[f.replace(".json", "")] = d;
      }
      return json(res, 200, out);
    }

    // 배지용 경량 색인 — 누구에게 초안이 있는지 + 지금 대기열은 누구인지. 본문은 싣지 않는다.
    if (p === "/drafts-index") {
      const files = existsSync(DRAFTS) ? (await readdir(DRAFTS)).filter(f => f.endsWith(".json")) : [];
      const drafts = {};
      for (const f of files) drafts[f.replace(".json", "")] = await mtime(path.join(DRAFTS, f));
      return json(res, 200, { drafts, pending: await pendingList() });
    }

    /* 초안 1명 조회 — 본문 + 검증 결과 + 상한. 초안이 마킹보다 오래됐으면 stale 로 알린다
       (지금 마킹의 결과가 아니라는 뜻 — 감시자가 다시 그릴 대상이다). */
    const m1 = p.match(/^\/draft\/(.+)$/);
    if (m1) {
      const hk = decodeURIComponent(m1[1]);
      if (!HAKBUN.test(hk)) return fail(res, 400, "학번 형식 오류");
      const df = path.join(DRAFTS, `${hk}.json`);
      const mf = path.join(MARKS, `${hk}.json`);
      const d = await readJson(df);
      if (!d?.setuk) return fail(res, 404, "저장된 초안이 없습니다.");
      const mark = await readJson(mf);
      return json(res, 200, {
        hakbun: hk,
        // unmet — 교사 기타 요구사항을 못 지켰을 때의 사유. 화면이 배너로 띄운다(notes 는 안 띄운다).
        draft: { setuk: d.setuk, ledger: Array.isArray(d.ledger) ? d.ledger : [],
                 name: d.name ?? "", competency: d.competency ?? "", notes: d.notes ?? "",
                 unmet: typeof d.unmet === "string" ? d.unmet.trim() : "" },
        // 레벨은 초안에 없으면 마킹에서 끌어온다(초안은 레벨 도입 전 산출물일 수 있다).
        validation: await validateSoft(d.setuk, d.level || mark?.level || ""),
        limits: await limits(),
        // 대기열에 있다 = 이 초안은 지금 마킹의 결과가 아니다. 판정은 pending.py 한 곳에서만.
        stale: (await pendingList()).includes(hk),
        rendered_at: await mtime(df),
      });
    }

    send(res, 404, "not found", "text/plain");
  } catch (e) {
    json(res, 500, { error: String(e) });
  }
});

server.listen(PORT, () => {
  const hasReview = existsSync(path.join(__dirname, "review.html"));
  console.log(`세특 마킹 도구: http://localhost:${PORT}/${hasReview ? "  (리뷰: /review)" : ""}`);
  console.log(`  쓰기: out/marks/ · 읽기: out/drafts_v3b/`);
  console.log(`  렌더: 감시자 + 에이전트. 별도 터미널에서  bash tool/watch_done.sh`);
  limits();
});
