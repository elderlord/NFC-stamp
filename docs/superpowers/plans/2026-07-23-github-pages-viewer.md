# GitHub Pages 도장판 뷰어 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NFC 카드 URL 파라미터(`n`, `id`, `s`)를 읽어 개인화된 도장판을 그리는 정적 GitHub Pages 뷰어를 만든다.

**Architecture:** 빌드 없는 순수 정적 페이지. 파싱·진행률 계산은 DOM을 모르는 순수 함수(`docs/logic.js`)로 분리해 Node 내장 러너로 테스트하고, 렌더링(`docs/app.js`)은 그 함수들을 import해 브라우저 DOM을 구성한다. `docs/index.html`이 진입점이며 GitHub Pages는 `main` 브랜치의 `/docs`를 서빙한다.

**Tech Stack:** 순수 HTML/CSS/JavaScript (ES 모듈), 의존성 없음. 테스트는 Node 내장 `node:test`.

## Global Constraints

- 빌드 도구·프레임워크·npm 의존성 없음. 파일을 그대로 GitHub Pages에 배포.
- JS는 ES 모듈(`<script type="module">`, `import`/`export`).
- 사용자 입력(닉네임 등)은 `textContent`로만 DOM에 삽입. `innerHTML` 사용 금지 (XSS 차단).
- 모바일 우선(세로) 레이아웃. 아이폰 Safari에서 열림.
- 사이트 BASE 주소: `https://elderlord.github.io/nfc-stamp/`
- 전시관 마스터는 `docs/logic.js`의 `EXHIBITS` 객체 한 곳에서만 정의. 테스트용 2곳(`1:우주관`, `2:로봇관`).
- 테스트 실행 환경: Node 18+ (`node --test`).
- 커밋 자주. 각 태스크 끝에서 커밋.

---

## File Structure

| 파일 | 책임 | DOM 접근 |
|---|---|---|
| `docs/logic.js` | `EXHIBITS` 설정, `parseParams`, `computeProgress` (순수 함수) | 없음 |
| `docs/app.js` | `logic.js`를 import해 `#app`에 렌더링 | 있음 |
| `docs/index.html` | 진입점: 뼈대 + 내장 CSS + 모듈 로드 | — |
| `test/logic.test.mjs` | `logic.js` 순수 함수 단위 테스트 | 없음 |

---

## Task 1: 순수 로직 (`logic.js`) — TDD

**Files:**
- Create: `docs/logic.js`
- Test: `test/logic.test.mjs`

**Interfaces:**
- Consumes: 없음 (표준 `URLSearchParams`만 사용)
- Produces:
  - `EXHIBITS: { [id: number]: { name: string } }`
  - `parseParams(search: string) => { n: string, id: string, visited: Set<number> }`
  - `computeProgress(visited: Set<number>, exhibits) => { done: number, total: number, items: Array<{ id: number, name: string, visited: boolean }> }`

- [ ] **Step 1: 실패하는 테스트 작성**

`test/logic.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseParams, computeProgress, EXHIBITS } from "../docs/logic.js";

test("parseParams: 정상 파싱", () => {
  const r = parseParams("?n=철수&id=2026-0001&s=1,2");
  assert.equal(r.n, "철수");
  assert.equal(r.id, "2026-0001");
  assert.deepEqual([...r.visited].sort((a, b) => a - b), [1, 2]);
});

test("parseParams: s 없음 → 빈 visited", () => {
  const r = parseParams("?n=철수&id=2026-0001");
  assert.equal(r.visited.size, 0);
});

test("parseParams: 중복·미지·비숫자 정리", () => {
  const r = parseParams("?s=1,1,99,abc,2");
  assert.deepEqual([...r.visited].sort((a, b) => a - b), [1, 2, 99]);
});

test("parseParams: 닉네임 URL 인코딩 디코드", () => {
  const r = parseParams("?n=%EC%B2%A0%EC%88%98"); // 철수
  assert.equal(r.n, "철수");
});

test("parseParams: 파라미터 전무", () => {
  const r = parseParams("");
  assert.equal(r.n, "");
  assert.equal(r.id, "");
  assert.equal(r.visited.size, 0);
});

test("computeProgress: 1곳 방문", () => {
  const { done, total, items } = computeProgress(new Set([1]), EXHIBITS);
  assert.equal(done, 1);
  assert.equal(total, 2);
  assert.deepEqual(items.map((i) => i.visited), [true, false]);
  assert.deepEqual(items.map((i) => i.name), ["우주관", "로봇관"]);
});

test("computeProgress: 미지 번호는 분자 미포함", () => {
  const { done, total } = computeProgress(new Set([1, 99]), EXHIBITS);
  assert.equal(done, 1);
  assert.equal(total, 2);
});

test("computeProgress: 0곳", () => {
  const { done } = computeProgress(new Set(), EXHIBITS);
  assert.equal(done, 0);
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `node --test`
Expected: FAIL — `Cannot find module '../docs/logic.js'` (아직 없음)

- [ ] **Step 3: 최소 구현 작성**

`docs/logic.js`:

```js
export const EXHIBITS = {
  1: { name: "우주관" },
  2: { name: "로봇관" },
};

export function parseParams(search) {
  const p = new URLSearchParams(search);
  const n = p.get("n") || "";
  const id = p.get("id") || "";
  const rawS = p.get("s") || "";
  const visited = new Set();
  for (const part of rawS.split(",")) {
    const num = Number.parseInt(part.trim(), 10);
    if (Number.isInteger(num)) visited.add(num);
  }
  return { n, id, visited };
}

export function computeProgress(visited, exhibits) {
  const ids = Object.keys(exhibits).map((k) => Number.parseInt(k, 10));
  const items = ids.map((id) => ({
    id,
    name: exhibits[id].name,
    visited: visited.has(id),
  }));
  const done = items.filter((it) => it.visited).length;
  return { done, total: ids.length, items };
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `node --test`
Expected: PASS — 8 tests passing.

- [ ] **Step 5: 커밋**

```bash
git add docs/logic.js test/logic.test.mjs
git commit -m "Add stamp-board viewer logic (parse params, compute progress)"
```

---

## Task 2: 페이지 뼈대 + 렌더링 (`index.html`, `app.js`)

**Files:**
- Create: `docs/index.html`
- Create: `docs/app.js`

**Interfaces:**
- Consumes: `EXHIBITS`, `parseParams`, `computeProgress` from `./logic.js`
- Produces: 브라우저에서 `#app` 안에 렌더링된 화면. (다른 태스크가 코드로 소비하지 않음 — 시각 검증)

렌더링 규칙(스펙 §화면 구조·§에러 처리):
- 파라미터 전무(`n`·`id` 비고 `visited` 0) → 플레이스홀더 안내만.
- 그 외 → 인사 / "N / 총 방문" / 도장판(방문 ⬤ 미방문 ◯) / 방문 목록(0곳이면 안내 문구) / ID 푸터(`id` 있을 때만).
- 모든 텍스트는 `textContent`로 삽입.

- [ ] **Step 1: `docs/app.js` 작성**

```js
import { EXHIBITS, parseParams, computeProgress } from "./logic.js";

function el(tag, opts = {}) {
  const node = document.createElement(tag);
  if (opts.text != null) node.textContent = opts.text;
  if (opts.className) node.className = opts.className;
  return node;
}

export function render(root, state) {
  root.replaceChildren();

  // 파라미터 전무 → 플레이스홀더
  if (!state.n && !state.id && state.visited.size === 0) {
    root.appendChild(
      el("p", {
        className: "placeholder",
        text: "카드를 스마트폰에 대면 나의 도장판이 열립니다",
      })
    );
    return;
  }

  const progress = computeProgress(state.visited, EXHIBITS);

  // 인사
  const greeting = state.n ? `${state.n}님, 환영합니다` : "환영합니다";
  root.appendChild(el("h1", { className: "greeting", text: greeting }));

  // 진행률 텍스트
  root.appendChild(
    el("p", { className: "count", text: `${progress.done} / ${progress.total} 방문` })
  );

  // 도장판
  const board = el("div", { className: "board" });
  for (const item of progress.items) {
    const stamp = el("div", { className: item.visited ? "stamp filled" : "stamp empty" });
    stamp.appendChild(el("span", { className: "mark", text: item.visited ? "⬤" : "◯" }));
    stamp.appendChild(el("span", { className: "label", text: item.name }));
    board.appendChild(stamp);
  }
  root.appendChild(board);

  // 방문 목록
  root.appendChild(el("h2", { className: "list-title", text: "방문한 전시관" }));
  const visitedItems = progress.items.filter((i) => i.visited);
  if (visitedItems.length === 0) {
    root.appendChild(el("p", { className: "empty", text: "아직 방문한 전시관이 없어요" }));
  } else {
    const ul = el("ul", { className: "visited-list" });
    for (const item of visitedItems) ul.appendChild(el("li", { text: item.name }));
    root.appendChild(ul);
  }

  // ID 푸터
  if (state.id) {
    root.appendChild(el("footer", { className: "id", text: `ID: ${state.id}` }));
  }
}

// 브라우저 진입점 (테스트 환경에서는 document가 없으므로 가드)
if (typeof document !== "undefined") {
  const root = document.getElementById("app");
  render(root, parseParams(location.search));
}
```

- [ ] **Step 2: `docs/index.html` 작성**

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>나의 도장판</title>
    <style>
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
        background: #f5f7fa;
        color: #1a1a2e;
        -webkit-text-size-adjust: 100%;
      }
      #app {
        max-width: 480px;
        margin: 0 auto;
        padding: 24px 20px 40px;
        min-height: 100vh;
      }
      .placeholder {
        margin-top: 40vh;
        text-align: center;
        color: #6b7280;
        font-size: 1.05rem;
      }
      .greeting { font-size: 1.6rem; margin: 8px 0 4px; }
      .count { font-size: 1.1rem; color: #3b82f6; font-weight: 600; margin: 0 0 20px; }
      .board { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }
      .stamp {
        display: flex; flex-direction: column; align-items: center; gap: 6px;
        width: 88px; padding: 16px 8px; border-radius: 16px;
        background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      }
      .stamp .mark { font-size: 1.8rem; line-height: 1; }
      .stamp.filled .mark { color: #ef4444; }
      .stamp.empty .mark { color: #d1d5db; }
      .stamp .label { font-size: 0.85rem; color: #374151; }
      .list-title { font-size: 1.1rem; margin: 0 0 8px; }
      .visited-list { margin: 0; padding-left: 20px; line-height: 1.7; }
      .empty { color: #6b7280; margin: 0; }
      .id { margin-top: 32px; font-size: 0.8rem; color: #9ca3af; }
    </style>
  </head>
  <body>
    <main id="app"></main>
    <script type="module" src="app.js"></script>
  </body>
</html>
```

- [ ] **Step 3: 로컬 서버로 시각 검증**

`docs/`를 서빙한다:

```bash
cd docs && python3 -m http.server 8000
```

브라우저(또는 헤드리스 Chromium)로 아래 URL을 열어 결과를 확인한다:

| URL | 기대 화면 |
|---|---|
| `http://localhost:8000/?n=철수&id=2026-0001&s=1` | 인사 "철수님, 환영합니다", "1 / 2 방문", 우주관 ⬤·로봇관 ◯, 방문 목록에 "우주관", 하단 "ID: 2026-0001" |
| `http://localhost:8000/?n=영희&s=1,2` | "영희님, 환영합니다", "2 / 2 방문", 둘 다 ⬤, 목록에 우주관·로봇관, ID 푸터 없음 |
| `http://localhost:8000/?id=2026-0002` | "환영합니다"(닉네임 없음), "0 / 2 방문", 둘 다 ◯, "아직 방문한 전시관이 없어요", "ID: 2026-0002" |
| `http://localhost:8000/` | 플레이스홀더 "카드를 스마트폰에 대면 나의 도장판이 열립니다"만 표시 |
| `http://localhost:8000/?n=%3Cscript%3Ealert(1)%3C/script%3E&s=1` | 인사에 `<script>alert(1)</script>` **문자 그대로** 표시, 경고창 뜨지 않음 (XSS 안전) |

모든 행이 기대대로면 통과.

- [ ] **Step 4: 커밋**

```bash
git add docs/index.html docs/app.js
git commit -m "Add stamp-board viewer page (index.html, render logic)"
```

---

## Task 3: README 갱신 + GitHub Pages 배포 안내

**Files:**
- Modify: `README.md` (로드맵 항목 + 웹 뷰어 섹션 추가)

**Interfaces:**
- Consumes: 없음
- Produces: 없음 (문서)

- [ ] **Step 1: README에 웹 뷰어 섹션 추가**

`README.md`의 "저장소 구조" 섹션 뒤에 아래를 추가한다:

```markdown
## 웹 뷰어 (GitHub Pages)

카드에 굽는 URL이 가리키는 개인화 도장판 페이지.

- 소스: `docs/` (GitHub Pages를 `main` 브랜치 `/docs`로 설정)
- 배포 주소: `https://elderlord.github.io/nfc-stamp/`
- 로컬 확인: `cd docs && python3 -m http.server 8000` 후
  `http://localhost:8000/?n=철수&id=2026-0001&s=1` 열기
- 로직 테스트: `node --test`

### GitHub Pages 켜기 (최초 1회, 병합 후)

저장소 Settings → Pages → Source를 **Deploy from a branch**,
Branch를 **`main` / `/docs`**로 지정. 저장하면 위 주소로 배포된다.
```

- [ ] **Step 2: README 로드맵 항목 갱신**

`README.md`의 로드맵에서 해당 줄을 아래처럼 바꾼다:

```markdown
- [x] GitHub Pages 뷰어 (URL 파라미터 → 개인화 화면)
```

- [ ] **Step 3: 커밋**

```bash
git add README.md
git commit -m "Document GitHub Pages viewer and deployment"
```

---

## 완료 기준

- `node --test` 8개 통과.
- Task 2 §Step 3 시각 검증 표의 모든 행이 기대대로 동작.
- README에 뷰어·배포 안내 반영.
- 세 태스크 각각 커밋됨.

## 이후 작업 (이 계획 범위 밖)

- 완주 축하 화면.
- 발급 스테이션 스크립트 — 이 데이터 계약(`n`/`id`/`s`)대로 카드에 URL을 굽는다.
- 실제 전시관 명단으로 `EXHIBITS` 갱신.
