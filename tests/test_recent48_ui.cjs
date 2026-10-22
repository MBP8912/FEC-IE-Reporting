/**
 * Regression: creating intentionally empty elements must never print "null".
 * Uses only Node's built-in test runner and a minimal DOM to exercise
 * the actual NY-17 48-hour browser script end-to-end.
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const browserScript = fs.readFileSync(
  path.resolve(__dirname, "../NY-17/recent48.js"), "utf8");

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this._ownText = "";
    this.children = [];
    this.className = "";
  }
  set textContent(value) {
    this._ownText = String(value);
    this.children = [];
  }
  get textContent() {
    return this._ownText + this.children.map(child => child.textContent).join("");
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this._ownText = "";
    this.children = [...children];
  }
}
async function render(payload) {
  const elements = new Map();
  const doc = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, new FakeElement("div"));
      return elements.get(id);
    },
    createElement(tag) { return new FakeElement(tag); },
  };
  const fakeFetch = async () => ({ok: true, json: async () => payload});
  vm.runInNewContext(browserScript, {
    document: doc, fetch: fakeFetch,
    Date, Intl, URL, String, Number, Array, console,
  }, {filename: "NY-17/recent48.js"});
  await new Promise(resolve => setImmediate(resolve));
  return elements;
}

test("NY-17 report list renders spender, purpose, date and amount without literal null", async () => {
  const now = new Date();
  const items = [
    {
      reported_at: new Date(now.getTime() - 60000).toISOString(),
      expenditure_date: "2026-10-20",
      spender: "Example Spending Committee",
      disposition: "oppose_conley",
      purpose: "DIRECT MAIL SERVICES",
      spend_type: "Mail",
      amount_cents: 125000,
      fec_url: "https://docquery.fec.gov/cgi-bin/fecimg/?1234",
    },
    {
      reported_at: new Date(now.getTime() - 120000).toISOString(),
      expenditure_date: "2026-10-20",
      spender: "Sample Action Fund",
      disposition: "support_conley",
      purpose: "DIGITAL ADVERTISING",
      spend_type: "Digital",
      amount_cents: 370000,
      fec_url: "https://docquery.fec.gov/cgi-bin/fecimg/?5678",
    },
  ];
  const elements = await render({
    status: "ok", checked_at: now.toISOString(),
    unresolved_recent_items: 0, items,
  });
  const text = elements.get("recent48-groups").textContent;
  assert.doesNotMatch(text, /\bnull\b/i);
  assert.match(text, /Example Spending Committee/);
  assert.match(text, /Sample Action Fund/);
  assert.match(text, /DIRECT MAIL SERVICES/);
  assert.match(text, /DIGITAL ADVERTISING/);
  assert.match(text, /Oppose Conley/);
  assert.match(text, /Support Conley/);
  assert.match(text, /\$1,250\.00/);
  assert.match(text, /\$3,700\.00/);
  assert.match(text, /Spent: Oct/);
});

test("empty recent data has a clear message, never leftover null placeholders", async () => {
  const elements = await render({
    status: "ok", checked_at: new Date().toISOString(),
    unresolved_recent_items: 0, items: [],
  });
  const text = elements.get("recent48-groups").textContent;
  assert.doesNotMatch(text, /\bnull\b/i);
  assert.match(text, /No qualifying expenditures reported in this 48-hour period/);
});

test("pending receipt timestamps do not render invented or null values", async () => {
  const elements = await render({status: "pending", items: []});
  const note = elements.get("recent48-note").textContent;
  const body = elements.get("recent48-groups").textContent;
  assert.match(note, /not yet been verified/);
  assert.doesNotMatch(body + note, /\bnull\b/i);
});
