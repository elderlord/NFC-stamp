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
