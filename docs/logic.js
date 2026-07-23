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
