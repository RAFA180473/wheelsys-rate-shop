#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT=Path(__file__).resolve().parents[1]
RATES_PATH=ROOT/'public'/'data'/'rates.json'
HISTORY_PATH=ROOT/'public'/'data'/'rateshop-history.json'

def pt_date(s): return datetime.strptime(s,'%d/%m/%Y').date()

def main():
    rates=json.loads(RATES_PATH.read_text(encoding='utf-8'))
    old={}
    if HISTORY_PATH.exists():
        old=json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
    old_targets={t.get('id'):t for t in old.get('targets',[]) if t.get('id')}
    targets=[]
    for tariff,locs in rates.items():
        for loc,rows in locs.items():
            periods={}
            for r in rows:
                periods.setdefault((r['pickupStart'],r['pickupEnd']),set()).add(r['group'])
            for (ps,pe),groups in sorted(periods.items(),key=lambda kv:pt_date(kv[0][0])):
                checkout=pt_date(ps); checkin=checkout+timedelta(days=7)
                tid=f'{tariff}|{loc}|{checkout.isoformat()}|{checkin.isoformat()}'
                prev=old_targets.get(tid,{})
                targets.append({
                    'id':tid,'tariff':tariff,'location':loc,
                    'ratePeriodStart':ps,'ratePeriodEnd':pe,
                    'checkout':checkout.isoformat(),'checkin':checkin.isoformat(),'days':7,
                    'groups':sorted(groups),'status':prev.get('status','pending'),
                    'lastCollectedAt':prev.get('lastCollectedAt')
                })
    out={
      'schemaVersion':1,
      'generatedAt':datetime.now(timezone.utc).isoformat(),
      'description':'Arquivo Rate Shop: targets das tarifas e pesquisas de concorrência guardadas.',
      'targets':targets,
      'searches':old.get('searches',[])
    }
    HISTORY_PATH.parent.mkdir(parents=True,exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Rate Shop history atualizado: {len(targets)} targets; {len(out["searches"])} pesquisas preservadas.')

if __name__=='__main__': main()
