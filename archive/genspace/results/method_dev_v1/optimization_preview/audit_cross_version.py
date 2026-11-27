"""Compare completed old/new development records; do not merge them."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'results/method_dev_v1';OLD=BASE/'run';NEW=BASE/'run_optimized'
DROP={'elapsed_seconds','public_probe_seconds','public_setup_seconds','public_ranking_seconds','state_machine_calls'}
def sha(x):return hashlib.sha256(x).hexdigest()
def read_valid(root,iid):
    path=root/iid;raw=(path/'record.json').read_bytes();marker=json.loads((path/'COMPLETE.json').read_text(encoding='utf8'))
    if marker['record_sha256']!=sha(raw) or marker['instance_id']!=iid:raise ValueError('invalid transaction '+str(path))
    return json.loads(raw),marker
def main():
    old={x.name for x in OLD.iterdir() if x.is_dir() and (x/'COMPLETE.json').is_file()}
    new={x.name for x in NEW.iterdir() if x.is_dir() and (x/'COMPLETE.json').is_file()}
    common=sorted(old&new)
    if len(old)!=230 or len(common)!=230:raise ValueError('old 230 instances are not all complete in both runs')
    mismatches=[];checked=0
    for iid in common:
        a,am=read_valid(OLD,iid);b,bm=read_valid(NEW,iid)
        if am['input_sha256']!=bm['input_sha256']:mismatches.append({'id':iid,'field':'input_sha256'});continue
        for k in ('instance_id','instance_hash','public_hash','private_hash','family','configuration','oracle'):
            if a.get(k)!=b.get(k):mismatches.append({'id':iid,'field':k})
        if set(a['methods'])!=set(b['methods']):mismatches.append({'id':iid,'field':'method set'});continue
        for method in a['methods']:
            x=a['methods'][method];y=b['methods'][method]
            if x['history']!=y['history']:mismatches.append({'id':iid,'field':method+' history'})
            if set(x['budgets'])!=set(y['budgets']):mismatches.append({'id':iid,'field':method+' budget set'});continue
            for budget in x['budgets']:
                xa={k:v for k,v in x['budgets'][budget].items() if k not in DROP};yb={k:v for k,v in y['budgets'][budget].items() if k not in DROP}
                if xa!=yb:mismatches.append({'id':iid,'field':method+' B'+budget,'differing_keys':sorted(k for k in set(xa)|set(yb) if xa.get(k)!=yb.get(k))})
                checked+=1
    report={'pass':not mismatches,'old_complete':len(old),'new_complete_at_check':len(new),'common_complete':len(common),'method_budget_comparisons':checked,
            'mismatches':mismatches,'excluded_fields':sorted(DROP),'scope':'completed records only; no merge, no timing inference',
            'old_manifest_sha256':sha((OLD/'run_manifest.json').read_bytes()),'new_manifest_sha256':sha((NEW/'run_manifest.json').read_bytes())}
    (Path(__file__).parent/'cross_version_audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ('pass','old_complete','new_complete_at_check','common_complete','method_budget_comparisons')},sort_keys=True))
    if mismatches:raise SystemExit(1)
if __name__=='__main__':main()
