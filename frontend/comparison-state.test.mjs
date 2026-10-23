import test from "node:test";
import assert from "node:assert/strict";
import { loadComparisonPhoto } from "./src/components/comparison-state.ts";

test("changing comparison B rejects its old response while A and failed B keep their own identity", async () => {
  const pending = new Map();
  const load = id => new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
  const sides = {};
  const a = loadComparisonPhoto("photo-a", load, value => { sides.A = value; });
  const oldB = loadComparisonPhoto("photo-b-old", load, value => { sides.B = value; });
  oldB();
  const b = loadComparisonPhoto("photo-b-new", load, value => { sides.B = value; });
  pending.get("photo-b-new").resolve({ id: "photo-b-new", path: "B/new.jpg", width: 640 });
  pending.get("photo-a").resolve({ id: "photo-a", path: "A/original.jpg", width: 320 });
  await new Promise(resolve => setImmediate(resolve));
  pending.get("photo-b-old").resolve({ id: "photo-b-old", path: "B/old.jpg", width: 120 });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(sides.A.detail.path, "A/original.jpg");
  assert.equal(sides.B.id, "photo-b-new");
  assert.equal(sides.B.detail.width, 640);
  b();
  const failed = loadComparisonPhoto("photo-missing", load, value => { sides.B = value; });
  pending.get("photo-missing").reject(new Error("Photo not found"));
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(sides.B, { id: "photo-missing", error: "Photo not found" });
  assert.equal(sides.A.detail.id, "photo-a");
  a(); failed();
});
