import { describe, expect, it } from "vitest";
import parity from "../data/parity.json";
import { AuditChain, canonical, firstBroken } from "./audit";
import type { AuditRecord } from "./audit";
import { sha256 } from "./sha256";

describe("sha256", () => {
  // Reference digests produced by Python's hashlib.
  const known: Array<[string, string]> = [
    ["", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    ["abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"],
    ["café ✓ 🌍", "4f378723b813249f54a996da694576431cafefb05aa9508752f89b7352a94661"],
    ["x".repeat(56), "04c26261370ee7541549d16dee320c723e3fd14671e66a099afe0a377c16888e"],
    ["x".repeat(1000), "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"],
  ];
  it("matches Python's hashlib", () => {
    for (const [text, digest] of known) expect(sha256(text)).toBe(digest);
  });
});

describe("canonical JSON", () => {
  it("sorts keys and escapes non-ASCII like Python", () => {
    expect(canonical({ b: 1, a: "é" })).toBe('{"a":"\\u00e9","b":1}');
  });
  it("refuses decimals", () => {
    expect(() => canonical({ score: 1.5 })).toThrow();
  });
});

describe("the chain", () => {
  it("produces the same hashes as the Python log", () => {
    const chain = new AuditChain();
    parity.audit.records.forEach((record, i) => {
      expect(chain.append(record as AuditRecord).hash).toBe(parity.audit.hashes[i]);
    });
    expect(chain.verify().ok).toBe(true);
  });

  const build = () => {
    const chain = new AuditChain();
    for (let i = 0; i < 4; i++) chain.append({ n: i });
    return chain;
  };

  it("notices an edited entry", () => {
    const chain = build();
    chain.entries[1].record = { n: 99 };
    expect(chain.verify()).toEqual({ ok: false, firstBad: 1 });
  });

  it("notices a deleted entry", () => {
    const chain = build();
    chain.entries.splice(1, 1);
    expect(firstBroken(chain.entries)).toBe(1);
  });
});