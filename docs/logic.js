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
    const token = part.trim();
    // 신뢰할 수 없는 URL 입력: 순수 정수 토큰만 허용 (1.5, -3, 2abc 등 배제)
    if (/^\d+$/.test(token)) visited.add(Number(token));
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
