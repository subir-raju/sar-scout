import { sha256 } from "./sha256";

export const GENESIS = "0".repeat(64);

export type AuditValue = string | number | boolean | null;
export type AuditRecord = Record<string, AuditValue>;

export interface AuditEntry {
  record: AuditRecord;
  prev: string;
  hash: string;
}

// Python's json.dumps writes every non-ASCII character as \uXXXX. Do the same.
const asciiOnly = (text: string) =>
  text.replace(/[\u0080-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));

/* The same text as Python's json.dumps(record, sort_keys=True, separators=(",", ":")).
   Whole numbers, strings, booleans and null only: JavaScript and Python print decimals
   differently, so a record that holds one is refused rather than hashed wrongly. */
export function canonical(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isInteger(value)) throw new Error("audit records cannot hold decimals; use a string");
    return String(value);
  }
  if (typeof value === "string") return asciiOnly(JSON.stringify(value));
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return "{" + keys.map((k) => asciiOnly(JSON.stringify(k)) + ":" + canonical(obj[k])).join(",") + "}";
}

const digest = (previous: string, record: AuditRecord) => sha256(previous + canonical(record));

/* Returns where the chain first breaks, or -1 when every entry checks out. */
export function firstBroken(entries: AuditEntry[]): number {
  let previous = GENESIS;
  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    if (entry.prev !== previous || digest(previous, entry.record) !== entry.hash) return i;
    previous = entry.hash;
  }
  return -1;
}

/* The same append as the class below, but on a plain list, which suits React state. */
export function appendEntry(entries: AuditEntry[], record: AuditRecord): AuditEntry[] {
  const prev = entries.length ? entries[entries.length - 1].hash : GENESIS;
  return [...entries, { record, prev, hash: digest(prev, record) }];
}

export class AuditChain {
  entries: AuditEntry[] = [];

  get last(): string {
    return this.entries.length ? this.entries[this.entries.length - 1].hash : GENESIS;
  }

  append(record: AuditRecord): AuditEntry {
    const entry = { record, prev: this.last, hash: digest(this.last, record) };
    this.entries.push(entry);
    return entry;
  }

  verify(): { ok: boolean; firstBad: number } {
    const firstBad = firstBroken(this.entries);
    return { ok: firstBad === -1, firstBad };
  }
}