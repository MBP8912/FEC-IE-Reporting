/* NY-17 independent expenditure dashboard. Browser never queries the FEC. */
(function(){
"use strict";
var DATA=null,groupSort="total",sortDesc=true,chartWindow="30";
var $=function(id){return document.getElementById(id)};
var dollar=function(v){return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(v||0)/100)};
var fullDollar=function(v){return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD"}).format(Number(v||0)/100)};
var readableDate=function(v){if(!v)return "Not reported";var d=new Date(v.slice(0,10)+"T12:00:00Z");return d.toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric",timeZone:"UTC"})};
var shortDate=function(v){if(!v)return "";var d=new Date(v+"T12:00:00Z");return d.toLocaleDateString("en-US",{month:"short",day:"numeric",timeZone:"UTC"})};
var escSource=function(url){try{var u=new URL(url);return u.protocol==="https:"&&["docquery.fec.gov","www.fec.gov"].includes(u.hostname)?u.toString():""}catch(e){return ""}};
function e(tag,cl,value){var n=document.createElement(tag);if(cl)n.className=cl;if(value!==undefined&&value!==null)n.textContent=String(value);return n}
function svg(tag,attrs){var n=document.createElementNS("http://www.w3.org/2000/svg",tag);Object.keys(attrs||{}).forEach(function(k){n.setAttribute(k,String(attrs[k]))});return n}
function status(text,type){var node=$("status");node.className="status "+(type||"pending");node.textContent=text}
function tally(root,content,cl){var t=e("span",cl,content);root.append(t);return t}
function summary(data){
  var t=data.totals||{};
  $("lawler-total").textContent=dollar(t.benefit_lawler);
  $("lawler-support").textContent=dollar(t.support_lawler);
  $("conley-oppose").textContent=dollar(t.oppose_conley);
  $("conley-total").textContent=dollar(t.benefit_conley);
  $("conley-support").textContent=dollar(t.support_conley);
  $("lawler-oppose").textContent=dollar(t.oppose_lawler);
  $("total-records").textContent=data.transactions.length.toLocaleString();
  $("total-groups").textContent=data.groups.length.toLocaleString();
  var excluded=data.counts.excluded||{};
  var suppressed=(excluded.repeated_transaction_or_amendment||0)+(excluded.notice_regular_duplicates||0)+(excluded.duplicate_source_id||0);
  $("dedup-note").textContent=suppressed.toLocaleString();
  var date=new Date(data.generated_at);
  if(!Number.isNaN(date.getTime()))$("last-updated").textContent="◷ Checked "+date.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"});
  status("Verified FEC data · "+data.transactions.length.toLocaleString()+" unique general-election Schedule E entries · "+
  data.groups.length.toLocaleString()+" spending groups. Details link to FEC source records.","good");
}
function legend(data){
 var container=$("legend");container.replaceChildren();
 data.disposition_order.forEach(function(k){
   var d=e("span","legend-item");var color=e("i","legend-dot");color.style.backgroundColor=data.colors[k];
   d.append(color,e("span","",data.disposition_labels[k]));container.append(d);
 });
}
function makeDayRange(data,mode){
 var all=data.daily||[];
 var end=(data.generated_at||"").slice(0,10);
 if(data.period&&data.period.to&&data.period.to<end)end=data.period.to;
 if(!end||!/^\d{4}-\d{2}-\d{2}$/.test(end))end="2026-10-21";
 var earliest=all.length?all[0].date:end;
 var dateEnd=Date.parse(end+"T00:00:00Z");
 var since=mode==="all"?Date.parse(earliest+"T00:00:00Z"):
     dateEnd-(Number(mode)-1)*86400000;
 var min=Date.parse((data.period&&data.period.from||"2025-01-01")+"T00:00:00Z");
 since=Math.max(min,since);
 var indexed=Object.fromEntries(all.map(function(x){return [x.date,x]}));
 var result=[];
 for(var stamp=since;stamp<=dateEnd;stamp+=86400000){
   var ds=new Date(stamp).toISOString().slice(0,10);
   var item=indexed[ds]||{date:ds,total:0};
   result.push(item);
 }
 return result;
}
function abbreviatedMoney(v){
 var n=v/100;
 if(n>=1000000)return "$"+(n/1000000).toFixed(n%1000000?1:0)+"m";
 if(n>=1000)return "$"+(n/1000).toFixed(n%1000?1:0)+"k";
 return "$"+Math.round(n);
}
function drawChart(){
 if(!DATA)return;
 var target=$("chart"),scroller=$("chart-scroller");
 target.replaceChildren();
 var days=makeDayRange(DATA,chartWindow);
 if(!days.length){target.append(e("div","chart-pending","No dates in the selected range."));return}
 var mx=Math.max.apply(null,days.map(function(day){return day.total||0}));
 var maximum=Math.max(10000,mx);
 var order=Math.pow(10,Math.floor(Math.log10(maximum)));
 var steps=[1,2,5,10];var maxAxis=steps[3]*order;
 for(var i=0;i<steps.length;i++){if(maximum<=steps[i]*order){maxAxis=steps[i]*order;break}}
 // Keep at least four useful horizontal gridlines, including top/bottom.
 var pxPerDay=chartWindow==="all"?23:Math.max(24,chartWindow==="90"?23:31);
 var plotW=days.length*pxPerDay;
 var width=Math.max(830,plotW+104),height=320,ml=76,mr=24,mt=15,mb=53,plotH=height-mt-mb;
 var actualPlotW=width-ml-mr;
 target.style.width=width+"px";
 var chart=svg("svg",{width:width,height:height,viewBox:"0 0 "+width+" "+height,role:"img","aria-label":"Daily FEC independent spending by disposition"});
 function ypos(v){return mt+plotH*(1-v/maxAxis)}
 for(i=0;i<=4;i++){
   var val=maxAxis*i/4,y=ypos(val);
   chart.append(svg("line",{x1:ml,y1:y,x2:width-mr,y2:y,"class":"grid-line"}));
   var lab=svg("text",{x:ml-10,y:y+4,"text-anchor":"end","class":"axis-text"});lab.textContent=abbreviatedMoney(val);chart.append(lab);
 }
 var band=actualPlotW/days.length;
 var barW=Math.min(24,Math.max(10,band*.63));
 var labelsStep=Math.max(1,Math.ceil(days.length/Math.min(13,Math.floor(width/100))));
 days.forEach(function(day,i){
   var xx=ml+i*band+(band-barW)/2;
   var running=0;
   DATA.disposition_order.forEach(function(d){
     var v=day[d]||0;
     if(v===0)return;
     var segment=svg("rect",{x:xx,y:ypos(running+v),width:barW,height:Math.max(1,v/maxAxis*plotH),rx:1.5,fill:DATA.colors[d],"class":"chart-segment",tabindex:0});
     var title=svg("title");title.textContent=readableDate(day.date)+" • "+DATA.disposition_labels[d]+": "+fullDollar(v);
     segment.append(title);chart.append(segment);running+=v;
   });
   if(i%labelsStep===0||i===days.length-1){
     var x=svg("text",{x:xx+barW/2,y:height-17,"text-anchor":"middle","class":"axis-text"});
     x.textContent=shortDate(day.date);chart.append(x);
   }
 });
 target.append(chart);
 $("chart-note").textContent="Daily expenditure amounts · "+shortDate(days[0].date)+" to "+shortDate(days[days.length-1].date)+
   " · "+days.length+" date"+(days.length===1?"":"s")+" shown. Hover or focus a stacked segment for the reported amount.";
 scroller.scrollLeft=chartWindow==="all"?scroller.scrollWidth:0;
}
function recordButton(amount,criteria,kind){
 if(!amount)return e("span","zero","—");
 var b=e("button","amount-link "+(kind||""),dollar(amount));
 b.type="button";b.title="View "+dollar(amount)+" in underlying FEC expenditures";
 b.addEventListener("click",function(){openDetails(criteria)});
 return b;
}
function groupTable(){
 if(!DATA)return;
 var q=($("group-search").value||"").trim().toLowerCase();
 var groups=DATA.groups.filter(function(g){return g.name.toLowerCase().includes(q)});
 groups.sort(function(a,b){
  var cmp=groupSort==="name"?a.name.localeCompare(b.name):Number(a[groupSort]||0)-Number(b[groupSort]||0);
  return sortDesc?-cmp:cmp;
 });
 var body=$("group-rows");body.replaceChildren();
 for(var i=0;i<groups.length;i++){
  var g=groups[i],row=e("tr");
  row.append(e("td","group-name",g.name));
  var tdTotal=e("td","num");tdTotal.append(recordButton(g.total,{group:g.name}, ""));row.append(tdTotal);
  DATA.disposition_order.forEach(function(kind){
    var td=e("td","num");td.append(recordButton(g[kind],{group:g.name,disposition:kind},
      (kind==="support_lawler"||kind==="oppose_conley")?"red-link":"blue-link"));row.append(td);
  });
  body.append(row);
 }
 if(!groups.length){var empty=e("tr");var td=e("td","table-placeholder",q?"No matching groups":"No verified spending groups.");td.colSpan=6;empty.append(td);body.append(empty)}
 var t=DATA.totals,foot=$("group-footer");foot.replaceChildren();
 var footerRow=e("tr","group-footer");footerRow.append(e("td","","TOTAL"));
 [t.all,t.support_lawler,t.oppose_conley,t.support_conley,t.oppose_lawler].forEach(function(amount,idx){
  var td=e("td","num");td.append(recordButton(amount,idx?{disposition:DATA.disposition_order[idx-1]}:{},idx>2?"blue-link":"red-link"));footerRow.append(td);
 });
 foot.append(footerRow);
 $("group-count").textContent=groups.length.toLocaleString()+" of "+DATA.groups.length.toLocaleString()+" reporting groups";
}
function makePivot(){
 if(!DATA)return;
 var root=$("pivot");root.replaceChildren();
 DATA.pivot.forEach(function(section,index){
  var detail=e("details","pivot-disposition");detail.dataset.disposition=section.key;
  if(index===0)detail.open=true;
  var sum=e("summary","pivot-disposition-title");
  sum.append(e("span","summary-label",section.name),e("span","summary-total",dollar(section.total)));
  detail.append(sum);
  var interior=e("div","pivot-contents");
  if(!section.categories.length){interior.append(e("div","table-placeholder","No spending in this disposition"))}
  section.categories.forEach(function(category){
    var d=e("details","pivot-category");
    var header=e("summary");header.append(e("span","summary-label",category.name),e("span","pivot-money",dollar(category.total)));d.append(header);
    category.groups.forEach(function(group){
      var row=e("div","pivot-group");
      var btn=e("button","",group.name);btn.type="button";btn.addEventListener("click",function(){openDetails({group:group.name,disposition:section.key,type:category.name})});
      row.append(btn,e("strong","pivot-money",dollar(group.amount_cents)));d.append(row);
    });
    interior.append(d);
  });
  detail.append(interior);root.append(detail);
 });
}
function sourceRow(item){
 var tr=e("tr");
 tr.append(e("td","date-column",readableDate(item.date)));
 var group=e("td");group.append(e("strong","",item.group));group.append(e("small","",item.payee?"Paid to: "+item.payee:"Payee not reported"));tr.append(group);
 var description=e("td");description.append(e("strong","",item.description));description.append(e("small","",item.type));tr.append(description);
 tr.append(e("td","",DATA.disposition_labels[item.disposition]||item.disposition));
 var last=e("td","num");last.append(e("strong","",fullDollar(item.amount_cents)));
 var url=escSource(item.pdf_url);
 if(url){var a=e("a","","Original FEC record ↗");a.href=url;a.target="_blank";a.rel="noopener noreferrer";last.append(a)}
 else last.append(e("small","","Source image not linked"));
 if(item.notice)last.append(e("small","","24/48-hour notice"));
 tr.append(last);return tr;
}
function openDetails(criteria){
 if(!DATA)return;
 criteria=criteria||{};
 var items=DATA.transactions.filter(function(t){
  return(!criteria.group||t.group===criteria.group)&&
         (!criteria.disposition||t.disposition===criteria.disposition)&&
         (!criteria.type||t.type===criteria.type);
 });
 var title=[criteria.group,criteria.disposition?DATA.disposition_labels[criteria.disposition]:null,criteria.type].filter(Boolean).join(" / ");
 $("detail-title").textContent=title||"All independent expenditures";
 var sum=items.reduce(function(s,t){return s+t.amount_cents},0);
 $("detail-summary").textContent=items.length.toLocaleString()+" source expenditure"+(items.length===1?"":"s")+" • "+fullDollar(sum);
 var body=$("detail-rows");body.replaceChildren();
 items.sort(function(a,b){return b.amount_cents-a.amount_cents||b.date.localeCompare(a.date)});
 items.forEach(function(item){body.append(sourceRow(item))});
 var dialog=$("detail-dialog");if(dialog.showModal)dialog.showModal();else dialog.setAttribute("open","");
}
function downloadCsv(){
 if(!DATA)return;
 var headers=["Expenditure date","Disposition","Spending group","Expenditure type","Original FEC description","Payee","Amount USD","Candidate ID","Original FEC source","FEC transaction ID","FEC filing date","Expedited notice"];
 var lines=DATA.transactions.map(function(t){return [t.date,DATA.disposition_labels[t.disposition],t.group,t.type,t.description,t.payee,(t.amount_cents/100).toFixed(2),t.candidate_id,t.pdf_url,t.transaction_id,t.filing_date,t.notice?"yes":"no"]});
 var cell=function(v){var s=String(v==null?"":v);return '"'+s.replaceAll('"','""')+'"';};
 var txt=[headers].concat(lines).map(function(row){return row.map(cell).join(",")}).join("\r\n");
 var url=URL.createObjectURL(new Blob(["\ufeff"+txt],{type:"text/csv;charset=utf-8"}));
 var a=e("a");a.href=url;a.download="ny17-independent-expenditures-2026-general.csv";document.body.append(a);a.click();a.remove();
 setTimeout(function(){URL.revokeObjectURL(url)},1500);
}
function build(data){
 if(!data||data.status!=="ok"){status("No verified FEC data published yet. The updater has not completed; figures are intentionally hidden.","pending");return}
 if(!Array.isArray(data.daily)||!Array.isArray(data.pivot)||!Array.isArray(data.groups)||!Array.isArray(data.transactions))throw new Error("Invalid JSON schema for FEC expenditures");
 DATA=data;
 summary(data);legend(data);drawChart();groupTable();makePivot();$("csv-download").disabled=false;
 var excluded=data.counts.excluded||{};
 var candidates=excluded.other_candidate||0,elections=excluded.other_election||0;
 var note="Excluded "+candidates+" records targeting other candidates and "+elections+" for other elections; "+(excluded.memo_item||0)+" memo entries excluded. Descriptions retain original FEC text in each source detail.";
 $("warnings").hidden=false;$("warnings").textContent=note;
}
document.querySelectorAll("[data-window]").forEach(function(btn){btn.addEventListener("click",function(){
 chartWindow=btn.dataset.window;
 document.querySelectorAll("[data-window]").forEach(function(b){b.classList.toggle("active",b===btn);b.setAttribute("aria-pressed",String(b===btn))});
 drawChart();
})});
document.querySelectorAll("#groups-table th button[data-sort]").forEach(function(btn){
 btn.addEventListener("click",function(){
  var v=btn.dataset.sort;
  sortDesc=groupSort===v?!sortDesc:v!=="name";
  groupSort=v;groupTable();
 });
});
$("group-search").addEventListener("input",groupTable);
$("csv-download").addEventListener("click",downloadCsv);
$("detail-close").addEventListener("click",function(){$("detail-dialog").close();});
$("expand-all").addEventListener("click",function(){
 var ds=[].slice.call(document.querySelectorAll("#pivot details"));var hasClosed=ds.some(function(d){return !d.open});
 ds.forEach(function(d){d.open=hasClosed});
 $("expand-all").textContent=hasClosed?"Collapse all":"Expand all";
});
fetch("./data/data.json?cache="+Date.now(),{cache:"no-store"})
 .then(function(r){if(!r.ok)throw Error("HTTP "+r.status+" reading FEC data");return r.json()})
 .then(build)
 .catch(function(err){status("Could not load verified expenditure data: "+err.message,"error")});
})();
