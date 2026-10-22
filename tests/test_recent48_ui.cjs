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
    if (tag.toLowerCase() === "details") this.open = false;
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
      fec_url: "https://docquery.fec.gov/cgi-bin/fecimg/?1234", notice: true, filing_form: "F24",
    },
    {
      reported_at: new Date(now.getTime() - 120000).toISOString(),
      expenditure_date: "2026-10-20",
      spender: "Sample Action Fund",
      disposition: "support_conley",
      purpose: "DIGITAL ADVERTISING",
      spend_type: "Digital",
      amount_cents: 370000,
      fec_url: "https://docquery.fec.gov/cgi-bin/fecimg/?5678", notice: true, filing_form: "F24",
    },
  ];
  const elements = await render({
    status: "ok", notice_only: true, checked_at: now.toISOString(),
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
    status: "ok", notice_only: true, checked_at: new Date().toISOString(),
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
  assert.match(note, /not yet verified/);
  assert.doesNotMatch(body + note, /\bnull\b/i);
});

test("rolling-48h panel shows two totals but keeps all spending tables collapsed until clicked", async () => {
  const now = new Date();
  const items = [
    { reported_at: new Date(now.getTime() - 60000).toISOString(),
      expenditure_date: "2026-10-20", spender: "Example PAC",
      disposition: "oppose_conley", purpose: "ADVERTISING",
      spend_type: "TV", amount_cents: 125000, fec_url: "", notice: true, filing_form: "F24" },
    { reported_at: new Date(now.getTime() - 61000).toISOString(),
      expenditure_date: "2026-10-20", spender: "Another PAC",
      disposition: "support_conley", purpose: "DIRECT MAIL",
      spend_type: "Mail", amount_cents: 280000, fec_url: "", notice: true, filing_form: "F24" },
  ];
  const elements = await render({
    status: "ok", notice_only: true, checked_at: now.toISOString(), unresolved_recent_items: 0, items,
  });
  const container = elements.get("recent48-groups");
  assert.equal(container.children.length, 1, "Both totals must share one expandable box");
  const detail = container.children[0];
  assert.equal(detail.tagName, "DETAILS");
  assert.equal(detail.open, false, "The box must be collapsed on initial load");
  const summary = detail.children[0];
  assert.equal(summary.tagName, "SUMMARY", "Native summary is the down-arrow toggle");
  assert.match(summary.textContent, /Spending benefiting Lawler/);
  assert.match(summary.textContent, /Spending benefiting Conley/);
  assert.match(summary.textContent, /\$1,250\.00/);
  assert.match(summary.textContent, /\$2,800\.00/);
  assert.doesNotMatch(summary.textContent, /Example PAC|DIRECT MAIL|ADVERTISING/,
    "Details must not be visible in collapsed headline");
  const expanded = detail.children[1];
  assert.equal(expanded.tagName, "DIV");
  assert.equal(expanded.children.length, 2, "Both candidate item tables are in the disclosure");
  assert.match(expanded.textContent, /Example PAC/);
  assert.match(expanded.textContent, /Another PAC/);
  assert.match(expanded.textContent, /DIRECT MAIL/);
  detail.open = true;
  assert.equal(detail.open, true, "Browser-native disclosure can expand on click");
});

test("F3X monthly and non-notice F5 rows cannot inflate latest-48-hour candidate totals", async () => {
  const now = new Date();
  const common = {reported_at:new Date(now.getTime()-60000).toISOString(),expenditure_date:"2026-10-20",
                  spend_type:"TV",fec_url:""};
  const elements = await render({
    status:"ok",notice_only:true,checked_at:now.toISOString(),unresolved_recent_items:0,
    items:[
      {...common,spender:"HMP",disposition:"oppose_lawler",purpose:"TV ADVERTISING",
        amount_cents:47378256,notice:false,filing_form:"F3X"},
      {...common,spender:"VoteVets",disposition:"oppose_lawler",purpose:"TV ADVERTISING",
        amount_cents:17496000,notice:false,filing_form:"F3X"},
      {...common,spender:"Quarterly F5",disposition:"oppose_lawler",purpose:"OLD SPEND",
        amount_cents:4500000,notice:false,filing_form:"F5"},
      {...common,spender:"Actual new notice",disposition:"oppose_conley",purpose:"TV BUY",
        amount_cents:125000,notice:true,filing_form:"F24"},
      {...common,spender:"Expedited noncommittee IE",disposition:"support_conley",purpose:"DIGITAL ADS",
        amount_cents:17500,notice:true,filing_form:"F5"}
    ]
  });
  const body = elements.get("recent48-groups").textContent;
  assert.doesNotMatch(body,/HMP|VoteVets|Quarterly F5|\$473,782|\$174,960/);
  assert.match(body,/Actual new notice|\$1,250/);
  assert.match(body,/Expedited noncommittee IE|\$175/);
});

test("legacy feeds lacking a verified notice-only marker never display regular spending as zero",async()=>{
  const elements=await render({status:"ok",checked_at:new Date().toISOString(),
    items:[{reported_at:new Date().toISOString(),spender:"HMP",disposition:"oppose_lawler",amount_cents:47378256}]});
  const note=elements.get("recent48-note").textContent;
  const body=elements.get("recent48-groups").textContent;
  assert.match(note,/notice-only FEC feed is not yet verified/);
  assert.doesNotMatch(body,/\$0|HMP|\$473,782/);
});
