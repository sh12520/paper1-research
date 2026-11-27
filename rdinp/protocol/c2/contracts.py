"""Closed A1 contract, exact integer JCS, acyclic digests and feasibility checks."""
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
REVISION = "RDINP-A1-CANDIDATE-2"
MAX = 9007199254740991
PHASES = ("INTENT_INITIAL", "INTENT_REPLAY", "COMMIT_INITIAL", "COMMIT_REPLAY")


def jcs(value):
    def string(s):
        if type(s) is not str or any(0xD800 <= ord(c) <= 0xDFFF for c in s):
            raise ValueError("non-scalar JSON string")
        return json.dumps(s, ensure_ascii=False, separators=(",", ":"))
    def emit(v):
        if v is None: return "null"
        if type(v) is bool: return "true" if v else "false"
        if type(v) is int:
            if abs(v) > MAX: raise ValueError("unsafe integer")
            return str(v)
        if type(v) is str: return string(v)
        if type(v) is list: return "[" + ",".join(emit(x) for x in v) + "]"
        if type(v) is dict:
            for k in v: string(k)
            return "{" + ",".join(string(k)+":"+emit(v[k]) for k in sorted(v, key=lambda s:s.encode("utf-16-be"))) + "}"
        raise ValueError("not integer-profile JSON")
    return emit(value).encode("utf-8")


def parse(raw):
    if type(raw) is not bytes or len(raw)>65536: raise ValueError("raw cap/type")
    def pairs(xs):
        d={}
        for k,v in xs:
            if k in d: raise ValueError("duplicate key")
            d[k]=v
        return d
    def forbidden(_): raise ValueError("noninteger JSON number")
    obj=json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_float=forbidden, parse_constant=forbidden)
    def depth(x,n=0):
        if n>32: raise ValueError("JSON depth")
        if type(x) is dict:
            for y in x.values(): depth(y,n+1)
        if type(x) is list:
            for y in x: depth(y,n+1)
    depth(obj)
    jcs(obj)
    return obj


def sha(raw): return hashlib.sha256(raw).hexdigest()
def digest(kind,obj): return sha((REVISION+":"+kind+"\0").encode("ascii")+jcs(obj))
def checked(n):
    if type(n) is not int or not 0<=n<=MAX: raise ValueError("derived integer overflow")
    return n
def ceildiv(a,b): return checked((a+b-1)//b)


class Contract:
    def __init__(self, plan_raw, policy, timing):
        self.plan_raw=plan_raw
        self.plan=parse(plan_raw)
        self.policy=parse(jcs(policy))
        self.timing=parse(jcs(timing))
        schema=json.loads((ROOT/"contracts.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate({"plan":self.plan,"policy":self.policy,"timing":self.timing})
        self.policy_digest=digest("POLICY",self.policy)
        if timing["phasePlanRawSha256"]!=sha(plan_raw) or timing["policyProfileDigest"]!=self.policy_digest:
            raise ValueError("configuration preimage mismatch")
        self.digest=digest("TIMING",timing)
        self.message_validator=Draft202012Validator(json.loads((ROOT/"message.schema.json").read_text(encoding="utf-8")))
        p=self.plan; t=self.timing; r=self.policy["resourceRules"]; c=self.policy["clockRules"]
        for n in (p["initialBudgetMs"],p["rejectDeadlineMs"],p["terminalDeadlineMs"],p["cleanupBudgetMs"],r["cleanupDispatchBudgetMs"],r["cleanupCompletionBudgetMs"],t["successRejectPublishBudget"],t["successCommitPublishBudget"],t["failureDispatchBudget"],t["failurePublishBudget"],t["deadlineSafetyMargin"]):checked(n*1000000)
        if tuple(x["phase"] for x in p["phases"])!=PHASES: raise ValueError("phase order")
        self.H=[]; prefix=p["initialBudgetMs"]
        for i,x in enumerate(p["phases"]):
            k=checked((x["requestLossBound"]+1)*(x["responseLossBound"]+1))
            if x["attempts"]<k: raise ValueError("attempt bound infeasible")
            h=checked((k-1)*x["retryMs"]+x["cleanMs"]); self.H.append(h)
            end=checked(prefix+h)
            effective=self.cutoff_ms(i)
            if end>=effective: raise ValueError("latch/publication budget infeasible")
            if i and x["cutoffMs"]<=p["phases"][i-1]["cutoffMs"]: raise ValueError("nonincreasing cutoff")
            prefix=checked(end+x["transitionMs"])
            checked(x["cutoffMs"]*1000000)
        if p["rejectDeadlineMs"]>p["terminalDeadlineMs"]: raise ValueError("reject after overall deadline")
        if r["cleanupDispatchBudgetMs"]+r["cleanupCompletionBudgetMs"]>p["cleanupBudgetMs"]: raise ValueError("cleanup infeasible")
        # Guardability independent of successful commit: latest guaranteed request -> final check.
        pre=p["initialBudgetMs"]+self.H[0]+p["phases"][0]["transitionMs"]+self.H[1]+p["phases"][1]["transitionMs"]
        x=p["phases"][2]; k=(x["requestLossBound"]+1)*(x["responseLossBound"]+1)
        client_ns=checked((pre+(k-1)*x["retryMs"])*1000000+p["sendJitterNs"]+c["clientObservationErrorNs"])
        upper=c["serverRateUpperPpm"]; lower=c["clientRateLowerPpm"]
        # Products explicitly checked: no hidden unlimited-integer wire arithmetic.
        converted=ceildiv(checked(client_ns*upper),lower)
        delivery=ceildiv(checked(p["requestDeliveryNs"]*upper),1000000)
        self.guard_bound=checked(converted+delivery+p["serverPrecheckNs"]+c["serverObservationErrorNs"]+r["commitTailBudgetNs"]+r["commitTailMarginNs"])
        if self.guard_bound>=p["leaseNs"]: raise ValueError("strict lease guardability infeasible")
        checked(p["leaseNs"]+r["commitTailBudgetNs"]+r["commitTailMarginNs"])
        self.logical_message_bound=checked(2*sum(x["attempts"] for x in p["phases"]))

    def cutoff_ms(self,index):
        p=self.plan;t=self.timing
        deadline=p["rejectDeadlineMs"] if index<2 else p["terminalDeadlineMs"]
        publish=t["successRejectPublishBudget"] if index<2 else t["successCommitPublishBudget"]
        return min(p["phases"][index]["cutoffMs"],deadline-publish-t["deadlineSafetyMargin"],p["terminalDeadlineMs"]-t["failureDispatchBudget"]-t["failurePublishBudget"]-t["deadlineSafetyMargin"])

    def message(self,obj):
        jcs(obj); self.message_validator.validate(obj)
        if obj["timingContractDigest"]!=self.digest: raise ValueError("timing digest")
        i=PHASES.index(obj["phase"])
        if obj["attempt"]>=self.plan["phases"][i]["attempts"]: raise ValueError("attempt cap")
        kinds=("INTENT","DECISION","PROBLEM") if i<2 else ("COMMIT","RECEIPT","PROBLEM")
        if obj["kind"] not in kinds: raise ValueError("phase kind")
        if obj["kind"]=="INTENT" and (obj["body"]["decisionDigest"] or obj["body"]["token"] or obj["body"]["epoch"]): raise ValueError("INTENT body")
        if obj["kind"]=="COMMIT" and (not obj["body"]["decisionDigest"] or not obj["body"]["token"]): raise ValueError("COMMIT body")
        if obj["kind"]=="DECISION" and (obj["body"]["status"] not in ("RESERVED","REJECTED") or obj["body"]["receiptDigest"]): raise ValueError("decision body")
        if obj["kind"]=="RECEIPT" and (obj["body"]["status"] not in ("COMMITTED","NOT_APPLIED") or not obj["body"]["receiptDigest"]): raise ValueError("receipt body")


def example_contract():
    """Local mechanism fixture only. Numbers are NOT observed or qualified hard bounds."""
    plan={"revision":REVISION,"initialBudgetMs":100,"phases":[{"phase":phase,"requestLossBound":1,"responseLossBound":1,"attempts":4,"retryMs":40,"cleanMs":120,"cutoffMs":(i+1)*1000,"transitionMs":20} for i,phase in enumerate(PHASES)],"rejectDeadlineMs":2500,"terminalDeadlineMs":5000,"leaseNs":10000000000,"cleanupBudgetMs":100,"requestDeliveryNs":10000000,"serverPrecheckNs":100000000,"sendJitterNs":10000000}
    policy={"revision":REVISION,"clientRules":{"attemptLifetime":"UNTIL_PHASE_CUTOFF","completionEvent":"VERIFIED_PHASE_WINNER_LATCH","deadlineEquality":"FAIL_CLOSED","commitPossibleWriteAhead":True,"onlineUnknownClosurePromised":False,"firstEffectPhasePrerequisites":True},"resourceRules":{"authorityKind":"SQLITE_LOGICAL_QUOTA","leaseEvent":"DURABLE_COMMIT_RETURN","commitTailBudgetNs":50000000,"commitTailMarginNs":1000000,"cleanupDispatchBudgetMs":50,"cleanupCompletionBudgetMs":50},"clockRules":{"clientUnit":"NANOSECONDS","serverUnit":"NANOSECONDS","bootBound":True,"requireNondecreasing":True,"maxTimestampNs":MAX,"clientRateLowerPpm":1000000,"serverRateUpperPpm":1000000,"clientObservationErrorNs":0,"serverObservationErrorNs":0},"transportRules":{"binding":"HTTP_JSON_ES256_DETACHED_JWS","messageAccounting":"LOGICAL_ENDPOINT_SENDS","applicationDuplicationInGuarantee":"NONE","transparentApplicationRetries":False,"redirectsAllowed":False,"sameAttemptRawIdentityRequired":True,"admittedArrivalReplyPolicy":"ONE_CORRELATED_REPLY_UNDER_LIVE_BOUNDED_EXECUTION"}}
    timing={"protocolRevision":REVISION,"contractKind":"CONDITIONAL_BILATERAL_LOGICAL_AUTHORITY","phasePlanRawSha256":sha(jcs(plan)),"policyProfileDigest":digest("POLICY",policy),"timeUnit":"MILLISECONDS","successRejectPublishBudget":100,"successCommitPublishBudget":100,"failureDispatchBudget":50,"failurePublishBudget":100,"deadlineSafetyMargin":10}
    return Contract(jcs(plan),policy,timing)
