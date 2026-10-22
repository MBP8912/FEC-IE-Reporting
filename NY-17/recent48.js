/* NY-17 pilot only: independent expenditures reported to the FEC in 48 hours. */
(function(){
"use strict";
const lookup=id=>document.getElementById(id);
const dollars=cents=>new Intl.NumberFormat("en-US",{style:"currency",currency:"USD"}).format(Number(cents)/100);
const ET={timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"};
const DAY={timeZone:"UTC",month:"short",day:"numeric",year:"numeric"};
function cell(tag,content,className){
  const n=document.createElement(tag);
  if(className)n.className=className;
  if(content!==undefined)n.textContent=String(content);
  return n;
}
function fmt(date){return new Intl.DateTimeFormat("en-US",ET).format(new Date(date))+" ET"}
function fmtDay(day){const date=new Date(day+"T12:00:00Z");return new Intl.DateTimeFormat("en-US",DAY).format(date)}
function allowedSource(url){
  try{const u=new URL(url);return u.protocol==="https:"&&["docquery.fec.gov","www.fec.gov"].includes(u.hostname)?u.href:null}
  catch(e){return null}
}
function view(payload){
  const groups=lookup("recent48-groups"),note=lookup("recent48-note"),updated=lookup("recent48-updated");
  groups.replaceChildren();
  if(!payload||!["ok","partial"].includes(payload.status)||!Array.isArray(payload.items)){
    note.textContent="Exact FEC receipt times have not yet been verified. No 48-hour amounts will be shown until the data is available.";
    updated.textContent="Receipt-time verification pending";
    return;
  }
  const now=Date.now(),since=now-48*60*60*1000;
  const recent=payload.items.filter(t=>{
    const time=Date.parse(t.reported_at);
    return Number.isFinite(time)&&time>=since&&time<=now&&
           Number.isSafeInteger(t.amount_cents);
  });
  const candidates=[
    {key:"lawler",name:"Lawler",party:"Republican",directions:["support_lawler","oppose_conley"],theme:"red"},
    {key:"conley",name:"Conley",party:"Democrat",directions:["support_conley","oppose_lawler"],theme:"blue"}
  ].map(group=>{
    const items=recent.filter(t=>group.directions.includes(t.disposition));
    const total=items.reduce((n,t)=>n+t.amount_cents,0);
    return {...group,items,total};
  }).sort((a,b)=>b.total-a.total||a.name.localeCompare(b.name));
  const label={support_lawler:"Support Lawler",oppose_conley:"Oppose Conley",
               support_conley:"Support Conley",oppose_lawler:"Oppose Lawler"};
  for(const candidate of candidates){
    const section=cell("section",null,"recent-beneficiary");
    const heading=cell("div",null,"recent-beneficiary-header "+candidate.theme);
    const text=cell("div",null,"recent-name");
    const dot=cell("span",null,"recent-dot "+candidate.theme);
    text.append(dot,cell("strong","Spending benefiting "+candidate.name));
    text.append(cell("span",candidate.items.length.toLocaleString()+" reported item"+(candidate.items.length===1?"":"s"),"recent-count"));
    const total=cell("div",payload.status==="partial"&&candidate.total===0?"—":dollars(candidate.total),"recent-total");
    heading.append(text,total);section.append(heading);
    const wrap=cell("div",null,"recent-table-scroll");
    const table=cell("table",null,"recent-table");
    const thead=cell("thead");
    const tr=cell("tr");
    for(const heading of ["Spender","Disposition","Purpose","Amount","Date"]){
      tr.append(cell("th",heading,heading==="Amount"?"num":""));
    }
    thead.append(tr);table.append(thead);
    const body=cell("tbody");
    if(!candidate.items.length){
      const row=cell("tr"),message=cell("td",
        payload.status==="partial"?
          "No verified-timestamp items for this candidate; some FEC receipt times are unresolved.":
          "No qualifying expenditures reported in this 48-hour period.",
        "recent-empty");
      message.colSpan=5;row.append(message);body.append(row);
    }else{
      candidate.items.sort((a,b)=>Date.parse(b.reported_at)-Date.parse(a.reported_at)||
          b.amount_cents-a.amount_cents||a.spender.localeCompare(b.spender));
      for(const item of candidate.items){
        const row=cell("tr");
        const spender=cell("td");
        const dest=allowedSource(item.fec_url);
        if(dest){
          const link=cell("a",item.spender+" ↗");link.href=dest;
          link.target="_blank";link.rel="noopener noreferrer";link.title="Original FEC filing";
          spender.append(link);
        }else{spender.textContent=item.spender}
        row.append(spender);
        row.append(cell("td",label[item.disposition]||item.disposition));
        const purpose=cell("td",null,"recent-purpose");
        purpose.append(cell("span",item.purpose),cell("small",item.spend_type||""));
        row.append(purpose);
        row.append(cell("td",dollars(item.amount_cents),"num recent-money"));
        const date=cell("td",null,"recent-date");
        date.append(cell("span",fmt(item.reported_at)));
        date.append(cell("small","Spent: "+fmtDay(item.expenditure_date)));
        row.append(date);body.append(row);
      }
    }
    table.append(body);wrap.append(table);section.append(wrap);groups.append(section);
  }
  const last=new Date(payload.checked_at);
  if(Number.isFinite(last.getTime())){
    updated.textContent="FEC receipt times checked "+fmt(payload.checked_at);
  }else{updated.textContent="Receipt time last checked: unavailable"}
  const age=Date.now()-last.getTime();
  const uncertain=Number(payload.unresolved_recent_items)||0;
  const explanations=["Based on FEC filing receipt timestamps, not expenditure dates. Shows processed, deduplicated Schedule E entries; newly submitted filings may take time to appear."];
  if(uncertain)explanations.push(uncertain+" potentially recent item"+(uncertain===1?" is":"s are")+" missing exact receipt time and excluded from the verified totals.");
  if(age>90*60*1000)explanations.push("Data is more than 90 minutes old; recent filings may not yet be included.");
  note.textContent=explanations.join(" ");
}
fetch("./data/recent48.json?cache="+Date.now(),{cache:"no-store"})
  .then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()})
  .then(view)
  .catch(err=>{
    lookup("recent48-updated").textContent="Receipt-time lookup unavailable";
    lookup("recent48-note").textContent="Unable to verify the FEC receipt-time feed ("+err.message+"). Recent spending totals are not shown.";
  });
})();
