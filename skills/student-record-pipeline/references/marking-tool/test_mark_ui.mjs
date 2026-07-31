/* mark.html 인라인 JS를 최소 DOM 스텁 위에서 돌려 상태 전이를 검증한다.
   확인 대상: 배지 4상태 · 확정 자동 해제(유령 상태 방지) · 반려 누적 · 저장 페이로드. */
import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync(new URL('./mark.html', import.meta.url), 'utf8');
const js = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));

const el = () => {
  const e = {
    innerHTML: '', textContent: '', value: '', checked: false, hidden: false, title: '', className: '',
    dataset: {}, style: {},
    classList: { _s: new Set(), add(c){this._s.add(c)}, remove(c){this._s.delete(c)},
                 toggle(c,v){v?this._s.add(c):this._s.delete(c)}, contains(c){return this._s.has(c)} },
    addEventListener(t, fn){ (this._h ||= {})[t] = fn },
    appendChild(){}, querySelector(){ return el() }, querySelectorAll(){ return [] },
    contains(){ return true }, scrollIntoView(){}, closest(){ return null }, remove(){},
  };
  return e;
};
const NODES = {};
const node = (sel) => (NODES[sel] ||= el());

const SAVES = [];
const ctx = {
  console,
  document: { querySelector: node, querySelectorAll: () => [], createElement: el, body: el() },
  window: { getSelection: () => null, scrollTo(){} },
  setInterval: () => 0, clearTimeout, setTimeout,
  Date, JSON, Set, Map, Object, Array, String, Math, Boolean,
  fetch: async (url, opt) => {
    if (opt?.method === 'POST' && String(url) === '/save') { SAVES.push(JSON.parse(opt.body)); return { ok: true, json: async () => ({ ok: true }) }; }
    if (String(url) === '/config') return { ok: true, json: async () => ({ limits: { byte_max: 715 }, watch_cmd: 'x' }) };
    if (String(url) === '/marks') return { ok: true, json: async () => ({}) };
    if (String(url) === '/drafts-index') return { ok: true, json: async () => ({ drafts: {}, pending: [] }) };
    if (String(url) === '/context') return { ok: true, json: async () => ({ context: 'ctx' }) };
    if (String(url) === '/students.json') return { ok: true, json: async () => ({
      classes: ['1-4'],
      sections: [{ key: 'a', label: 'A칸', tag: 'A' }, { key: 'b', label: 'B칸', tag: 'B' }, { key: 'c', label: 'C칸', tag: 'C' }],
      students: [{ order: '1', cls: '1-4', hakbun: '10401', name: '홍길동', status: '확정',
                   a: '가나다라마', b: '바사아자차', c: '카타파하거' }],
    }) };
    return { ok: false, status: 404, json: async () => ({}) };
  },
};
vm.createContext(ctx);
vm.runInContext(js, ctx);
await new Promise(r => setTimeout(r, 30));   // init() 완료 대기

const G = (n) => vm.runInContext(n, ctx);
const S = () => G('STATE')['10401'];
const badge = () => node('#bd-10401').textContent;
let fails = 0;
const t = (name, cond) => { console.log(`${cond ? '  ✅' : '  ❌'} ${name}`); if (!cond) fails++; };

console.log('\n[섹션 일반화] students.json 의 sections 3칸을 그대로 읽는가');
t('SECTIONS 3칸 (p3/p4 하드코딩 아님)', G('SECTIONS').length === 3 && G('SECTIONS')[2].key === 'c');
t('c칸 원문 박스 생성됨', !!NODES['#src-10401-c']);
t('secTag("c") = "C"', G('secTag("c")') === 'C');

console.log('\n[위임] 하이라이트 0개 = AI가 원문에서 직접 고름. 개수로만 갈린다');
t('하이라이트 0개 → 위임', G('isDelegated("10401")') === true);
G('STATE["10401"].done = true; paintStatus("10401")');
t('배지에 위임 표시', badge().includes('위임'));
G('STATE["10401"].highlights.push({section:"a",text:"가나다",why:""}); paintStatus("10401")');
t(`'왜'가 비어도 하이라이트가 있으면 위임 아님(부분 마킹=하드바인딩)`, G('isDelegated("10401")') === false);
t('배지에서 위임 표시 사라짐', !badge().includes('위임'));
G('STATE["10401"].highlights = []; STATE["10401"].done = false; paintStatus("10401")');

console.log('\n[배지 전이] 마킹중 → 굽는 중 → 초안 나옴 → 확정');
t('초기 = 마킹중', badge() === '마킹중');
G('STATE["10401"].highlights.push({section:"a",text:"가나다",why:"핵심"})');
G('save("10401", true)');
G('STATE["10401"].done = true; paintStatus("10401")');
t('요청했는데 초안 없음 = 굽는 중', badge() === '굽는 중');
// 초안 도착 = 파일이 생기고(DIDX) 서버 대기열에서 빠진 상태(PEND). 둘 다 서버가 알려준다.
G('DIDX["10401"] = 123; PEND.delete("10401"); paintStatus("10401")');
t('초안 도착 = 초안 나옴', badge() === '초안 나옴');
G('PEND.add("10401"); paintStatus("10401")');
t('초안이 있어도 대기열에 있으면 굽는 중(다시 그려질 것)', badge() === '굽는 중');
G('PEND.delete("10401"); paintStatus("10401")');
G('setApproved("10401", true)');
// 배지 문자열에서 이모지를 뺐다(2026-07-31 UI 재설계). 이모지는 OS·폰트마다 폭이 달라
// 줄이 흔들리고, 상태색을 디자인 토큰에 맞출 수 없으며, 스크린리더가 그림 이름을 읽는다.
// 상태 구분은 이제 배지 클래스(b-ok/b-hold/…)와 레일 점이 색으로 한다.
t('확정 = 확정', badge() === '확정');
t('approved=true 저장됨', S().approved === true && !!S().approved_at);

console.log('\n[확정 자동 해제] 확정 후 재료가 바뀌면 유령 상태가 남지 않는가');
G('STATE["10401"].highlights[0].why = "다른 이유"; save("10401", true)');
t('왜 수정 → 확정 해제', S().approved === false && S().approved_at === null);
t('배지도 되돌아감 — 재료가 바뀌었으니 다시 굽는다', badge() === '굽는 중');
G('setApproved("10401", true)');
G('STATE["10401"].level = "상"; save("10401", true)');
t('레벨 변경 → 확정 해제', S().approved === false);
G('setApproved("10401", true)');
G('STATE["10401"].competency = "새 역량"; save("10401", true)');
t('역량 변경 → 확정 해제', S().approved === false);
G('setApproved("10401", true)');
G('STATE["10401"].extra = "짧게 써줘"; save("10401", true)');
t('기타 요구사항 변경 → 확정 해제(재료다)', S().approved === false);
t('기타 요구사항 변경 → 대기열 진입', G('PEND.has("10401")') === true);
G('setApproved("10401", true)');
const atAfterApprove = S().material_at;
G('save("10401", true)');
t('재료 변화 없는 저장은 확정 유지', S().approved === true);

console.log('\n[material_at] 감시자가 "다시 그릴까"를 판정하는 기준 — 재료가 바뀔 때만 찍힌다');
t('확정은 material_at 을 건드리지 않는다(확정본 덮어쓰기 방지)', S().material_at === atAfterApprove);
G('setApproved("10401", false)');
t('확정 취소도 material_at 을 건드리지 않는다', S().material_at === atAfterApprove);
await new Promise(r => setTimeout(r, 3));   // ISO 스탬프가 ms 해상도라 같은 밀리초면 문자열이 같다
G('STATE["10401"].highlights.push({section:"b",text:"바사아",why:""}); save("10401", true)');
t('하이라이트 추가 → material_at 갱신', S().material_at !== atAfterApprove);
t('재료 변경 시 대기열에 즉시 반영', G('PEND.has("10401")') === true);

console.log('\n[반려] 사유 누적 · 확정 해제 · 초안 캐시 폐기');
G('setApproved("10401", true)');
const atBeforeReject = S().material_at;
await new Promise(r => setTimeout(r, 3));   // ISO 스탬프 ms 해상도 — 같은 밀리초면 문자열이 같다
G('DIDX["10401"] = 123; PEND.delete("10401")');
G('reject("10401", "통설을 지어냄")');
t('반려는 재료가 그대로여도 material_at 을 찍는다(다시 그리라는 명시 요청)', S().material_at !== atBeforeReject);
t('반려 즉시 대기열 진입', G('PEND.has("10401")') === true);
t('rejects 1건 · 사유 보존', S().rejects.length === 1 && S().rejects[0].reason === '통설을 지어냄');
t('반려 시 확정 해제', S().approved === false);
t('반려 시 요청 상태 유지(done)', S().done === true);
t('초안 캐시 폐기 → 굽는 중', badge() === '굽는 중');
G('reject("10401", "")');
t('사유 없는 반려도 누적(지우지 않음)', S().rejects.length === 2 && S().rejects[1].reason === '');

console.log('\n[반려 스냅샷] 물린 본문이 다음 렌더에 덮어써져도 남는가');
G('DRAFT["10401"] = {draft:{setuk:"물린 문장 A"}}');
G('reject("10401", "A 가 이상함")');
t('반려 시 지금 초안 본문을 함께 붙잡는다', S().rejects.at(-1).setuk === '물린 문장 A');
G('DRAFT["10401"] = {draft:{setuk:"물린 문장 B"}}');
G('reject("10401", "B 도 이상함")');
t('2회 이상 물려도 각 회차 본문이 따로 남는다',
  S().rejects.at(-2).setuk === '물린 문장 A' && S().rejects.at(-1).setuk === '물린 문장 B');
G('delete DRAFT["10401"]');
G('reject("10401", "초안 없이 물림")');
t('초안 캐시가 없으면 빈 스냅샷(터지지 않음)', S().rejects.at(-1).setuk === '');

console.log('\n[판정 보류] 안 읽은 것과 읽고 못 정한 것을 가른다');
G('STATE["10401"].rejects = []; STATE["10401"].done = true; DIDX["10401"] = 999; PEND.delete("10401")');
G('setHeld("10401", true)');
t('보류 배지로 갈린다', badge() === '보류');
t('보류는 대기열에서 빠진다(재렌더 낭비 방지)', G('PEND.has("10401")') === false);
t('held/held_at 저장됨', S().held === true && !!S().held_at);
const atBeforeHold = S().material_at;
t('보류는 재료가 아니다 — material_at 을 안 건드린다', S().material_at === atBeforeHold);
G('setApproved("10401", true)');
t('확정하면 보류가 풀린다', S().held === false && S().held_at === null);
G('setApproved("10401", false); setHeld("10401", true)');
G('reject("10401", "역시 아님")');
t('[다시] 누르면 보류가 풀린다(판정을 한 것)', S().held === false);
G('setHeld("10401", true)');
await new Promise(r => setTimeout(r, 3));
G('STATE["10401"].competency = "또 다른 역량"; save("10401", true)');
t('재료가 바뀌면 보류가 풀린다 — 그 초안은 이미 옛것이다', S().held === false);

console.log('\n[근거 라벨] 원문 근거가 없는 서술이 원문에서 온 것처럼 보이면 안 된다(계약서 §0-3)');
const origin = (span, dele, hi) => G(`ledgerOrigin(${JSON.stringify(span)}, ${!!dele}, ${hi ?? -1})`);
t('기타 요구사항 → 원문 근거 없음으로 표시',
  origin('기타 요구사항: 발표도 적극적이었음').tag === '교사 요구사항(원문 근거 없음)');
t('접두사는 벗겨서 보여준다', origin('기타 요구사항: 발표도 적극적이었음').body === '발표도 적극적이었음');
t('위임 학생이어도 기타 요구사항이 우선 — 원문에서 온 게 아니다',
  origin('기타 요구사항: 발표도 적극적이었음', true).tag === '교사 요구사항(원문 근거 없음)');
t('위임의 나머지 근거는 원문(AI 선택)', origin('김춘추: 한강 쪽으로', true).tag === '원문(AI 선택)');
t('교사 지정(역량·왜)은 그대로 구분', origin('교사 지정 — 역량: 개인 서사').tag === '교사 지정');
t('되짚기 성공한 근거는 하이라이트', origin('[1](p3) "가나다"', false, 0).tag === '하이라이트');

console.log('\n[저장 페이로드] 디스크에 실제로 나가는 모양');
const last = SAVES[SAVES.length - 1];
t('approved/rejects/level 포함', 'approved' in last && Array.isArray(last.rejects) && 'level' in last);
t('기타 요구사항(extra) 포함', last.extra === '짧게 써줘');
t('원문(sections)도 함께 저장', last.a === '가나다라마' && last.c === '카타파하거');
t('내부 필드 누출 없음', !('_sig' in last));

console.log(fails ? `\n실패 ${fails}건` : '\n전부 통과');
process.exit(fails ? 1 : 0);
