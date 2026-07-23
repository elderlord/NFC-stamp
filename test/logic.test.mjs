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

test("parseParams: 소수·음수·혼합 토큰 배제 (순수 정수만)", () => {
  const r = parseParams("?s=1.5,-3,2abc,2");
  assert.deepEqual([...r.visited].sort((a, b) => a - b), [2]);
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
