"""ES256 detached JWS with immutable static principal/role/revision trust pins."""
import base64
import copy
import json
import uuid
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from contracts import ROOT, REVISION, parse, jcs, sha, digest
from jsonschema import Draft202012Validator, ValidationError


def b64(raw): return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
def unb64(value):
    raw=base64.b64decode(value+"="*((-len(value))%4),altchars=b"-_",validate=True)
    if b64(raw)!=value: raise ValueError("noncanonical base64url")
    return raw


class Identity:
    def __init__(self, principal, role, key=None):
        self.principal=principal;self.role=role;self.kid=principal+"-a1"
        self.key=key or ec.generate_private_key(ec.SECP256R1())
    def pin(self):
        pem=self.key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
        return {"principal":self.principal,"role":self.role,"revision":REVISION,"kid":self.kid,"publicKeyPem":pem}
    def sign(self,message):
        m=copy.deepcopy(message)
        h={"alg":"ES256","crit":["rdinp_canon","rdinp_nonce","rdinp_scope"],"kid":self.kid,"rdinp_canon":"JCS-INTEGER-SCALAR-UNICODE","rdinp_nonce":m["nonce"],"rdinp_scope":REVISION,"typ":"application/rdinp+jws"}
        protected=b64(jcs(h));payload=jcs(m)
        signature=self.key.sign((protected+"."+b64(payload)).encode("ascii"),ec.ECDSA(hashes.SHA256()))
        r,s=decode_dss_signature(signature)
        m["signature"]={"kid":self.kid,"value":protected+".."+b64(r.to_bytes(32,"big")+s.to_bytes(32,"big"))}
        return jcs(m)


class Trust:
    def __init__(self,pins):
        try:Draft202012Validator(json.loads((ROOT/"trust.schema.json").read_text(encoding="utf-8"))).validate(pins)
        except ValidationError as e:raise ValueError("static trust schema") from e
        self.pins={}
        for pin in pins:
            if set(pin)!={"principal","role","revision","kid","publicKeyPem"} or pin["revision"]!=REVISION or pin["role"] not in ("initiator","responder") or pin["kid"] in self.pins: raise ValueError("static pin")
            key=serialization.load_pem_public_key(pin["publicKeyPem"].encode("ascii"))
            if not isinstance(key,ec.EllipticCurvePublicKey) or not isinstance(key.curve,ec.SECP256R1):raise ValueError("P256 required")
            self.pins[pin["kid"]]=(copy.deepcopy(pin),key)
        if len(self.pins)!=2 or {p[0]["role"] for p in self.pins.values()}!={"initiator","responder"} or len({p[0]["principal"] for p in self.pins.values()})!=2:raise ValueError("strict bilateral pins")
        self.digest=sha(jcs([self.pins[k][0] for k in sorted(self.pins)]))
    def verify(self,raw,contract,principal,role):
        m=parse(raw);contract.message(m)
        env=m["signature"];pin,key=self.pins[env["kid"]]
        if pin["principal"]!=principal or pin["role"]!=role or m["sender"]!=principal:raise ValueError("authorization")
        parts=env["value"].split(".")
        if len(parts)!=3 or parts[1]!="":raise ValueError("detached JWS")
        h=parse(unb64(parts[0]));expected={"alg":"ES256","crit":["rdinp_canon","rdinp_nonce","rdinp_scope"],"kid":env["kid"],"rdinp_canon":"JCS-INTEGER-SCALAR-UNICODE","rdinp_nonce":m["nonce"],"rdinp_scope":REVISION,"typ":"application/rdinp+jws"}
        if h!=expected or unb64(parts[0])!=jcs(h):raise ValueError("protected header")
        sig=unb64(parts[2])
        if len(sig)!=64:raise ValueError("signature width")
        unsigned=dict(m);unsigned.pop("signature")
        key.verify(encode_dss_signature(int.from_bytes(sig[:32],"big"),int.from_bytes(sig[32:],"big")),(parts[0]+"."+b64(jcs(unsigned))).encode("ascii"),ec.ECDSA(hashes.SHA256()))
        return m


def base_message(contract,kind,negotiation,intent,phase,attempt,sender,recipient,body):
    return {"revision":REVISION,"kind":kind,"negotiationId":negotiation,"intentId":intent,"phase":phase,"attempt":attempt,"messageId":uuid.uuid4().hex,"nonce":uuid.uuid4().hex,"sender":sender,"recipient":recipient,"timingContractDigest":contract.digest,"requestRawSha256":"","requestJcsSha256":"","body":copy.deepcopy(body)}


def outcome_digest(kind,request,body):
    stable=copy.deepcopy(body);stable.pop("receiptDigest",None)
    if kind=="DECISION":stable.pop("decisionDigest",None)
    context={"revision":REVISION,"negotiationId":request["negotiationId"],"intentId":request["intentId"],"initiator":request["sender"],"authority":request["recipient"],"timingContractDigest":request["timingContractDigest"],"body":stable}
    return digest(kind,context)


def response(identity,contract,request,raw,kind,body):
    m=base_message(contract,kind,request["negotiationId"],request["intentId"],request["phase"],request["attempt"],identity.principal,request["sender"],body)
    m["requestRawSha256"]=sha(raw);m["requestJcsSha256"]=sha(jcs(request))
    return identity.sign(m)
