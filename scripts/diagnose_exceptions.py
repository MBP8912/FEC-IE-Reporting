#!/usr/bin/env python3
"""One-time NY-17 and CO-4 missing Schedule E IE records diagnostic."""
from __future__ import annotations
import json, os
from urllib.parse import urlencode
import refresh as core

SPECS=[
 ("NY17_PP_17",dict(committee_id="C00489799",candidate_office_state="NY",candidate_office_district="17",is_notice="true")),
 ("NY17_PP_ANY",dict(committee_id="C00489799",is_notice="true")),
 ("CO4_FREEDOM_BOEBERT",dict(committee_id="C00552851",candidate_id="H0CO03165",is_notice="true")),
 ("CO4_FREEDOM_ANY",dict(committee_id="C00552851",is_notice="true")),
]
FIELDS=["sub_id","candidate_id","candidate_name","candidate_office_state","candidate_office_district","committee_id","committee_name","expenditure_date","expenditure_amount","support_oppose_indicator","election_type","filing_form","filing_date","file_number","is_notice","expenditure_description","transaction_id","pdf_url"]
def main():
 key=os.environ.get("FEC_API_KEY") or "DEMO_KEY"
 for name,filtering in SPECS:
  args=dict(api_key=key,cycle=2026,most_recent="true",per_page=100,sort="-expenditure_date",**filtering)
  try:
   payload=core.request_json(core.API_URL+"?"+urlencode(args),attempts=1)
   rows=payload.get("results") or []
   count=payload.get("pagination",{}).get("count")
   print("EXCEPTION_QUERY",name,"COUNT",count,"ROWS",len(rows),flush=True)
   for row in rows:
    candidate_name=str(row.get("candidate_name") or "").upper()
    is_target=name.endswith("_17") or name.endswith("_BOEBERT") or any(z in candidate_name for z in ("LAWLER","CONLEY","BOEBERT"))
    if is_target:
     print("EXCEPTION_ROW",name,json.dumps({k:row.get(k) for k in FIELDS},ensure_ascii=False,separators=(",",":")),flush=True)
  except Exception as exc:
   print("EXCEPTION_QUERY_ERROR",name,str(exc),flush=True)
if __name__=="__main__": main()
