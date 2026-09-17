#!/usr/bin/env python3
"""
ULTIMATE RECRUITING ENGINE v18.16
Recruiter-style GitHub sourcing: ICP profile OR recruiter brief -> evidence-first ranked candidates.

Design principles
- Recruiter-entered MUST/NICE requirements remain source of truth.
- Semantic expansion improves discovery; it never silently changes MUST into NICE or vice versa.
- Candidate claims are based only on public GitHub evidence.
- "Missing" means "not verified in public GitHub evidence", not "candidate does not know it".
- GitHub followers/stars are supporting open-source signals, never professional seniority.
- Results are shown 10 at a time.
"""

import os, re, sys, time, base64
from collections import defaultdict, Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
import requests

# ----------------------------- GitHub API ---------------------------------

TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
API_VERSION = "2022-11-28"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": API_VERSION,
    "User-Agent": "Recruiter-GitHub-Sourcing-Engine-v18.16",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def api_get(url, params=None, raw=False):
    """Serial GitHub GET with explicit errors and rate-limit awareness."""
    try:
        r = SESSION.get(url, params=params, timeout=15)
    except requests.RequestException as e:
        print(f"\n⚠️ GitHub network error: {e}")
        return None

    if r.status_code in (403, 429):
        remaining = r.headers.get("x-ratelimit-remaining", "?")
        reset = r.headers.get("x-ratelimit-reset")
        msg = ""
        try:
            msg = r.json().get("message", "")
        except Exception:
            pass
        if remaining == "0" and reset:
            try:
                when = datetime.fromtimestamp(int(reset), tz=timezone.utc).strftime("%H:%M UTC")
                print(f"\n⚠️ GitHub rate limit reached. Resets around {when}. {msg}")
            except Exception:
                print(f"\n⚠️ GitHub rate limit reached. {msg}")
        else:
            print(f"\n⚠️ GitHub throttled this request. {msg}")
        return None

    if r.status_code == 404:
        return None
    if not r.ok:
        print(f"\n⚠️ GitHub API {r.status_code}: {r.text[:180]}")
        return None
    return r.text if raw else r.json()

def show_rate_limit():
    data = api_get("https://api.github.com/rate_limit")
    if not data:
        return
    core = data.get("resources", {}).get("core", {})
    search = data.get("resources", {}).get("search", {})
    print(f"API: {'authenticated' if TOKEN else 'unauthenticated'} | "
          f"core {core.get('remaining','?')}/{core.get('limit','?')} | "
          f"search {search.get('remaining','?')}/{search.get('limit','?')}")

# ------------------------- Technical knowledge ----------------------------

# Canonical skill -> aliases. Short aliases are matched with boundaries, never raw substrings.
SKILLS = {
    # languages
    "python": ["python", "python3"], "java": ["java"], "go": ["golang", "go language"],
    "rust": ["rust"], "c++": ["c++", "cpp"], "c#": ["c#", "csharp"],
    "javascript": ["javascript", "js"], "typescript": ["typescript", "ts"],
    "ruby": ["ruby"], "php": ["php"], "kotlin": ["kotlin"], "scala": ["scala"],
    "swift": ["swift"], "sql": ["sql"], "bash": ["bash", "shell scripting"],

    # frontend/mobile
    "react": ["react", "reactjs", "react.js"], "next.js": ["next.js", "nextjs"],
    "vue": ["vue", "vue.js"], "angular": ["angular"], "svelte": ["svelte"],
    "react native": ["react native", "react-native"], "flutter": ["flutter"],
    "ios": ["ios"], "android": ["android"],

    # backend/frameworks
    "django": ["django", "drf"], "fastapi": ["fastapi"], "flask": ["flask"],
    "spring": ["spring boot", "spring framework"], "node.js": ["node.js", "nodejs"],
    "express": ["express.js", "expressjs"], ".net": [".net", "dotnet", "asp.net"],
    "rails": ["ruby on rails", "rails"], "grpc": ["grpc"], "graphql": ["graphql"],
    "rest api": ["rest api", "restful api"], "microservices": ["microservices", "micro-services"],

    # cloud/platform/devops
    "kubernetes": ["kubernetes", "k8s", "container orchestration"],
    "docker": ["docker", "containerization", "container runtime"],
    "terraform": ["terraform", "infrastructure as code", "iac"],
    "ansible": ["ansible"], "helm": ["helm", "helm charts"],
    "argocd": ["argocd", "argo cd"], "jenkins": ["jenkins"],
    "gitops": ["gitops", "git ops"],
    "ci/cd": ["ci/cd", "continuous integration", "continuous deployment"],
    "github actions": ["github actions"], "gitlab ci": ["gitlab ci", "gitlab-ci"],
    "aws": ["aws", "amazon web services"], "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud platform"], "linux": ["linux"],
    "openshift": ["openshift", "red hat ocp", "ocp"],
    "rancher": ["rancher"], "eks": ["amazon eks", "aws eks", "eks"],
    "aks": ["azure kubernetes service", "aks"], "gke": ["google kubernetes engine", "gke"],
    "prometheus": ["prometheus"], "grafana": ["grafana"], "datadog": ["datadog"],
    "opentelemetry": ["opentelemetry", "open telemetry"],

    # VMware/private cloud/network/storage
    "vmware cloud foundation": ["vmware cloud foundation", "vcf"],
    "vsphere": ["vsphere", "esxi"], "vsan": ["vsan"],
    "nsx": ["vmware nsx", "nsx"], "sddc": ["software-defined data center", "software defined data center", "sddc"],
    "networking": ["enterprise networking", "network architecture"],
    "kubernetes networking": ["kubernetes networking", "container networking"],
    "cni": ["cni", "container network interface"], "ipam": ["ipam", "ip address management"],
    "ingress": ["ingress", "ingress controller"], "egress": ["egress"],
    "bgp": ["bgp"], "ospf": ["ospf"], "dns": ["dns"], "dhcp": ["dhcp"],
    "storage architecture": ["storage architecture", "storage infrastructure"],
    "infrastructure architecture": ["infrastructure architecture", "infrastructure architect"],

    # data
    "postgresql": ["postgresql", "postgres"], "mysql": ["mysql"], "mongodb": ["mongodb"],
    "redis": ["redis"], "elasticsearch": ["elasticsearch"], "dynamodb": ["dynamodb"],
    "cassandra": ["cassandra"], "kafka": ["apache kafka", "kafka"], "spark": ["apache spark", "spark"],
    "airflow": ["apache airflow", "airflow"], "dbt": ["dbt", "data build tool"],
    "snowflake": ["snowflake"], "databricks": ["databricks"],

    # AI/ML
    "pytorch": ["pytorch"], "tensorflow": ["tensorflow", "keras"],
    "scikit-learn": ["scikit-learn", "sklearn"], "hugging face": ["hugging face", "huggingface"],
    "llm": ["large language model", "large language models", "llm", "llms"],
    "rag": ["retrieval augmented generation", "retrieval-augmented generation", "rag"],
    "langchain": ["langchain"], "mlops": ["mlops", "ml ops"], "cuda": ["cuda"],

    # security
    "application security": ["application security", "appsec"], "cloud security": ["cloud security"],
    "kubernetes security": ["kubernetes security", "container security"],
    "iam": ["identity and access management", "iam"], "oauth": ["oauth"], "owasp": ["owasp"],
    "penetration testing": ["penetration testing", "pentesting"],

    # certifications
    "cka": ["cka", "certified kubernetes administrator"],
    "ckad": ["ckad", "certified kubernetes application developer"],
    "ccie": ["ccie"], "ccnp": ["ccnp"], "vcp-vcf": ["vcp-vcf"],
    "vcap-nv": ["vcap-nv"],

    # capability concepts
    "troubleshooting": ["troubleshooting", "problem solving", "root cause analysis", "rca"],
    "distributed systems": ["distributed systems", "distributed system"],
    "system design": ["system design", "systems design"],
    "api design": ["api", "apis", "api design", "api development", "application programming interface"],
    "asynchronous systems": ["asynchronous systems", "async processing", "asynchronous processing"],
    "observability": ["observability", "logging metrics monitoring", "monitoring and alerting"],
    "cloud infrastructure": ["cloud infrastructure", "cloud platform", "cloud environments"],
    "data modeling": ["data modeling", "data modelling"],
    "workflow orchestration": ["workflow orchestration", "workflow engine", "workflow engines"],
    "ai agents": ["ai agents", "ai agent", "agent infrastructure", "agentic"],
    "model serving": ["model serving", "model-serving", "inference serving"],
    "ai infrastructure": ["ai infrastructure", "ai platform infrastructure", "llm infrastructure"],
    "ml infrastructure": ["ml infrastructure", "ml/data infrastructure", "data/ml infrastructure"],
    "evaluation systems": ["evaluation systems", "evaluation loops", "eval systems", "evaluations"],
    "automation systems": ["automation systems", "automation platforms", "background automation"],
    "inference pipelines": ["inference pipelines", "inference pipeline"],
    "permissions": ["permissions", "approvals", "auditability", "authorization"],
    "platform engineering": ["platform engineering", "platform engineer"],
    "site reliability engineering": ["site reliability engineering", "sre"],
}

# Related concepts are DISCOVERY/EVIDENCE context, not recruiter requirement mutation.
RELATED = {
    "kubernetes": ["openshift", "rancher", "eks", "aks", "gke", "helm", "cni", "argocd"],
    "docker": ["kubernetes", "containerd", "podman"],
    "vmware cloud foundation": ["vsphere", "vsan", "nsx", "sddc"],
    "vsphere": ["vmware cloud foundation", "esxi", "vsan"],
    "vsan": ["vmware cloud foundation", "vsphere", "storage architecture"],
    "nsx": ["vmware cloud foundation", "sddc", "networking"],
    "kubernetes networking": ["cni", "ingress", "egress", "ipam", "networking"],
    "terraform": ["infrastructure as code", "pulumi", "cloudformation"],
    "platform engineering": ["kubernetes", "terraform", "helm", "argocd", "ci/cd"],
    "site reliability engineering": ["kubernetes", "prometheus", "grafana", "opentelemetry"],
    "react": ["next.js", "typescript", "javascript"],
    "node.js": ["javascript", "typescript", "express"],
    "django": ["python", "postgresql", "rest api"],
    "spring": ["java", "microservices"],
    "kafka": ["distributed systems", "spark"],
    "pytorch": ["python", "cuda", "hugging face"],
    "llm": ["rag", "hugging face", "langchain", "python"],
}

DOMAINS = {
    "PLATFORM_INFRASTRUCTURE": {
        "signals": ["kubernetes", "docker", "terraform", "helm", "gitops", "platform engineering", "cloud infrastructure", "observability", "linux"],
        "specializations": {
            "Kubernetes Platform": ["kubernetes", "helm", "openshift", "rancher", "eks", "aks", "gke"],
            "Private Cloud / VMware": ["vmware cloud foundation", "vsphere", "vsan", "nsx", "sddc"],
            "Infrastructure Automation": ["terraform", "ansible", "ci/cd", "argocd"],
            "SRE / Observability": ["site reliability engineering", "prometheus", "grafana", "opentelemetry"],
        },
    },
    "BACKEND": {
        "signals": ["python", "java", "go", "node.js", "django", "spring", "fastapi", "microservices", "grpc",
                    "distributed systems", "system design", "api design", "asynchronous systems"],
        "specializations": {
            "Distributed Backend": ["distributed systems", "microservices", "kafka", "grpc"],
            "Python Backend": ["python", "django", "fastapi", "flask"],
            "Java Backend": ["java", "spring"],
            "Go Backend": ["go", "grpc"],
        },
    },
    "FRONTEND": {
        "signals": ["react", "vue", "angular", "next.js", "javascript", "typescript", "svelte"],
        "specializations": {"Web Frontend": ["react", "vue", "angular", "next.js", "svelte", "typescript"]},
    },
    "FULLSTACK": {
        "signals": ["react", "javascript", "typescript", "node.js", "python", "java", "postgresql"],
        "specializations": {"Full Stack Web": ["react", "next.js", "node.js", "django", "spring", "postgresql"]},
    },
    "DATA": {
        "signals": ["sql", "spark", "kafka", "airflow", "dbt", "snowflake", "databricks"],
        "specializations": {"Data Engineering": ["spark", "kafka", "airflow", "dbt", "snowflake", "databricks"]},
    },
    "AI_ML": {
        "signals": ["pytorch", "tensorflow", "scikit-learn", "llm", "rag", "hugging face", "mlops",
                    "ai agents", "model serving", "ai infrastructure", "ml infrastructure",
                    "evaluation systems", "inference pipelines"],
        "specializations": {
            "ML Engineering": ["pytorch", "tensorflow", "scikit-learn", "mlops"],
            "LLM / GenAI": ["llm", "rag", "hugging face", "langchain"],
        },
    },
    "MOBILE": {
        "signals": ["swift", "kotlin", "ios", "android", "flutter", "react native"],
        "specializations": {"Mobile Engineering": ["swift", "kotlin", "ios", "android", "flutter", "react native"]},
    },
    "SECURITY": {
        "signals": ["application security", "cloud security", "kubernetes security", "iam", "owasp", "penetration testing"],
        "specializations": {"Cloud / App Security": ["application security", "cloud security", "kubernetes security", "iam", "owasp"]},
    },
}

# ---------------------------- Text matching --------------------------------

def normalize(text):
    text = (text or "").lower()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def phrase_present(text, phrase):
    """Boundary-aware phrase match. Prevents 'tf'->TensorFlow style false positives."""
    text = normalize(text)
    phrase = normalize(phrase)
    if not phrase:
        return False
    # Word-ish boundaries while preserving + # . / -
    pat = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
    return re.search(pat, text, flags=re.I) is not None

def fuzzy_token_match(text, alias, threshold=0.88):
    """Conservative typo handling for single meaningful words only."""
    alias = normalize(alias)
    if " " in alias or len(alias) < 5 or not alias.isalnum():
        return False
    words = re.findall(r"[a-z0-9+#.-]+", normalize(text))
    for word in words:
        if abs(len(word) - len(alias)) <= 2 and SequenceMatcher(None, word, alias).ratio() >= threshold:
            return True
    return False

def match_skill(text, skill, allow_fuzzy=True):
    aliases = [skill] + SKILLS.get(skill, [])
    for alias in aliases:
        if phrase_present(text, alias):
            return True, alias, "exact/alias"
    if allow_fuzzy:
        for alias in aliases:
            if fuzzy_token_match(text, alias):
                return True, alias, "typo/fuzzy"
    return False, None, None

def extract_known_skills(text, allow_fuzzy=True):
    found = []
    for skill in SKILLS:
        ok, alias, method = match_skill(text, skill, allow_fuzzy)
        if ok:
            found.append(skill)
    return found


GENERIC_WORDS = {
    "experience","years","year","strong","advanced","good","knowledge","understanding",
    "hands-on","hands","working","ability","skills","skill","required","preferred",
    "design","development","administration","deployment","solutions","similar",
    "architecture","architect","engineering","engineer","platform","senior","lead",
    "expertise","proficiency","familiarity","certification","certifications","certified","building","build","using","with","and","or",
    "company","team","initiative","opportunity","growth","ownership","quality","candidate","candidates","role",
    "hands-on","coding","code","implementation","components","systems","product","context","internal","support",
    "strong","practical","recent","prior","exposure","knowledge","curiosity","learning","agility",
    "the","a","an","of","in","for","to","on","at","from"
}

def clean_requirement_line(line):
    """Turn a recruiter bullet into a stable raw requirement phrase."""
    x = re.sub(r"^\s*[-*•\d.)]+\s*", "", line).strip()
    x = re.sub(r"\s+", " ", x)
    return x.strip(" :-")

def requirement_lines(section_text):
    return [clean_requirement_line(x) for x in section_text.splitlines()
            if clean_requirement_line(x)]

def unknown_technical_entities(section_text, known_skills):
    """
    Strict open-world extraction for technologies not in SKILLS.
    Preserve branded/camel-case/version/slash technologies (e.g. WASMEdge, eBPF/XDP,
    NebulaMesh, GitOps) without turning ordinary JD prose or industry labels into skills.
    """
    entities = []
    known_aliases = set()
    for s in known_skills:
        known_aliases.add(normalize(s))
        known_aliases.update(normalize(a) for a in SKILLS.get(s, []))

    blocked_acronyms = {"ai","ml","it","hr","api","apis","saas","sql","ui","ux"}
    blocked_words = {
        "rippling","senior","staff","product","platform","backend","infrastructure","systems",
        "engineering","engineer","company","team","initiative","context","coding","code",
        "production","quality","strong","hands-on","hands","workflows","workflow","data",
        "technical","general-purpose","languages","language","such","more","specifically",
        "adjacent","plus","recent","prior","exposure","knowledge","learning","agility"
    }

    for raw in requirement_lines(section_text):
        line = re.sub(r"\b\d{1,2}\s*(?:\+|[-–—]\s*\d{1,2})?\s*(?:years?|yrs?)\b", " ", raw, flags=re.I)

        # Remove known aliases before searching for genuinely unknown technology tokens.
        shadow = line
        for alias in sorted(known_aliases, key=len, reverse=True):
            if alias:
                shadow = re.sub(rf"(?i)(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", " ", shadow)

        pieces = re.split(r"[,;]|\s+\bor\b\s+|\s+\band\b\s+|\s+\+\s+", shadow, flags=re.I)

        for piece in pieces:
            piece = piece.strip(" -:().")
            if not (2 <= len(piece) <= 90):
                continue

            tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]*(?:/[A-Za-z0-9+#.-]+)?", piece)
            strong_tokens = []

            for tok in tokens:
                nt = normalize(tok).strip(".")
                if nt in known_aliases or nt in blocked_words or nt in blocked_acronyms:
                    continue

                camel = any(c.isupper() for c in tok[1:]) and any(c.islower() for c in tok)
                slash_tech = "/" in tok and any(c.isupper() for c in tok)
                symbolic = any(ch in "+#" for ch in tok)
                versioned = any(ch.isdigit() for ch in tok)
                upper = tok.isupper() and len(tok) >= 3 and nt not in blocked_acronyms
                branded_hyphen = "-" in tok and (camel or upper or versioned)

                if camel or slash_tech or symbolic or versioned or upper or branded_hyphen:
                    strong_tokens.append(tok.strip("."))

            if not strong_tokens:
                continue

            # Keep one adjacent noun after a branded token, e.g. "NebulaMesh Runtime".
            words = [w.strip(".") for w in tokens if normalize(w) not in blocked_words]
            for st in strong_tokens:
                try:
                    pos = words.index(st)
                except ValueError:
                    pos = -1
                phrase = st
                if pos >= 0 and pos + 1 < len(words):
                    nxt = words[pos+1]
                    if normalize(nxt) not in blocked_acronyms and len(nxt) >= 3 and nxt[0].isalpha():
                        phrase = f"{st} {nxt}"
                if normalize(phrase) not in {normalize(e) for e in entities}:
                    entities.append(phrase)

    return entities[:24]

def raw_requirement_concepts(section_text):
    """
    Keep the recruiter's own requirement wording as search context.
    This is the universal fallback when the vocabulary has never seen a technology.
    """
    concepts = []
    for line in requirement_lines(section_text):
        base = re.sub(r"\([^)]*\)", "", line).strip(" :-")
        base = re.sub(r"\b(?:strong|advanced|good|hands-on)\b", "", base, flags=re.I)
        base = re.sub(r"\s+", " ", base).strip()
        if 2 <= len(base) <= 90:
            concepts.append(base)
        for p in re.findall(r"\(([^)]{2,100})\)", line):
            for x in re.split(r"[,;/]|\s+\bor\b\s+", p, flags=re.I):
                x = x.strip()
                if 2 <= len(x) <= 60:
                    concepts.append(x)
    # stable de-dupe
    out = []
    for x in concepts:
        if normalize(x) not in [normalize(y) for y in out]:
            out.append(x)
    return out[:40]

def dynamic_term_present(text, term):
    """Conservative exact/proximity check for unknown recruiter-supplied entities."""
    term = normalize(term)
    if not term:
        return False
    if phrase_present(text, term):
        return True
    toks = [t for t in re.findall(r"[a-z0-9+#.-]+", term) if t not in GENERIC_WORDS and len(t) >= 2]
    # For multi-token unknown concepts, require all meaningful tokens close together.
    if len(toks) >= 2:
        nt = normalize(text)
        positions = []
        for tok in toks[:5]:
            m = re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", nt)
            if not m:
                return False
            positions.append(m.start())
        return max(positions) - min(positions) <= 120
    return False


def split_brief(text):
    """
    Robustly separate required vs preferred sections in recruiter-written long JDs.
    Handles headings such as:
      What you need to have / What we're looking for / Requirements / Qualifications
      What would be nice to have / Preferred qualifications / Nice to have
    Later summary sections like 'Technical Skills' do not leak back into NICE.
    """
    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""

    must_re = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:"
        r"must\s*(?:[- ]?\s*to\s*)?[- ]?\s*have|mandatory|requirements?|"
        r"minimum qualifications?|basic qualifications?|what you need to have|"
        r"what we(?:'|’)re looking for|what we are looking for|who you are"
        r")\s*:?\s*$"
    )
    nice_re = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:"
        r"nice\s*(?:[- ]?\s*to\s*)?[- ]?\s*have|preferred|preferred qualifications?|"
        r"good\s*(?:[- ]?\s*to\s*)?[- ]?\s*have|what would be nice to have|"
        r"bonus|bonus points|desired qualifications?"
        r")\s*:?\s*$"
    )
    stop_re = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:"
        r"location|locations|work location|based in|education|compensation|salary|"
        r"notice period|benefits|interview process|visa|employment type|contract type|"
        r"technical skills|skills summary|about(?: the role| us| team)?|"
        r"responsibilities|what you(?:'|’)ll do|what you will do|what’s exciting about this role|"
        r"what's exciting about this role"
        r")\s*:?\s*$"
    )

    must_pos = must_re.search(text)
    nice_pos = nice_re.search(text)

    if must_pos:
        start_m = must_pos.end()
        boundaries = [len(text)]
        if nice_pos and nice_pos.start() > start_m:
            boundaries.append(nice_pos.start())
        stop = stop_re.search(text, start_m)
        if stop and (not nice_pos or stop.start() < nice_pos.start()):
            boundaries.append(stop.start())
        must_text = text[start_m:min(boundaries)]
    else:
        # No explicit required heading: use the body up to a NICE or metadata/summary heading.
        boundaries = [len(text)]
        if nice_pos:
            boundaries.append(nice_pos.start())
        stop = stop_re.search(text)
        if stop and stop.start() > 0:
            # Ignore an opening "What you will do"/Responsibilities heading and continue after it.
            opening = text[:stop.start()].strip()
            if opening:
                boundaries.append(stop.start())
        must_text = text[:min(boundaries)]

    if nice_pos:
        start_n = nice_pos.end()
        stop = stop_re.search(text, start_n)
        end_n = stop.start() if stop else len(text)
        nice_text = text[start_n:end_n]
    else:
        nice_text = ""

    return first_line, must_text, nice_text

def extract_experience(text):
    """Return a recruiter requirement range without pretending GitHub verifies tenure."""
    # Normalize hyphen variants for ranges: 5–8, 5—8, 5-8 years.
    norm = (text or "").replace("–", "-").replace("—", "-")
    ranges = re.findall(r"\b(\d{1,2})\s*-\s*(\d{1,2})\s*(?:years?|yrs?)\b", norm, re.I)
    if ranges:
        vals = [(int(a), int(b)) for a, b in ranges if int(a) <= int(b)]
        if vals:
            # Prefer the first explicit range; long JDs often repeat it later.
            lo, hi = vals[0]
            return {"min": lo, "max": hi, "display": f"{lo}-{hi} years"}

    plus = re.findall(r"\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b", norm, re.I)
    if plus:
        lo = int(plus[0])
        return {"min": lo, "max": None, "display": f"{lo}+ years"}

    exact = re.findall(r"\b(\d{1,2})\s*(?:years?|yrs?)\b", norm, re.I)
    if exact:
        lo = int(exact[0])
        return {"min": lo, "max": None, "display": f"{lo}+ years"}

    return None

def extract_years(text):
    """Backward-compatible minimum years value."""
    exp = extract_experience(text)
    return exp["min"] if exp else None

def infer_domain(skills, title=""):
    scores = {}
    title_n = normalize(title)
    for domain, data in DOMAINS.items():
        score = 0.0
        for s in data["signals"]:
            if s in skills:
                score += 2.0
        # title hints are supporting only
        words = domain.lower().replace("_", " ").split()
        score += sum(0.5 for w in words if phrase_present(title_n, w))
        scores[domain] = score

    # Fullstack requires evidence spanning frontend + backend, not just one stack.
    front = any(s in skills for s in DOMAINS["FRONTEND"]["signals"])
    back = any(s in skills for s in DOMAINS["BACKEND"]["signals"])
    if front and back:
        scores["FULLSTACK"] += 4

    best = max(scores, key=scores.get) if scores else "GENERAL"
    if scores.get(best, 0) <= 0:
        return "GENERAL", 40, []
    total = sum(v for v in scores.values() if v > 0) or 1
    confidence = min(95, round(55 + 40 * scores[best] / total))

    specs = []
    data = DOMAINS.get(best, {})
    for name, signals in data.get("specializations", {}).items():
        hits = [s for s in signals if s in skills]
        if hits:
            specs.append((name, len(hits), hits))
    specs.sort(key=lambda x: x[1], reverse=True)
    return best, confidence, specs[:3]


def infer_requirement_orientation(must_known, nice_known, title, full_text):
    """Infer what the ROLE is about; MUST/title/body dominate NICE technologies."""
    scores = {d: 0.0 for d in DOMAINS}

    for domain, data in DOMAINS.items():
        signals = set(data.get("signals", []))
        scores[domain] += 3.0 * sum(1 for s in must_known if s in signals)
        scores[domain] += 0.65 * sum(1 for s in nice_known if s in signals)

    blob = normalize(f"{title} {full_text}")
    phrase_boosts = {
        "BACKEND": [
            "backend", "distributed systems", "distributed services", "apis",
            "asynchronous", "production services", "system design"
        ],
        "PLATFORM_INFRASTRUCTURE": [
            "platform team", "platform components", "cloud infrastructure",
            "containerized", "observability", "reliability", "production operation"
        ],
        "AI_ML": [
            "ai-powered", "ai agents", "agent infrastructure", "llm",
            "rag", "model serving", "evaluation pipelines"
        ],
        "FRONTEND": ["frontend", "front-end", "design system", "browser ui"],
        "DATA": ["data pipelines", "data engineering", "data platform", "etl"],
        "MOBILE": ["mobile", "android", "ios"],
        "SECURITY": ["security", "appsec", "cybersecurity"],
    }
    for domain, phrases in phrase_boosts.items():
        for phrase in phrases:
            if phrase_present(blob, phrase):
                scores[domain] += 1.4

    # FULLSTACK is not inferred just because JS/TS appears in NICE.
    explicit_fullstack = phrase_present(blob, "full stack") or phrase_present(blob, "full-stack")
    must_front = any(s in must_known for s in DOMAINS["FRONTEND"]["signals"])
    must_back = any(s in must_known for s in DOMAINS["BACKEND"]["signals"])
    if explicit_fullstack and must_front and must_back:
        scores["FULLSTACK"] += 6.0
    else:
        scores["FULLSTACK"] *= 0.25

    positive = {k: v for k, v in scores.items() if v > 0}
    if not positive:
        return {
            "primary": "GENERAL", "secondary": None,
            "percentages": {}, "evidence": {}
        }

    total = sum(positive.values())
    percentages = {k: round(v / total * 100) for k, v in positive.items()}
    ranked = sorted(percentages.items(), key=lambda x: x[1], reverse=True)
    return {
        "primary": ranked[0][0],
        "secondary": ranked[1][0] if len(ranked) > 1 and ranked[1][1] >= 15 else None,
        "percentages": dict(ranked),
        "evidence": {},
    }

def _domain_from_orientation(orientation):
    primary = orientation.get("primary") or "GENERAL"
    if primary == "GENERAL":
        return "GENERAL", 40
    pct = orientation.get("percentages", {}).get(primary, 0)
    return primary, min(95, 55 + pct)

def _soften_explicit_plus_lines(must_text, nice_text):
    """Move explicit bonus/strong-plus bullets out of MUST without weakening normal 'preferably' prose."""
    hard_lines, soft_lines = [], []
    for raw in must_text.splitlines():
        n = normalize(raw)
        if re.search(r"\b(?:strong plus|bonus points?|nice to have)\b", n):
            soft_lines.append(raw)
        else:
            hard_lines.append(raw)
    if soft_lines:
        nice_text = (nice_text.strip() + "\n" + "\n".join(soft_lines)).strip()
    return "\n".join(hard_lines).strip(), nice_text

def analyze_brief(text, source="BRIEF"):
    title, must_text, nice_text = split_brief(text)
    must_text, nice_text = _soften_explicit_plus_lines(must_text, nice_text)
    must_known = extract_known_skills(must_text)
    nice_known = [s for s in extract_known_skills(nice_text) if s not in must_known]

    must_unknown = unknown_technical_entities(must_text, must_known + nice_known)
    nice_unknown = unknown_technical_entities(nice_text, must_known + nice_known + must_unknown)
    nice_unknown = [x for x in nice_unknown
                    if normalize(x) not in {normalize(y) for y in must_unknown}]

    must = list(dict.fromkeys(must_known + must_unknown))
    nice = list(dict.fromkeys(nice_known + nice_unknown))

    orientation = infer_requirement_orientation(must_known, nice_known, title, text)
    domain, conf = _domain_from_orientation(orientation)

    # Specializations still use the established domain dictionary.
    _, _, specs = infer_domain(must_known, title)
    experience = extract_experience(text)
    years = experience["min"] if experience else None

    context = []
    for s in must_known:
        for rel in RELATED.get(s, []):
            if rel not in must and rel not in nice and rel not in context:
                context.append(rel)

    return {
        "source": source, "title": title, "must": must, "nice": nice,
        "must_known": must_known, "nice_known": nice_known,
        "must_unknown": must_unknown, "nice_unknown": nice_unknown,
        "raw_must_concepts": raw_requirement_concepts(must_text),
        "raw_nice_concepts": raw_requirement_concepts(nice_text),
        "must_clusters": build_requirement_clusters(must_text, must),
        "nice_clusters": build_requirement_clusters(nice_text, nice),
        "context": context[:18], "domain": domain, "domain_confidence": conf,
        "specializations": specs, "years": years, "experience": experience,
        "technical_orientation": orientation,
    }


# ---------------- Requirement clusters + directional framework intelligence ----------------

# Directional relations are intentionally NOT symmetric.
# Target is what may be inferred; source is the public GitHub evidence.
# STRONG = strong technical implication, but still displayed as inference rather than exact proof.
# ECOSYSTEM = related evidence useful for recall/ranking, never equal to an explicit requirement.
FRAMEWORK_IMPLICATIONS = {
    "kubernetes": {
        "STRONG": ["eks", "aks", "gke", "openshift"],
        "ECOSYSTEM": ["helm", "rancher", "cni", "argocd", "kubernetes networking"],
    },
    "python": {
        "STRONG": ["django", "fastapi", "flask", "pytorch", "tensorflow", "scikit-learn"],
        "ECOSYSTEM": ["airflow"],
    },
    "java": {"STRONG": ["spring"], "ECOSYSTEM": []},
    "javascript": {"STRONG": ["react", "vue", "angular", "node.js", "next.js"], "ECOSYSTEM": []},
    "react": {"STRONG": ["next.js"], "ECOSYSTEM": ["react native"]},
    "vmware cloud foundation": {
        "STRONG": [],
        "ECOSYSTEM": ["vsphere", "vsan", "nsx", "sddc"],
    },
    "kubernetes networking": {
        "STRONG": ["cni"],
        "ECOSYSTEM": ["ingress", "egress", "ipam", "nsx"],
    },
    "platform engineering": {
        "STRONG": [],
        "ECOSYSTEM": ["kubernetes", "terraform", "helm", "argocd", "ci/cd"],
    },
    "site reliability engineering": {
        "STRONG": [],
        "ECOSYSTEM": ["prometheus", "grafana", "opentelemetry", "kubernetes"],
    },
}

def _cluster_mode(raw, members):
    low = normalize(raw)
    # Recruiter alternatives: "one of", "either", or explicit OR list.
    if re.search(r"\b(?:at least )?one of\b|\beither\b", low):
        return "ANY"
    if len(members) > 1 and re.search(r"\bor\b", low):
        return "ANY"
    return "ALL"

def build_requirement_clusters(section_text, extracted_items):
    """
    Preserve recruiter bullet logic.
    ANY = one alternative is enough ("one of Python/Java/Go", "Go or Rust").
    ALL = multiple concepts are jointly desired in the same bullet.
    """
    clusters = []
    used = set()
    lines = requirement_lines(section_text)

    for raw in lines:
        members = []
        for item in extracted_items:
            if item in SKILLS:
                if match_skill(raw, item, True)[0]:
                    members.append(item)
            elif dynamic_term_present(raw, item):
                members.append(item)

        unique = []
        for member in members:
            if member not in unique:
                unique.append(member)
                used.add(member)

        if unique:
            clusters.append({
                "label": re.sub(r"\s+", " ", raw).strip(),
                "members": unique,
                "mode": _cluster_mode(raw, unique),
            })

    for item in extracted_items:
        if item not in used:
            clusters.append({"label": item, "members": [item], "mode": "ALL"})

    return clusters

def inferred_relation_for(target_skill, candidate_exact_skills):
    """
    Return strongest directional relationship supporting target_skill.
    Exact evidence is handled separately and always wins.
    """
    rel = FRAMEWORK_IMPLICATIONS.get(target_skill, {})
    for source in rel.get("STRONG", []):
        if source in candidate_exact_skills:
            return "STRONG", source
    for source in rel.get("ECOSYSTEM", []):
        if source in candidate_exact_skills:
            return "ECOSYSTEM", source
    return None, None

def cluster_coverage(clusters, direct_matches, inferred_matches=None):
    """Score recruiter requirement groups while respecting ANY/ALL semantics."""
    inferred_matches = inferred_matches or {}
    if not clusters:
        return 0.0, []

    details = []
    total = 0.0

    for cluster in clusters:
        members = cluster["members"]
        vals = []
        for member in members:
            if member in direct_matches:
                vals.append(1.0)
            elif member in inferred_matches:
                kind = inferred_matches[member][0]
                vals.append(0.70 if kind == "STRONG" else 0.35)
            else:
                vals.append(0.0)

        mode = cluster.get("mode", "ALL")
        if not vals:
            value = 0.0
        elif mode == "ANY":
            value = max(vals)
        elif len(vals) == 1:
            value = vals[0]
        else:
            # Flexible ALL: breadth matters strongly, but one missing item is not an automatic rejection.
            value = 0.30 * max(vals) + 0.70 * (sum(vals) / len(vals))

        total += value
        details.append((cluster["label"], round(value, 3), members, mode))

    return total / len(clusters), details

def repo_quality_factor(repo):
    """Downweight obvious tutorial/demo/fork-like evidence without hiding it."""
    if not repo:
        return 0.65
    if repo.get("fork"):
        return 0.20
    text = normalize(" ".join([repo.get("name") or "", repo.get("description") or ""]))
    low_signal = ["tutorial", "course", "bootcamp", "learning", "learn ", "example", "examples",
                  "demo", "boilerplate", "awesome-", "interview-prep", "practice"]
    if any(x in text for x in low_signal):
        return 0.45
    stars = repo.get("stargazers_count") or 0
    return min(1.0, 0.75 + (0.05 if stars >= 5 else 0) + (0.10 if stars >= 25 else 0))

def evidence_strength(ev, repos):
    """
    Evidence-quality score, independent of social popularity/seniority.
    Repeated authored repo evidence > one metadata mention > bio/inference.
    """
    if not ev:
        return 0.0
    repo_map = {r.get("name"): r for r in repos}
    vals = []
    repo_hits = 0

    for item in ev:
        typ = item[0]
        where = item[2] if len(item) > 2 else ""
        if typ == "REPO":
            repo_hits += 1
            vals.append(0.82 * repo_quality_factor(repo_map.get(where)))
        elif typ == "README":
            repo_hits += 1
            vals.append(0.72 * repo_quality_factor(repo_map.get(where)))
        elif typ == "BIO":
            vals.append(0.58)
        elif typ == "INFERRED_STRONG":
            vals.append(0.50)
        elif typ == "INFERRED_ECOSYSTEM":
            vals.append(0.25)

    if not vals:
        return 0.0
    base = max(vals)
    if repo_hits >= 2:
        base += 0.10
    if repo_hits >= 3:
        base += 0.05
    return min(1.0, base)


# ----------------------------- ICP analysis --------------------------------

def fetch_user(username):
    return api_get(f"https://api.github.com/users/{username}")

def fetch_user_repos(username, limit=30):
    data = api_get(f"https://api.github.com/users/{username}/repos",
                   {"sort": "updated", "direction": "desc", "per_page": min(limit, 100)})
    return data or []

def fetch_readme(owner, repo):
    try:
        r = SESSION.get(f"https://api.github.com/repos/{owner}/{repo}/readme",
                        headers={**HEADERS, "Accept": "application/vnd.github.raw+json"}, timeout=10)
        if r.status_code == 200:
            return r.text[:12000]
    except requests.RequestException:
        pass
    return ""

def repo_text(repo, readme=""):
    topics = " ".join(repo.get("topics") or [])
    return " ".join([
        repo.get("name") or "", repo.get("description") or "",
        repo.get("language") or "", topics, readme or ""
    ])


# -------------------------- Technical orientation --------------------------

ORIENTATION_SIGNALS = {
    "FRONTEND": {
        "skills": ["react","next.js","vue","angular","svelte","javascript","typescript"],
        "terms": ["frontend","front-end","ui","web app","design system","browser","component library"],
    },
    "BACKEND": {
        "skills": ["python","java","go","node.js","django","fastapi","flask","spring","grpc","rest api",
                   "microservices","postgresql","mysql","mongodb","redis"],
        "terms": ["backend","back-end","api","server","service","microservice","distributed systems"],
    },
    "PLATFORM_INFRA": {
        "skills": ["kubernetes","docker","terraform","ansible","helm","argocd","linux","aws","azure","gcp",
                   "openshift","rancher","prometheus","grafana","site reliability engineering","platform engineering"],
        "terms": ["platform","infrastructure","infra","devops","sre","cloud native","cloud-native","reliability"],
    },
    "DATA": {
        "skills": ["sql","kafka","spark","airflow","dbt","snowflake","databricks"],
        "terms": ["data engineering","data pipeline","etl","warehouse","analytics platform"],
    },
    "AI_ML": {
        "skills": ["pytorch","tensorflow","scikit-learn","hugging face","llm","rag","langchain","mlops","cuda"],
        "terms": ["machine learning","ml engineer","ai engineer","artificial intelligence","inference","model serving"],
    },
    "MOBILE": {
        "skills": ["swift","kotlin","ios","android","flutter","react native"],
        "terms": ["mobile","ios","android"],
    },
    "SECURITY": {
        "skills": ["application security","cloud security","kubernetes security","iam","oauth","owasp","penetration testing"],
        "terms": ["security","appsec","infosec","cybersecurity"],
    },
}

def technical_orientation(profile, repos):
    """
    Explain what a GitHub profile appears to be technically oriented toward.
    This is descriptive public-evidence weighting, not professional seniority.
    """
    bio = profile.get("bio") or ""
    authored = [r for r in repos if not r.get("fork")]
    repo_texts = [repo_text(r) for r in authored]
    combined = normalize(" ".join([bio] + repo_texts))

    scores = {k: 0.0 for k in ORIENTATION_SIGNALS}
    evidence = defaultdict(list)

    for orient, cfg in ORIENTATION_SIGNALS.items():
        for skill in cfg["skills"]:
            count = 0
            if match_skill(bio, skill, False)[0]:
                count += 1
                evidence[orient].append(f"bio:{skill}")
            for r, txt in zip(authored, repo_texts):
                if match_skill(txt, skill, False)[0]:
                    count += 1
                    if len(evidence[orient]) < 5:
                        evidence[orient].append(f"{r.get('name')}:{skill}")
            scores[orient] += min(count, 5) * 1.5

        for term in cfg["terms"]:
            if phrase_present(combined, term):
                scores[orient] += 1.0

    # FULLSTACK is a derived orientation only when both sides have material evidence.
    front = scores["FRONTEND"]
    back = scores["BACKEND"]
    fullstack = min(front, back) * 1.4 if front >= 3 and back >= 3 else 0.0
    scores["FULLSTACK"] = fullstack
    if fullstack:
        evidence["FULLSTACK"] = ["material frontend + backend evidence"]

    total = sum(v for v in scores.values() if v > 0)
    if total <= 0:
        return {"primary": "UNKNOWN", "secondary": None, "percentages": {}, "evidence": {}}

    percentages = {k: round(v / total * 100) for k, v in scores.items() if v > 0}
    ranked = sorted(percentages.items(), key=lambda x: x[1], reverse=True)
    primary = ranked[0][0]
    secondary = ranked[1][0] if len(ranked) > 1 and ranked[1][1] >= 15 else None

    return {
        "primary": primary,
        "secondary": secondary,
        "percentages": dict(ranked),
        "evidence": {k: evidence[k] for k in evidence},
    }

def candidate_likeness(profile, repos):
    """
    Distinguish likely individual engineers from community/content/automation accounts.
    This only affects ranking confidence; it does not judge engineering ability.
    """
    login = normalize(profile.get("login") or "")
    name = normalize(profile.get("name") or "")
    bio = normalize(profile.get("bio") or "")
    blob = " ".join([login, name, bio])

    if profile.get("type") != "User":
        return "NON_PERSON", 0.10, ["GitHub account type is not User"]

    bot_terms = ["[bot]", " bot ", "automation bot", "github actions bot"]
    if any(t in f" {blob} " for t in bot_terms):
        return "AUTOMATION", 0.10, ["automation/bot wording"]

    community_terms = ["community", "blogging site", "developer community", "open source community",
                       "collective", "academy", "training platform", "tutorials"]
    instructor_terms = ["instructor", "udemy", "students", "youtube lecturer", "trainer", "courses"]

    community_hits = [t for t in community_terms if t in blob]
    instructor_hits = [t for t in instructor_terms if t in blob]

    if community_hits:
        return "COMMUNITY_OR_CONTENT", 0.55, community_hits[:3]
    if instructor_hits:
        return "INSTRUCTOR_OR_CONTENT", 0.72, instructor_hits[:3]

    # Normal individual account.
    return "INDIVIDUAL", 1.00, []


def profile_identity(username):
    """
    Convert an ideal GitHub profile into a recruiter-style capability bar.
    Core stack = repeated/high-confidence public evidence.
    Supporting stack = useful adjacent evidence.
    Goal is meet/exceed/close-enough capability, never human cloning.
    """
    profile = fetch_user(username)
    if not profile or profile.get("type") != "User":
        return None

    repos = fetch_user_repos(username, 40)
    authored = [r for r in repos if not r.get("fork")]
    bio = profile.get("bio") or ""

    repo_counts = Counter()
    repo_quality = defaultdict(float)
    bio_hits = set(extract_known_skills(bio, allow_fuzzy=False))

    for r in authored:
        txt = repo_text(r)
        found = extract_known_skills(txt, allow_fuzzy=False)
        quality = repo_quality_factor(r)
        for s in found:
            repo_counts[s] += 1
            repo_quality[s] += quality

    all_skills = set(repo_counts) | bio_hits
    if not all_skills:
        return None

    domain, conf, specs = infer_domain(list(all_skills), bio)
    orientation = technical_orientation(profile, repos)
    domain_signals = set(DOMAINS.get(domain, {}).get("signals", []))

    def icp_weight(skill):
        repeated = min(repo_counts.get(skill, 0), 6)
        quality = min(repo_quality.get(skill, 0.0), 5.0)
        bio_bonus = 1.0 if skill in bio_hits else 0.0
        domain_bonus = 0.8 if skill in domain_signals else 0.0
        return repeated * 2.4 + quality + bio_bonus + domain_bonus

    ranked = sorted(all_skills, key=lambda s: (icp_weight(s), repo_counts.get(s, 0)), reverse=True)
    top_weight = icp_weight(ranked[0]) if ranked else 0

    # Core requires repeated evidence or explicit bio evidence.
    # One-off technologies stay SUPPORTING rather than becoming synthetic MUSTs.
    core = []
    for s in ranked:
        count = repo_counts.get(s, 0)
        if count >= 2 or s in bio_hits:
            core.append(s)
        if len(core) >= 5:
            break

    # Sparse public profile fallback: only ensure at least one usable core signal.
    if not core and ranked:
        core = [ranked[0]]

    supporting = [s for s in ranked if s not in core][:7]

    context = []
    for s in core:
        context.extend(RELATED.get(s, []))
    for s in supporting[:4]:
        context.extend(RELATED.get(s, [])[:2])
    context = list(dict.fromkeys(x for x in context if x not in core and x not in supporting))[:14]

    spec_names = [x[0] for x in specs[:2]]
    target_label = " / ".join(spec_names) if spec_names else domain.replace("_", " ").title()

    return {
        "source": "ICP",
        "title": f"{target_label} capability profile inferred from @{username}",
        "must": core,
        "nice": supporting,
        "must_known": core,
        "nice_known": supporting,
        "must_unknown": [],
        "nice_unknown": [],
        "raw_must_concepts": core,
        "raw_nice_concepts": supporting,
        "must_clusters": [{"label": x, "members": [x]} for x in core],
        "nice_clusters": [{"label": x, "members": [x]} for x in supporting],
        "context": context,
        "domain": domain,
        "domain_confidence": conf,
        "specializations": specs,
        "years": None,
        "icp_profile": profile,
        "icp_username": username.lower(),
        "icp_repos": repos,
        "icp_evidence_counts": dict(repo_counts),
        "technical_orientation": orientation,
        "icp_mode_note": "Reference bar: candidates may meet, exceed, or closely match the core stack; cloning is not required.",
    }

# -------------------------- Location intelligence --------------------------

import unicodedata

# Country-first location knowledge. This is intentionally data, not branching logic:
# adding a country/city does not require changing the matching algorithm.
COUNTRY_DATA = {
    "united states": {
        "aliases": ["usa", "us", "u.s.", "united states", "united states of america"],
        "cities": ["new york","san francisco","san jose","seattle","austin","boston","chicago","denver",
                   "los angeles","san diego","portland","atlanta","miami","dallas","houston","phoenix",
                   "salt lake city","raleigh","charlotte","washington dc","philadelphia","detroit",
                   "minneapolis","pittsburgh","nashville","orlando","tampa","columbus","indianapolis",
                   "kansas city","st louis","las vegas","baltimore","richmond","madison","boulder",
                   "palo alto","mountain view","sunnyvale","redwood city","cupertino"],
    },
    "canada": {
        "aliases": ["canada", "ca"],
        "cities": ["toronto","vancouver","montreal","ottawa","calgary","edmonton","waterloo","quebec city",
                   "halifax","winnipeg","victoria"],
    },
    "united kingdom": {
        "aliases": ["uk","u.k.","united kingdom","great britain","britain"],
        "cities": ["london","manchester","birmingham","edinburgh","glasgow","bristol","cambridge","oxford",
                   "reading","leeds","liverpool","sheffield","nottingham","cardiff","belfast","brighton"],
    },
    "india": {
        "aliases": ["india","bharat"],
        "cities": ["bengaluru","bangalore","mumbai","pune","hyderabad","delhi","new delhi","gurgaon","gurugram",
                   "noida","greater noida","chennai","kolkata","ahmedabad","kochi","cochin","thiruvananthapuram",
                   "trivandrum","jaipur","indore","chandigarh","mohali","bhubaneswar","coimbatore","mysuru","mysore",
                   "nagpur","surat","vadodara","lucknow"],
    },
    "germany": {
        "aliases": ["germany","deutschland"],
        "cities": ["berlin","munich","münchen","hamburg","frankfurt","cologne","köln","düsseldorf","stuttgart",
                   "leipzig","dresden","nuremberg","hannover"],
    },
    "france": {
        "aliases": ["france"],
        "cities": ["paris","lyon","toulouse","marseille","lille","bordeaux","nantes","nice","grenoble"],
    },
    "spain": {
        "aliases": ["spain","españa"],
        "cities": ["madrid","barcelona","valencia","seville","sevilla","malaga","málaga","bilbao","zaragoza"],
    },
    "italy": {
        "aliases": ["italy","italia"],
        "cities": ["milan","milano","rome","roma","turin","torino","bologna","florence","firenze","naples","napoli"],
    },
    "netherlands": {
        "aliases": ["netherlands","holland"],
        "cities": ["amsterdam","rotterdam","the hague","den haag","utrecht","eindhoven","delft"],
    },
    "ireland": {
        "aliases": ["ireland","republic of ireland"],
        "cities": ["dublin","cork","galway","limerick"],
    },
    "sweden": {
        "aliases": ["sweden","sverige"],
        "cities": ["stockholm","gothenburg","göteborg","malmö","malmo","uppsala"],
    },
    "norway": {
        "aliases": ["norway","norge"],
        "cities": ["oslo","bergen","trondheim","stavanger"],
    },
    "denmark": {
        "aliases": ["denmark","danmark"],
        "cities": ["copenhagen","københavn","aarhus","odense","aalborg"],
    },
    "finland": {
        "aliases": ["finland","suomi"],
        "cities": ["helsinki","espoo","tampere","turku","oulu"],
    },
    "switzerland": {
        "aliases": ["switzerland","schweiz","suisse"],
        "cities": ["zurich","zürich","geneva","genève","lausanne","basel","bern"],
    },
    "austria": {
        "aliases": ["austria","österreich"],
        "cities": ["vienna","wien","graz","linz","salzburg","innsbruck"],
    },
    "poland": {
        "aliases": ["poland","polska"],
        "cities": ["warsaw","warszawa","krakow","kraków","wroclaw","wrocław","gdansk","gdańsk","poznan","poznań","lodz","łódź"],
    },
    "czechia": {
        "aliases": ["czechia","czech republic"],
        "cities": ["prague","praha","brno","ostrava"],
    },
    "portugal": {
        "aliases": ["portugal"],
        "cities": ["lisbon","lisboa","porto","braga","coimbra"],
    },
    "belgium": {
        "aliases": ["belgium"],
        "cities": ["brussels","bruxelles","antwerp","antwerpen","ghent","gent","leuven"],
    },
    "romania": {
        "aliases": ["romania"],
        "cities": ["bucharest","bucurești","cluj-napoca","cluj","iasi","iași","timisoara","timișoara"],
    },
    "estonia": {"aliases": ["estonia"], "cities": ["tallinn","tartu"]},
    "lithuania": {"aliases": ["lithuania"], "cities": ["vilnius","kaunas"]},
    "latvia": {"aliases": ["latvia"], "cities": ["riga"]},
    "greece": {"aliases": ["greece"], "cities": ["athens","thessaloniki"]},
    "hungary": {"aliases": ["hungary"], "cities": ["budapest","debrecen"]},
    "serbia": {"aliases": ["serbia"], "cities": ["belgrade","novi sad"]},
    "croatia": {"aliases": ["croatia"], "cities": ["zagreb","split"]},
    "ukraine": {"aliases": ["ukraine"], "cities": ["kyiv","kiev","lviv","kharkiv","odesa","odessa"]},

    "japan": {
        "aliases": ["japan","nippon","nihon"],
        "cities": ["tokyo","yokohama","osaka","kyoto","nagoya","fukuoka","sapporo","kobe","sendai"],
    },
    "china": {
        "aliases": ["china","prc","people's republic of china"],
        "cities": ["beijing","shanghai","shenzhen","guangzhou","hangzhou","chengdu","wuhan","nanjing","suzhou","xian","xi'an"],
    },
    "singapore": {"aliases": ["singapore","sg"], "cities": ["singapore"]},
    "south korea": {
        "aliases": ["south korea","korea","republic of korea"],
        "cities": ["seoul","busan","incheon","daejeon","suwon"],
    },
    "taiwan": {
        "aliases": ["taiwan"],
        "cities": ["taipei","new taipei","hsinchu","taichung","kaohsiung"],
    },
    "vietnam": {
        "aliases": ["vietnam","viet nam"],
        "cities": ["ho chi minh city","hcmc","saigon","hanoi","da nang","danang"],
    },
    "thailand": {"aliases": ["thailand"], "cities": ["bangkok","chiang mai","phuket"]},
    "malaysia": {
        "aliases": ["malaysia"],
        "cities": ["kuala lumpur","petaling jaya","cyberjaya","penang","george town","johor bahru"],
    },
    "indonesia": {
        "aliases": ["indonesia"],
        "cities": ["jakarta","bandung","surabaya","yogyakarta","bali","denpasar"],
    },
    "philippines": {
        "aliases": ["philippines"],
        "cities": ["manila","makati","taguig","quezon city","cebu","davao"],
    },

    "brazil": {
        "aliases": ["brazil","brasil"],
        "cities": ["são paulo","sao paulo","rio de janeiro","belo horizonte","brasilia","brasília","curitiba",
                   "porto alegre","recife","florianopolis","florianópolis","campinas","salvador"],
    },
    "mexico": {
        "aliases": ["mexico","méxico"],
        "cities": ["mexico city","ciudad de mexico","cdmx","guadalajara","monterrey","queretaro","querétaro",
                   "puebla","tijuana","merida","mérida"],
    },
    "argentina": {
        "aliases": ["argentina"],
        "cities": ["buenos aires","cordoba","córdoba","rosario","mendoza"],
    },
    "colombia": {
        "aliases": ["colombia"],
        "cities": ["bogota","bogotá","medellin","medellín","cali","barranquilla"],
    },
    "chile": {"aliases": ["chile"], "cities": ["santiago","valparaiso","valparaíso","concepcion","concepción"]},
    "peru": {"aliases": ["peru","perú"], "cities": ["lima","arequipa"]},
    "uruguay": {"aliases": ["uruguay"], "cities": ["montevideo"]},
    "costa rica": {"aliases": ["costa rica"], "cities": ["san jose costa rica","san josé costa rica"]},

    "south africa": {
        "aliases": ["south africa","rsa"],
        "cities": ["johannesburg","cape town","pretoria","durban","stellenbosch"],
    },
    "nigeria": {"aliases": ["nigeria"], "cities": ["lagos","abuja","ibadan"]},
    "egypt": {"aliases": ["egypt"], "cities": ["cairo","alexandria","giza"]},
    "kenya": {"aliases": ["kenya"], "cities": ["nairobi","mombasa"]},
    "ghana": {"aliases": ["ghana"], "cities": ["accra","kumasi"]},
    "morocco": {"aliases": ["morocco"], "cities": ["casablanca","rabat","marrakesh","marrakech"]},
    "tunisia": {"aliases": ["tunisia"], "cities": ["tunis"]},
    "rwanda": {"aliases": ["rwanda"], "cities": ["kigali"]},

    "australia": {
        "aliases": ["australia","au"],
        "cities": ["sydney","melbourne","brisbane","perth","adelaide","canberra","gold coast","newcastle"],
    },
    "new zealand": {
        "aliases": ["new zealand","nz"],
        "cities": ["auckland","wellington","christchurch","hamilton","dunedin"],
    },

    "united arab emirates": {
        "aliases": ["uae","u.a.e.","united arab emirates","emirates"],
        "cities": ["dubai","abu dhabi","sharjah"],
    },
    "saudi arabia": {
        "aliases": ["saudi arabia","ksa","kingdom of saudi arabia","saudi"],
        "cities": ["riyadh","jeddah","dammam","khobar","al khobar"],
    },
    "israel": {
        "aliases": ["israel"],
        "cities": ["tel aviv","jerusalem","haifa","herzliya","beer sheva","beersheba"],
    },
    "qatar": {"aliases": ["qatar"], "cities": ["doha"]},
    "bahrain": {"aliases": ["bahrain"], "cities": ["manama"]},
    "kuwait": {"aliases": ["kuwait"], "cities": ["kuwait city"]},
    "oman": {"aliases": ["oman"], "cities": ["muscat"]},
    "turkey": {
        "aliases": ["turkey","türkiye","turkiye"],
        "cities": ["istanbul","ankara","izmir"],
    },
}


# Recruiter-friendly macro regions. These are sourcing regions, not legal/political classifications.
REGION_DATA = {
    "europe": {
        "aliases": ["europe", "eu region", "european region"],
        "countries": [
            "germany","france","spain","italy","netherlands","ireland","sweden","norway","denmark",
            "finland","switzerland","austria","poland","czechia","portugal","belgium","romania",
            "estonia","lithuania","latvia","greece","hungary","serbia","croatia","ukraine",
            "united kingdom"
        ],
    },
    "dach": {
        "aliases": ["dach"],
        "countries": ["germany","austria","switzerland"],
    },
    "emea": {
        "aliases": ["emea", "europe middle east africa"],
        "countries": [
            "germany","france","spain","italy","netherlands","ireland","sweden","norway","denmark",
            "finland","switzerland","austria","poland","czechia","portugal","belgium","romania",
            "estonia","lithuania","latvia","greece","hungary","serbia","croatia","ukraine","united kingdom",
            "united arab emirates","saudi arabia","israel","qatar","bahrain","kuwait","oman","turkey",
            "south africa","nigeria","egypt","kenya","ghana","morocco","tunisia","rwanda"
        ],
    },
    "middle east": {
        "aliases": ["middle east", "mena middle east"],
        "countries": [
            "united arab emirates","saudi arabia","israel","qatar","bahrain","kuwait","oman","turkey","egypt"
        ],
    },
    "apac": {
        "aliases": ["apac", "asia pacific", "asia-pacific"],
        "countries": [
            "india","japan","china","singapore","south korea","taiwan","vietnam","thailand","malaysia",
            "indonesia","philippines","australia","new zealand"
        ],
    },
    "asia": {
        "aliases": ["asia"],
        "countries": [
            "india","japan","china","singapore","south korea","taiwan","vietnam","thailand","malaysia",
            "indonesia","philippines"
        ],
    },
    "latam": {
        "aliases": ["latam", "latin america", "latin-america"],
        "countries": ["brazil","mexico","argentina","colombia","chile","peru","uruguay","costa rica"],
    },
    "africa": {
        "aliases": ["africa"],
        "countries": ["south africa","nigeria","egypt","kenya","ghana","morocco","tunisia","rwanda"],
    },
    "oceania": {
        "aliases": ["oceania"],
        "countries": ["australia","new zealand"],
    },
    "north america": {
        "aliases": ["north america", "na"],
        "countries": ["united states","canada","mexico"],
    },
}

COUNTRY_TO_REGIONS = defaultdict(list)
REGION_ALIAS_INDEX = {}


# Common city/metro aliases. Compact matching also handles "Sanfrancisco".
CITY_ALIASES = {
    "san francisco": ["san francisco","sf","sf bay area","bay area","san francisco bay area","sanfrancisco"],
    "new york": ["new york","new york city","nyc","manhattan"],
    "washington dc": ["washington dc","washington d.c.","dc","d.c."],
    "bengaluru": ["bengaluru","bangalore"],
    "gurgaon": ["gurgaon","gurugram"],
    "ho chi minh city": ["ho chi minh city","hcmc","saigon"],
    "mexico city": ["mexico city","ciudad de mexico","ciudad de méxico","cdmx"],
    "são paulo": ["são paulo","sao paulo"],
    "krakow": ["krakow","kraków"],
    "munich": ["munich","münchen"],
    "cologne": ["cologne","köln"],
    "zurich": ["zurich","zürich"],
    "copenhagen": ["copenhagen","københavn"],
    "kyiv": ["kyiv","kiev"],
}

# Metro/commutable expansion. These are curated practical metro relationships,
# not a claim of mathematically exact 50 km distance.
NEARBY_CITIES = {
    "san francisco": ["oakland","berkeley","san mateo","redwood city","palo alto","south san francisco","daly city"],
    "new york": ["jersey city","hoboken","newark","brooklyn","queens"],
    "london": ["reading","watford","slough","guildford","cambridge","oxford"],
    "bengaluru": ["whitefield","electronic city"],
    "delhi": ["new delhi","gurgaon","gurugram","noida","greater noida","faridabad","ghaziabad"],
    "mumbai": ["navi mumbai","thane","panvel"],
    "toronto": ["mississauga","brampton","markham","vaughan"],
    "vancouver": ["burnaby","richmond","surrey"],
    "sydney": ["parramatta","north sydney"],
    "melbourne": ["richmond victoria","southbank"],
    "tokyo": ["yokohama","kawasaki","chiba","saitama"],
    "berlin": ["potsdam"],
    "paris": ["boulogne-billancourt","saint-denis","la défense","la defense"],
    "são paulo": ["campinas","barueri","osasco"],
    "dubai": ["sharjah","ajman"],
    "riyadh": [],
}

def _loc_ascii(text):
    """Accent-insensitive, punctuation-tolerant normalized location."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def _loc_compact(text):
    """Also allows Sanfrancisco -> San Francisco matching."""
    return re.sub(r"[^a-z0-9]", "", _loc_ascii(text))

def _loc_contains(location, term):
    loc_n, term_n = _loc_ascii(location), _loc_ascii(term)
    if not loc_n or not term_n:
        return False
    if phrase_present(loc_n, term_n):
        return True
    # Compact form is only used for meaningful terms, avoiding tiny alias accidents.
    return len(_loc_compact(term_n)) >= 4 and _loc_compact(term_n) in _loc_compact(loc_n)


# ------------------------ Planet-wide location augmentation ------------------------
# Static ISO-country and IANA-timezone data are embedded so this file needs no extra package install.
WORLD_COUNTRY_RECORDS = [('AD', 'AND', 'andorra', ['Andorra', 'Principality of Andorra', 'AND']),
 ('AE', 'ARE', 'united arab emirates', ['United Arab Emirates', 'ARE']),
 ('AF', 'AFG', 'afghanistan', ['Afghanistan', 'Islamic Republic of Afghanistan', 'AFG']),
 ('AG', 'ATG', 'antigua and barbuda', ['Antigua and Barbuda', 'ATG']),
 ('AI', 'AIA', 'anguilla', ['Anguilla', 'AIA']),
 ('AL', 'ALB', 'albania', ['Albania', 'Republic of Albania', 'ALB']),
 ('AM', 'ARM', 'armenia', ['Armenia', 'Republic of Armenia', 'ARM']),
 ('AO', 'AGO', 'angola', ['Angola', 'Republic of Angola', 'AGO']),
 ('AQ', 'ATA', 'antarctica', ['Antarctica', 'ATA']),
 ('AR', 'ARG', 'argentina', ['Argentina', 'Argentine Republic', 'ARG']),
 ('AS', 'ASM', 'american samoa', ['American Samoa', 'ASM']),
 ('AT', 'AUT', 'austria', ['Austria', 'Republic of Austria', 'AUT']),
 ('AU', 'AUS', 'australia', ['Australia', 'AUS']),
 ('AW', 'ABW', 'aruba', ['Aruba', 'ABW']),
 ('AX', 'ALA', 'åland islands', ['Åland Islands', 'ALA']),
 ('AZ', 'AZE', 'azerbaijan', ['Azerbaijan', 'Republic of Azerbaijan', 'AZE']),
 ('BA', 'BIH', 'bosnia and herzegovina', ['Bosnia and Herzegovina', 'Republic of Bosnia and Herzegovina', 'BIH']),
 ('BB', 'BRB', 'barbados', ['Barbados', 'BRB']),
 ('BD', 'BGD', 'bangladesh', ['Bangladesh', "People's Republic of Bangladesh", 'BGD']),
 ('BE', 'BEL', 'belgium', ['Belgium', 'Kingdom of Belgium', 'BEL']),
 ('BF', 'BFA', 'burkina faso', ['Burkina Faso', 'BFA']),
 ('BG', 'BGR', 'bulgaria', ['Bulgaria', 'Republic of Bulgaria', 'BGR']),
 ('BH', 'BHR', 'bahrain', ['Bahrain', 'Kingdom of Bahrain', 'BHR']),
 ('BI', 'BDI', 'burundi', ['Burundi', 'Republic of Burundi', 'BDI']),
 ('BJ', 'BEN', 'benin', ['Benin', 'Republic of Benin', 'BEN']),
 ('BL', 'BLM', 'saint barthélemy', ['Saint Barthélemy', 'BLM']),
 ('BM', 'BMU', 'bermuda', ['Bermuda', 'BMU']),
 ('BN', 'BRN', 'brunei', ['Brunei Darussalam', 'BRN']),
 ('BO', 'BOL', 'bolivia', ['Bolivia, Plurinational State of', 'Plurinational State of Bolivia', 'Bolivia', 'BOL']),
 ('BQ', 'BES', 'bonaire, sint eustatius and saba', ['Bonaire, Sint Eustatius and Saba', 'BES']),
 ('BR', 'BRA', 'brazil', ['Brazil', 'Federative Republic of Brazil', 'BRA']),
 ('BS', 'BHS', 'bahamas', ['Bahamas', 'Commonwealth of the Bahamas', 'BHS']),
 ('BT', 'BTN', 'bhutan', ['Bhutan', 'Kingdom of Bhutan', 'BTN']),
 ('BV', 'BVT', 'bouvet island', ['Bouvet Island', 'BVT']),
 ('BW', 'BWA', 'botswana', ['Botswana', 'Republic of Botswana', 'BWA']),
 ('BY', 'BLR', 'belarus', ['Belarus', 'Republic of Belarus', 'BLR']),
 ('BZ', 'BLZ', 'belize', ['Belize', 'BLZ']),
 ('CA', 'CAN', 'canada', ['Canada', 'CAN']),
 ('CC', 'CCK', 'cocos (keeling) islands', ['Cocos (Keeling) Islands', 'CCK']),
 ('CD', 'COD', 'democratic republic of the congo', ['Congo, The Democratic Republic of the', 'COD']),
 ('CF', 'CAF', 'central african republic', ['Central African Republic', 'CAF']),
 ('CG', 'COG', 'republic of the congo', ['Congo', 'Republic of the Congo', 'COG']),
 ('CH', 'CHE', 'switzerland', ['Switzerland', 'Swiss Confederation', 'CHE']),
 ('CI', 'CIV', "cote d'ivoire", ["Côte d'Ivoire", "Republic of Côte d'Ivoire", 'CIV']),
 ('CK', 'COK', 'cook islands', ['Cook Islands', 'COK']),
 ('CL', 'CHL', 'chile', ['Chile', 'Republic of Chile', 'CHL']),
 ('CM', 'CMR', 'cameroon', ['Cameroon', 'Republic of Cameroon', 'CMR']),
 ('CN', 'CHN', 'china', ['China', "People's Republic of China", 'CHN']),
 ('CO', 'COL', 'colombia', ['Colombia', 'Republic of Colombia', 'COL']),
 ('CR', 'CRI', 'costa rica', ['Costa Rica', 'Republic of Costa Rica', 'CRI']),
 ('CU', 'CUB', 'cuba', ['Cuba', 'Republic of Cuba', 'CUB']),
 ('CV', 'CPV', 'cape verde', ['Cabo Verde', 'Republic of Cabo Verde', 'CPV']),
 ('CW', 'CUW', 'curaçao', ['Curaçao', 'CUW']),
 ('CX', 'CXR', 'christmas island', ['Christmas Island', 'CXR']),
 ('CY', 'CYP', 'cyprus', ['Cyprus', 'Republic of Cyprus', 'CYP']),
 ('CZ', 'CZE', 'czechia', ['Czechia', 'Czech Republic', 'CZE']),
 ('DE', 'DEU', 'germany', ['Germany', 'Federal Republic of Germany', 'DEU']),
 ('DJ', 'DJI', 'djibouti', ['Djibouti', 'Republic of Djibouti', 'DJI']),
 ('DK', 'DNK', 'denmark', ['Denmark', 'Kingdom of Denmark', 'DNK']),
 ('DM', 'DMA', 'dominica', ['Dominica', 'Commonwealth of Dominica', 'DMA']),
 ('DO', 'DOM', 'dominican republic', ['Dominican Republic', 'DOM']),
 ('DZ', 'DZA', 'algeria', ['Algeria', "People's Democratic Republic of Algeria", 'DZA']),
 ('EC', 'ECU', 'ecuador', ['Ecuador', 'Republic of Ecuador', 'ECU']),
 ('EE', 'EST', 'estonia', ['Estonia', 'Republic of Estonia', 'EST']),
 ('EG', 'EGY', 'egypt', ['Egypt', 'Arab Republic of Egypt', 'EGY']),
 ('EH', 'ESH', 'western sahara', ['Western Sahara', 'ESH']),
 ('ER', 'ERI', 'eritrea', ['Eritrea', 'the State of Eritrea', 'ERI']),
 ('ES', 'ESP', 'spain', ['Spain', 'Kingdom of Spain', 'ESP']),
 ('ET', 'ETH', 'ethiopia', ['Ethiopia', 'Federal Democratic Republic of Ethiopia', 'ETH']),
 ('FI', 'FIN', 'finland', ['Finland', 'Republic of Finland', 'FIN']),
 ('FJ', 'FJI', 'fiji', ['Fiji', 'Republic of Fiji', 'FJI']),
 ('FK', 'FLK', 'falkland islands (malvinas)', ['Falkland Islands (Malvinas)', 'FLK']),
 ('FM', 'FSM', 'micronesia, federated states of', ['Micronesia, Federated States of', 'Federated States of Micronesia', 'FSM']),
 ('FO', 'FRO', 'faroe islands', ['Faroe Islands', 'FRO']),
 ('FR', 'FRA', 'france', ['France', 'French Republic', 'FRA']),
 ('GA', 'GAB', 'gabon', ['Gabon', 'Gabonese Republic', 'GAB']),
 ('GB', 'GBR', 'united kingdom', ['United Kingdom', 'United Kingdom of Great Britain and Northern Ireland', 'GBR']),
 ('GD', 'GRD', 'grenada', ['Grenada', 'GRD']),
 ('GE', 'GEO', 'georgia', ['Georgia', 'GEO']),
 ('GF', 'GUF', 'french guiana', ['French Guiana', 'GUF']),
 ('GG', 'GGY', 'guernsey', ['Guernsey', 'GGY']),
 ('GH', 'GHA', 'ghana', ['Ghana', 'Republic of Ghana', 'GHA']),
 ('GI', 'GIB', 'gibraltar', ['Gibraltar', 'GIB']),
 ('GL', 'GRL', 'greenland', ['Greenland', 'GRL']),
 ('GM', 'GMB', 'gambia', ['Gambia', 'Republic of the Gambia', 'GMB']),
 ('GN', 'GIN', 'guinea', ['Guinea', 'Republic of Guinea', 'GIN']),
 ('GP', 'GLP', 'guadeloupe', ['Guadeloupe', 'GLP']),
 ('GQ', 'GNQ', 'equatorial guinea', ['Equatorial Guinea', 'Republic of Equatorial Guinea', 'GNQ']),
 ('GR', 'GRC', 'greece', ['Greece', 'Hellenic Republic', 'GRC']),
 ('GS', 'SGS', 'south georgia and the south sandwich islands', ['South Georgia and the South Sandwich Islands', 'SGS']),
 ('GT', 'GTM', 'guatemala', ['Guatemala', 'Republic of Guatemala', 'GTM']),
 ('GU', 'GUM', 'guam', ['Guam', 'GUM']),
 ('GW', 'GNB', 'guinea-bissau', ['Guinea-Bissau', 'Republic of Guinea-Bissau', 'GNB']),
 ('GY', 'GUY', 'guyana', ['Guyana', 'Republic of Guyana', 'GUY']),
 ('HK', 'HKG', 'hong kong', ['Hong Kong', 'Hong Kong Special Administrative Region of China', 'HKG']),
 ('HM', 'HMD', 'heard island and mcdonald islands', ['Heard Island and McDonald Islands', 'HMD']),
 ('HN', 'HND', 'honduras', ['Honduras', 'Republic of Honduras', 'HND']),
 ('HR', 'HRV', 'croatia', ['Croatia', 'Republic of Croatia', 'HRV']),
 ('HT', 'HTI', 'haiti', ['Haiti', 'Republic of Haiti', 'HTI']),
 ('HU', 'HUN', 'hungary', ['Hungary', 'HUN']),
 ('ID', 'IDN', 'indonesia', ['Indonesia', 'Republic of Indonesia', 'IDN']),
 ('IE', 'IRL', 'ireland', ['Ireland', 'IRL']),
 ('IL', 'ISR', 'israel', ['Israel', 'State of Israel', 'ISR']),
 ('IM', 'IMN', 'isle of man', ['Isle of Man', 'IMN']),
 ('IN', 'IND', 'india', ['India', 'Republic of India', 'IND']),
 ('IO', 'IOT', 'british indian ocean territory', ['British Indian Ocean Territory', 'IOT']),
 ('IQ', 'IRQ', 'iraq', ['Iraq', 'Republic of Iraq', 'IRQ']),
 ('IR', 'IRN', 'iran', ['Iran, Islamic Republic of', 'Islamic Republic of Iran', 'Iran', 'IRN']),
 ('IS', 'ISL', 'iceland', ['Iceland', 'Republic of Iceland', 'ISL']),
 ('IT', 'ITA', 'italy', ['Italy', 'Italian Republic', 'ITA']),
 ('JE', 'JEY', 'jersey', ['Jersey', 'JEY']),
 ('JM', 'JAM', 'jamaica', ['Jamaica', 'JAM']),
 ('JO', 'JOR', 'jordan', ['Jordan', 'Hashemite Kingdom of Jordan', 'JOR']),
 ('JP', 'JPN', 'japan', ['Japan', 'JPN']),
 ('KE', 'KEN', 'kenya', ['Kenya', 'Republic of Kenya', 'KEN']),
 ('KG', 'KGZ', 'kyrgyzstan', ['Kyrgyzstan', 'Kyrgyz Republic', 'KGZ']),
 ('KH', 'KHM', 'cambodia', ['Cambodia', 'Kingdom of Cambodia', 'KHM']),
 ('KI', 'KIR', 'kiribati', ['Kiribati', 'Republic of Kiribati', 'KIR']),
 ('KM', 'COM', 'comoros', ['Comoros', 'Union of the Comoros', 'COM']),
 ('KN', 'KNA', 'saint kitts and nevis', ['Saint Kitts and Nevis', 'KNA']),
 ('KP', 'PRK', 'north korea', ["Korea, Democratic People's Republic of", "Democratic People's Republic of Korea", 'North Korea', 'PRK']),
 ('KR', 'KOR', 'south korea', ['Korea, Republic of', 'South Korea', 'KOR']),
 ('KW', 'KWT', 'kuwait', ['Kuwait', 'State of Kuwait', 'KWT']),
 ('KY', 'CYM', 'cayman islands', ['Cayman Islands', 'CYM']),
 ('KZ', 'KAZ', 'kazakhstan', ['Kazakhstan', 'Republic of Kazakhstan', 'KAZ']),
 ('LA', 'LAO', 'laos', ["Lao People's Democratic Republic", 'Laos', 'LAO']),
 ('LB', 'LBN', 'lebanon', ['Lebanon', 'Lebanese Republic', 'LBN']),
 ('LC', 'LCA', 'saint lucia', ['Saint Lucia', 'LCA']),
 ('LI', 'LIE', 'liechtenstein', ['Liechtenstein', 'Principality of Liechtenstein', 'LIE']),
 ('LK', 'LKA', 'sri lanka', ['Sri Lanka', 'Democratic Socialist Republic of Sri Lanka', 'LKA']),
 ('LR', 'LBR', 'liberia', ['Liberia', 'Republic of Liberia', 'LBR']),
 ('LS', 'LSO', 'lesotho', ['Lesotho', 'Kingdom of Lesotho', 'LSO']),
 ('LT', 'LTU', 'lithuania', ['Lithuania', 'Republic of Lithuania', 'LTU']),
 ('LU', 'LUX', 'luxembourg', ['Luxembourg', 'Grand Duchy of Luxembourg', 'LUX']),
 ('LV', 'LVA', 'latvia', ['Latvia', 'Republic of Latvia', 'LVA']),
 ('LY', 'LBY', 'libya', ['Libya', 'LBY']),
 ('MA', 'MAR', 'morocco', ['Morocco', 'Kingdom of Morocco', 'MAR']),
 ('MC', 'MCO', 'monaco', ['Monaco', 'Principality of Monaco', 'MCO']),
 ('MD', 'MDA', 'moldova', ['Moldova, Republic of', 'Republic of Moldova', 'Moldova', 'MDA']),
 ('ME', 'MNE', 'montenegro', ['Montenegro', 'MNE']),
 ('MF', 'MAF', 'saint martin (french part)', ['Saint Martin (French part)', 'MAF']),
 ('MG', 'MDG', 'madagascar', ['Madagascar', 'Republic of Madagascar', 'MDG']),
 ('MH', 'MHL', 'marshall islands', ['Marshall Islands', 'Republic of the Marshall Islands', 'MHL']),
 ('MK', 'MKD', 'north macedonia', ['North Macedonia', 'Republic of North Macedonia', 'MKD']),
 ('ML', 'MLI', 'mali', ['Mali', 'Republic of Mali', 'MLI']),
 ('MM', 'MMR', 'myanmar', ['Myanmar', 'Republic of Myanmar', 'MMR']),
 ('MN', 'MNG', 'mongolia', ['Mongolia', 'MNG']),
 ('MO', 'MAC', 'macao', ['Macao', 'Macao Special Administrative Region of China', 'MAC']),
 ('MP', 'MNP', 'northern mariana islands', ['Northern Mariana Islands', 'Commonwealth of the Northern Mariana Islands', 'MNP']),
 ('MQ', 'MTQ', 'martinique', ['Martinique', 'MTQ']),
 ('MR', 'MRT', 'mauritania', ['Mauritania', 'Islamic Republic of Mauritania', 'MRT']),
 ('MS', 'MSR', 'montserrat', ['Montserrat', 'MSR']),
 ('MT', 'MLT', 'malta', ['Malta', 'Republic of Malta', 'MLT']),
 ('MU', 'MUS', 'mauritius', ['Mauritius', 'Republic of Mauritius', 'MUS']),
 ('MV', 'MDV', 'maldives', ['Maldives', 'Republic of Maldives', 'MDV']),
 ('MW', 'MWI', 'malawi', ['Malawi', 'Republic of Malawi', 'MWI']),
 ('MX', 'MEX', 'mexico', ['Mexico', 'United Mexican States', 'MEX']),
 ('MY', 'MYS', 'malaysia', ['Malaysia', 'MYS']),
 ('MZ', 'MOZ', 'mozambique', ['Mozambique', 'Republic of Mozambique', 'MOZ']),
 ('NA', 'NAM', 'namibia', ['Namibia', 'Republic of Namibia', 'NAM']),
 ('NC', 'NCL', 'new caledonia', ['New Caledonia', 'NCL']),
 ('NE', 'NER', 'niger', ['Niger', 'Republic of the Niger', 'NER']),
 ('NF', 'NFK', 'norfolk island', ['Norfolk Island', 'NFK']),
 ('NG', 'NGA', 'nigeria', ['Nigeria', 'Federal Republic of Nigeria', 'NGA']),
 ('NI', 'NIC', 'nicaragua', ['Nicaragua', 'Republic of Nicaragua', 'NIC']),
 ('NL', 'NLD', 'netherlands', ['Netherlands', 'Kingdom of the Netherlands', 'NLD']),
 ('NO', 'NOR', 'norway', ['Norway', 'Kingdom of Norway', 'NOR']),
 ('NP', 'NPL', 'nepal', ['Nepal', 'Federal Democratic Republic of Nepal', 'NPL']),
 ('NR', 'NRU', 'nauru', ['Nauru', 'Republic of Nauru', 'NRU']),
 ('NU', 'NIU', 'niue', ['Niue', 'NIU']),
 ('NZ', 'NZL', 'new zealand', ['New Zealand', 'NZL']),
 ('OM', 'OMN', 'oman', ['Oman', 'Sultanate of Oman', 'OMN']),
 ('PA', 'PAN', 'panama', ['Panama', 'Republic of Panama', 'PAN']),
 ('PE', 'PER', 'peru', ['Peru', 'Republic of Peru', 'PER']),
 ('PF', 'PYF', 'french polynesia', ['French Polynesia', 'PYF']),
 ('PG', 'PNG', 'papua new guinea', ['Papua New Guinea', 'Independent State of Papua New Guinea', 'PNG']),
 ('PH', 'PHL', 'philippines', ['Philippines', 'Republic of the Philippines', 'PHL']),
 ('PK', 'PAK', 'pakistan', ['Pakistan', 'Islamic Republic of Pakistan', 'PAK']),
 ('PL', 'POL', 'poland', ['Poland', 'Republic of Poland', 'POL']),
 ('PM', 'SPM', 'saint pierre and miquelon', ['Saint Pierre and Miquelon', 'SPM']),
 ('PN', 'PCN', 'pitcairn', ['Pitcairn', 'PCN']),
 ('PR', 'PRI', 'puerto rico', ['Puerto Rico', 'PRI']),
 ('PS', 'PSE', 'palestine', ['Palestine, State of', 'the State of Palestine', 'PSE']),
 ('PT', 'PRT', 'portugal', ['Portugal', 'Portuguese Republic', 'PRT']),
 ('PW', 'PLW', 'palau', ['Palau', 'Republic of Palau', 'PLW']),
 ('PY', 'PRY', 'paraguay', ['Paraguay', 'Republic of Paraguay', 'PRY']),
 ('QA', 'QAT', 'qatar', ['Qatar', 'State of Qatar', 'QAT']),
 ('RE', 'REU', 'réunion', ['Réunion', 'REU']),
 ('RO', 'ROU', 'romania', ['Romania', 'ROU']),
 ('RS', 'SRB', 'serbia', ['Serbia', 'Republic of Serbia', 'SRB']),
 ('RU', 'RUS', 'russia', ['Russian Federation', 'RUS']),
 ('RW', 'RWA', 'rwanda', ['Rwanda', 'Rwandese Republic', 'RWA']),
 ('SA', 'SAU', 'saudi arabia', ['Saudi Arabia', 'Kingdom of Saudi Arabia', 'SAU']),
 ('SB', 'SLB', 'solomon islands', ['Solomon Islands', 'SLB']),
 ('SC', 'SYC', 'seychelles', ['Seychelles', 'Republic of Seychelles', 'SYC']),
 ('SD', 'SDN', 'sudan', ['Sudan', 'Republic of the Sudan', 'SDN']),
 ('SE', 'SWE', 'sweden', ['Sweden', 'Kingdom of Sweden', 'SWE']),
 ('SG', 'SGP', 'singapore', ['Singapore', 'Republic of Singapore', 'SGP']),
 ('SH', 'SHN', 'saint helena, ascension and tristan da cunha', ['Saint Helena, Ascension and Tristan da Cunha', 'SHN']),
 ('SI', 'SVN', 'slovenia', ['Slovenia', 'Republic of Slovenia', 'SVN']),
 ('SJ', 'SJM', 'svalbard and jan mayen', ['Svalbard and Jan Mayen', 'SJM']),
 ('SK', 'SVK', 'slovakia', ['Slovakia', 'Slovak Republic', 'SVK']),
 ('SL', 'SLE', 'sierra leone', ['Sierra Leone', 'Republic of Sierra Leone', 'SLE']),
 ('SM', 'SMR', 'san marino', ['San Marino', 'Republic of San Marino', 'SMR']),
 ('SN', 'SEN', 'senegal', ['Senegal', 'Republic of Senegal', 'SEN']),
 ('SO', 'SOM', 'somalia', ['Somalia', 'Federal Republic of Somalia', 'SOM']),
 ('SR', 'SUR', 'suriname', ['Suriname', 'Republic of Suriname', 'SUR']),
 ('SS', 'SSD', 'south sudan', ['South Sudan', 'Republic of South Sudan', 'SSD']),
 ('ST', 'STP', 'sao tome and principe', ['Sao Tome and Principe', 'Democratic Republic of Sao Tome and Principe', 'STP']),
 ('SV', 'SLV', 'el salvador', ['El Salvador', 'Republic of El Salvador', 'SLV']),
 ('SX', 'SXM', 'sint maarten (dutch part)', ['Sint Maarten (Dutch part)', 'SXM']),
 ('SY', 'SYR', 'syria', ['Syrian Arab Republic', 'Syria', 'SYR']),
 ('SZ', 'SWZ', 'eswatini', ['Eswatini', 'Kingdom of Eswatini', 'SWZ']),
 ('TC', 'TCA', 'turks and caicos islands', ['Turks and Caicos Islands', 'TCA']),
 ('TD', 'TCD', 'chad', ['Chad', 'Republic of Chad', 'TCD']),
 ('TF', 'ATF', 'french southern territories', ['French Southern Territories', 'ATF']),
 ('TG', 'TGO', 'togo', ['Togo', 'Togolese Republic', 'TGO']),
 ('TH', 'THA', 'thailand', ['Thailand', 'Kingdom of Thailand', 'THA']),
 ('TJ', 'TJK', 'tajikistan', ['Tajikistan', 'Republic of Tajikistan', 'TJK']),
 ('TK', 'TKL', 'tokelau', ['Tokelau', 'TKL']),
 ('TL', 'TLS', 'timor-leste', ['Timor-Leste', 'Democratic Republic of Timor-Leste', 'TLS']),
 ('TM', 'TKM', 'turkmenistan', ['Turkmenistan', 'TKM']),
 ('TN', 'TUN', 'tunisia', ['Tunisia', 'Republic of Tunisia', 'TUN']),
 ('TO', 'TON', 'tonga', ['Tonga', 'Kingdom of Tonga', 'TON']),
 ('TR', 'TUR', 'turkey', ['Türkiye', 'Republic of Türkiye', 'TUR']),
 ('TT', 'TTO', 'trinidad and tobago', ['Trinidad and Tobago', 'Republic of Trinidad and Tobago', 'TTO']),
 ('TV', 'TUV', 'tuvalu', ['Tuvalu', 'TUV']),
 ('TW', 'TWN', 'taiwan', ['Taiwan, Province of China', 'Taiwan', 'TWN']),
 ('TZ', 'TZA', 'tanzania', ['Tanzania, United Republic of', 'United Republic of Tanzania', 'Tanzania', 'TZA']),
 ('UA', 'UKR', 'ukraine', ['Ukraine', 'UKR']),
 ('UG', 'UGA', 'uganda', ['Uganda', 'Republic of Uganda', 'UGA']),
 ('UM', 'UMI', 'united states minor outlying islands', ['United States Minor Outlying Islands', 'UMI']),
 ('US', 'USA', 'united states', ['United States', 'United States of America', 'USA']),
 ('UY', 'URY', 'uruguay', ['Uruguay', 'Eastern Republic of Uruguay', 'URY']),
 ('UZ', 'UZB', 'uzbekistan', ['Uzbekistan', 'Republic of Uzbekistan', 'UZB']),
 ('VA', 'VAT', 'vatican city', ['Holy See (Vatican City State)', 'VAT']),
 ('VC', 'VCT', 'saint vincent and the grenadines', ['Saint Vincent and the Grenadines', 'VCT']),
 ('VE', 'VEN', 'venezuela', ['Venezuela, Bolivarian Republic of', 'Bolivarian Republic of Venezuela', 'Venezuela', 'VEN']),
 ('VG', 'VGB', 'virgin islands, british', ['Virgin Islands, British', 'British Virgin Islands', 'VGB']),
 ('VI', 'VIR', 'virgin islands, u.s.', ['Virgin Islands, U.S.', 'Virgin Islands of the United States', 'VIR']),
 ('VN', 'VNM', 'vietnam', ['Viet Nam', 'Socialist Republic of Viet Nam', 'Vietnam', 'VNM']),
 ('VU', 'VUT', 'vanuatu', ['Vanuatu', 'Republic of Vanuatu', 'VUT']),
 ('WF', 'WLF', 'wallis and futuna', ['Wallis and Futuna', 'WLF']),
 ('WS', 'WSM', 'samoa', ['Samoa', 'Independent State of Samoa', 'WSM']),
 ('XK', 'XKX', 'kosovo', ['Kosovo', 'XKX']),
 ('YE', 'YEM', 'yemen', ['Yemen', 'Republic of Yemen', 'YEM']),
 ('YT', 'MYT', 'mayotte', ['Mayotte', 'MYT']),
 ('ZA', 'ZAF', 'south africa', ['South Africa', 'Republic of South Africa', 'ZAF']),
 ('ZM', 'ZMB', 'zambia', ['Zambia', 'Republic of Zambia', 'ZMB']),
 ('ZW', 'ZWE', 'zimbabwe', ['Zimbabwe', 'Republic of Zimbabwe', 'ZWE'])]

TIMEZONE_CITY_COUNTRY = {'Abidjan': 'CI',
 'Accra': 'GH',
 'Adak': 'US',
 'Addis Ababa': 'ET',
 'Adelaide': 'AU',
 'Aden': 'YE',
 'Algiers': 'DZ',
 'Almaty': 'KZ',
 'Amman': 'JO',
 'Amsterdam': 'NL',
 'Anadyr': 'RU',
 'Anchorage': 'US',
 'Andorra': 'AD',
 'Anguilla': 'AI',
 'Antananarivo': 'MG',
 'Antigua': 'AG',
 'Apia': 'WS',
 'Aqtau': 'KZ',
 'Aqtobe': 'KZ',
 'Araguaina': 'BR',
 'Aruba': 'AW',
 'Ashgabat': 'TM',
 'Asmara': 'ER',
 'Astrakhan': 'RU',
 'Asuncion': 'PY',
 'Athens': 'GR',
 'Atikokan': 'CA',
 'Atyrau': 'KZ',
 'Auckland': 'NZ',
 'Azores': 'PT',
 'Baghdad': 'IQ',
 'Bahia': 'BR',
 'Bahia Banderas': 'MX',
 'Bahrain': 'BH',
 'Baku': 'AZ',
 'Bamako': 'ML',
 'Bangkok': 'TH',
 'Bangui': 'CF',
 'Banjul': 'GM',
 'Barbados': 'BB',
 'Barnaul': 'RU',
 'Beirut': 'LB',
 'Belem': 'BR',
 'Belgrade': 'RS',
 'Belize': 'BZ',
 'Berlin': 'DE',
 'Bermuda': 'BM',
 'Beulah': 'US',
 'Bishkek': 'KG',
 'Bissau': 'GW',
 'Blanc-Sablon': 'CA',
 'Blantyre': 'MW',
 'Boa Vista': 'BR',
 'Bogota': 'CO',
 'Boise': 'US',
 'Bougainville': 'PG',
 'Bratislava': 'SK',
 'Brazzaville': 'CG',
 'Brisbane': 'AU',
 'Broken Hill': 'AU',
 'Brunei': 'BN',
 'Brussels': 'BE',
 'Bucharest': 'RO',
 'Budapest': 'HU',
 'Buenos Aires': 'AR',
 'Bujumbura': 'BI',
 'Busingen': 'DE',
 'Cairo': 'EG',
 'Cambridge Bay': 'CA',
 'Campo Grande': 'BR',
 'Canary': 'ES',
 'Cancun': 'MX',
 'Cape Verde': 'CV',
 'Caracas': 'VE',
 'Casablanca': 'MA',
 'Casey': 'AQ',
 'Catamarca': 'AR',
 'Cayenne': 'GF',
 'Cayman': 'KY',
 'Center': 'US',
 'Ceuta': 'ES',
 'Chagos': 'IO',
 'Chatham': 'NZ',
 'Chicago': 'US',
 'Chihuahua': 'MX',
 'Chisinau': 'MD',
 'Chita': 'RU',
 'Christmas': 'CX',
 'Chuuk': 'FM',
 'Ciudad Juarez': 'MX',
 'Cocos': 'CC',
 'Colombo': 'LK',
 'Comoro': 'KM',
 'Conakry': 'GN',
 'Copenhagen': 'DK',
 'Cordoba': 'AR',
 'Costa Rica': 'CR',
 'Coyhaique': 'CL',
 'Creston': 'CA',
 'Cuiaba': 'BR',
 'Curacao': 'CW',
 'Dakar': 'SN',
 'Damascus': 'SY',
 'Danmarkshavn': 'GL',
 'Dar es Salaam': 'TZ',
 'Darwin': 'AU',
 'Davis': 'AQ',
 'Dawson': 'CA',
 'Dawson Creek': 'CA',
 'Denver': 'US',
 'Detroit': 'US',
 'Dhaka': 'BD',
 'Dili': 'TL',
 'Djibouti': 'DJ',
 'Dominica': 'DM',
 'Douala': 'CM',
 'Dubai': 'AE',
 'Dublin': 'IE',
 'DumontDUrville': 'AQ',
 'Dushanbe': 'TJ',
 'Easter': 'CL',
 'Edmonton': 'CA',
 'Efate': 'VU',
 'Eirunepe': 'BR',
 'El Aaiun': 'EH',
 'El Salvador': 'SV',
 'Eucla': 'AU',
 'Fakaofo': 'TK',
 'Famagusta': 'CY',
 'Faroe': 'FO',
 'Fiji': 'FJ',
 'Fort Nelson': 'CA',
 'Fortaleza': 'BR',
 'Freetown': 'SL',
 'Funafuti': 'TV',
 'Gaborone': 'BW',
 'Galapagos': 'EC',
 'Gambier': 'PF',
 'Gaza': 'PS',
 'Gibraltar': 'GI',
 'Glace Bay': 'CA',
 'Goose Bay': 'CA',
 'Grand Turk': 'TC',
 'Grenada': 'GD',
 'Guadalcanal': 'SB',
 'Guadeloupe': 'GP',
 'Guam': 'GU',
 'Guatemala': 'GT',
 'Guayaquil': 'EC',
 'Guernsey': 'GG',
 'Guyana': 'GY',
 'Halifax': 'CA',
 'Harare': 'ZW',
 'Havana': 'CU',
 'Hebron': 'PS',
 'Helsinki': 'FI',
 'Hermosillo': 'MX',
 'Ho Chi Minh': 'VN',
 'Hobart': 'AU',
 'Hong Kong': 'HK',
 'Honolulu': 'US',
 'Hovd': 'MN',
 'Indianapolis': 'US',
 'Inuvik': 'CA',
 'Iqaluit': 'CA',
 'Irkutsk': 'RU',
 'Isle of Man': 'IM',
 'Istanbul': 'TR',
 'Jakarta': 'ID',
 'Jamaica': 'JM',
 'Jayapura': 'ID',
 'Jersey': 'JE',
 'Jerusalem': 'IL',
 'Johannesburg': 'ZA',
 'Juba': 'SS',
 'Jujuy': 'AR',
 'Juneau': 'US',
 'Kabul': 'AF',
 'Kaliningrad': 'RU',
 'Kamchatka': 'RU',
 'Kampala': 'UG',
 'Kanton': 'KI',
 'Karachi': 'PK',
 'Kathmandu': 'NP',
 'Kerguelen': 'TF',
 'Khandyga': 'RU',
 'Khartoum': 'SD',
 'Kigali': 'RW',
 'Kinshasa': 'CD',
 'Kiritimati': 'KI',
 'Kirov': 'RU',
 'Knox': 'US',
 'Kolkata': 'IN',
 'Kosrae': 'FM',
 'Kralendijk': 'BQ',
 'Krasnoyarsk': 'RU',
 'Kuala Lumpur': 'MY',
 'Kuching': 'MY',
 'Kuwait': 'KW',
 'Kwajalein': 'MH',
 'Kyiv': 'UA',
 'La Paz': 'BO',
 'La Rioja': 'AR',
 'Lagos': 'NG',
 'Libreville': 'GA',
 'Lima': 'PE',
 'Lindeman': 'AU',
 'Lisbon': 'PT',
 'Ljubljana': 'SI',
 'Lome': 'TG',
 'London': 'GB',
 'Longyearbyen': 'SJ',
 'Lord Howe': 'AU',
 'Los Angeles': 'US',
 'Louisville': 'US',
 'Lower Princes': 'SX',
 'Luanda': 'AO',
 'Lubumbashi': 'CD',
 'Lusaka': 'ZM',
 'Luxembourg': 'LU',
 'Macau': 'MO',
 'Maceio': 'BR',
 'Macquarie': 'AU',
 'Madeira': 'PT',
 'Madrid': 'ES',
 'Magadan': 'RU',
 'Mahe': 'SC',
 'Majuro': 'MH',
 'Makassar': 'ID',
 'Malabo': 'GQ',
 'Maldives': 'MV',
 'Malta': 'MT',
 'Managua': 'NI',
 'Manaus': 'BR',
 'Manila': 'PH',
 'Maputo': 'MZ',
 'Marengo': 'US',
 'Mariehamn': 'AX',
 'Marigot': 'MF',
 'Marquesas': 'PF',
 'Martinique': 'MQ',
 'Maseru': 'LS',
 'Matamoros': 'MX',
 'Mauritius': 'MU',
 'Mawson': 'AQ',
 'Mayotte': 'YT',
 'Mazatlan': 'MX',
 'Mbabane': 'SZ',
 'McMurdo': 'AQ',
 'Melbourne': 'AU',
 'Mendoza': 'AR',
 'Menominee': 'US',
 'Merida': 'MX',
 'Metlakatla': 'US',
 'Mexico City': 'MX',
 'Midway': 'UM',
 'Minsk': 'BY',
 'Miquelon': 'PM',
 'Mogadishu': 'SO',
 'Monaco': 'MC',
 'Moncton': 'CA',
 'Monrovia': 'LR',
 'Monterrey': 'MX',
 'Montevideo': 'UY',
 'Monticello': 'US',
 'Montserrat': 'MS',
 'Moscow': 'RU',
 'Muscat': 'OM',
 'Nairobi': 'KE',
 'Nassau': 'BS',
 'Nauru': 'NR',
 'Ndjamena': 'TD',
 'New Salem': 'US',
 'New York': 'US',
 'Niamey': 'NE',
 'Nicosia': 'CY',
 'Niue': 'NU',
 'Nome': 'US',
 'Norfolk': 'NF',
 'Noronha': 'BR',
 'Nouakchott': 'MR',
 'Noumea': 'NC',
 'Novokuznetsk': 'RU',
 'Novosibirsk': 'RU',
 'Nuuk': 'GL',
 'Ojinaga': 'MX',
 'Omsk': 'RU',
 'Oral': 'KZ',
 'Oslo': 'NO',
 'Ouagadougou': 'BF',
 'Pago Pago': 'AS',
 'Palau': 'PW',
 'Palmer': 'AQ',
 'Panama': 'PA',
 'Paramaribo': 'SR',
 'Paris': 'FR',
 'Perth': 'AU',
 'Petersburg': 'US',
 'Phnom Penh': 'KH',
 'Phoenix': 'US',
 'Pitcairn': 'PN',
 'Podgorica': 'ME',
 'Pohnpei': 'FM',
 'Pontianak': 'ID',
 'Port Moresby': 'PG',
 'Port of Spain': 'TT',
 'Port-au-Prince': 'HT',
 'Porto Velho': 'BR',
 'Porto-Novo': 'BJ',
 'Prague': 'CZ',
 'Puerto Rico': 'PR',
 'Punta Arenas': 'CL',
 'Pyongyang': 'KP',
 'Qatar': 'QA',
 'Qostanay': 'KZ',
 'Qyzylorda': 'KZ',
 'Rankin Inlet': 'CA',
 'Rarotonga': 'CK',
 'Recife': 'BR',
 'Regina': 'CA',
 'Resolute': 'CA',
 'Reunion': 'RE',
 'Reykjavik': 'IS',
 'Riga': 'LV',
 'Rio Branco': 'BR',
 'Rio Gallegos': 'AR',
 'Riyadh': 'SA',
 'Rome': 'IT',
 'Rothera': 'AQ',
 'Saipan': 'MP',
 'Sakhalin': 'RU',
 'Salta': 'AR',
 'Samara': 'RU',
 'Samarkand': 'UZ',
 'San Juan': 'AR',
 'San Luis': 'AR',
 'San Marino': 'SM',
 'Santarem': 'BR',
 'Santiago': 'CL',
 'Santo Domingo': 'DO',
 'Sao Paulo': 'BR',
 'Sao Tome': 'ST',
 'Sarajevo': 'BA',
 'Saratov': 'RU',
 'Scoresbysund': 'GL',
 'Seoul': 'KR',
 'Shanghai': 'CN',
 'Simferopol': 'UA',
 'Singapore': 'SG',
 'Sitka': 'US',
 'Skopje': 'MK',
 'Sofia': 'BG',
 'South Georgia': 'GS',
 'Srednekolymsk': 'RU',
 'St Barthelemy': 'BL',
 'St Helena': 'SH',
 'St Johns': 'CA',
 'St Kitts': 'KN',
 'St Lucia': 'LC',
 'St Thomas': 'VI',
 'St Vincent': 'VC',
 'Stanley': 'FK',
 'Stockholm': 'SE',
 'Swift Current': 'CA',
 'Sydney': 'AU',
 'Syowa': 'AQ',
 'Tahiti': 'PF',
 'Taipei': 'TW',
 'Tallinn': 'EE',
 'Tarawa': 'KI',
 'Tashkent': 'UZ',
 'Tbilisi': 'GE',
 'Tegucigalpa': 'HN',
 'Tehran': 'IR',
 'Tell City': 'US',
 'Thimphu': 'BT',
 'Thule': 'GL',
 'Tijuana': 'MX',
 'Tirane': 'AL',
 'Tokyo': 'JP',
 'Tomsk': 'RU',
 'Tongatapu': 'TO',
 'Toronto': 'CA',
 'Tortola': 'VG',
 'Tripoli': 'LY',
 'Troll': 'AQ',
 'Tucuman': 'AR',
 'Tunis': 'TN',
 'Ulaanbaatar': 'MN',
 'Ulyanovsk': 'RU',
 'Urumqi': 'CN',
 'Ushuaia': 'AR',
 'Ust-Nera': 'RU',
 'Vaduz': 'LI',
 'Vancouver': 'CA',
 'Vatican': 'VA',
 'Vevay': 'US',
 'Vienna': 'AT',
 'Vientiane': 'LA',
 'Vilnius': 'LT',
 'Vincennes': 'US',
 'Vladivostok': 'RU',
 'Volgograd': 'RU',
 'Vostok': 'AQ',
 'Wake': 'UM',
 'Wallis': 'WF',
 'Warsaw': 'PL',
 'Whitehorse': 'CA',
 'Winamac': 'US',
 'Windhoek': 'NA',
 'Winnipeg': 'CA',
 'Yakutat': 'US',
 'Yakutsk': 'RU',
 'Yangon': 'MM',
 'Yekaterinburg': 'RU',
 'Yerevan': 'AM',
 'Zagreb': 'HR',
 'Zurich': 'CH'}

REGION_ISO = {
    "europe": ['AL', 'AD', 'AT', 'BY', 'BE', 'BA', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IS', 'IE', 'IT', 'XK', 'LV', 'LI', 'LT', 'LU', 'MT', 'MD', 'MC', 'ME', 'NL', 'MK', 'NO', 'PL', 'PT', 'RO', 'RU', 'SM', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH', 'UA', 'GB', 'VA'],
    "european union": ['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'],
    "dach": ['DE', 'AT', 'CH'],
    "nordics": ['DK', 'FI', 'IS', 'NO', 'SE'],
    "benelux": ['BE', 'NL', 'LU'],
    "cee": ['AL', 'BY', 'BA', 'BG', 'HR', 'CZ', 'EE', 'HU', 'XK', 'LV', 'LT', 'MD', 'ME', 'MK', 'PL', 'RO', 'RS', 'SK', 'SI', 'UA'],
    "africa": ['DZ', 'AO', 'BJ', 'BW', 'BF', 'BI', 'CV', 'CM', 'CF', 'TD', 'KM', 'CG', 'CD', 'CI', 'DJ', 'EG', 'GQ', 'ER', 'SZ', 'ET', 'GA', 'GM', 'GH', 'GN', 'GW', 'KE', 'LS', 'LR', 'LY', 'MG', 'MW', 'ML', 'MR', 'MU', 'MA', 'MZ', 'NA', 'NE', 'NG', 'RW', 'ST', 'SN', 'SC', 'SL', 'SO', 'ZA', 'SS', 'SD', 'TZ', 'TG', 'TN', 'UG', 'ZM', 'ZW'],
    "asia": ['AF', 'AM', 'AZ', 'BH', 'BD', 'BT', 'BN', 'KH', 'CN', 'GE', 'IN', 'ID', 'IR', 'IQ', 'IL', 'JP', 'JO', 'KZ', 'KW', 'KG', 'LA', 'LB', 'MY', 'MV', 'MN', 'MM', 'NP', 'KP', 'OM', 'PK', 'PS', 'PH', 'QA', 'SA', 'SG', 'KR', 'LK', 'SY', 'TW', 'TJ', 'TH', 'TL', 'TM', 'TR', 'AE', 'UZ', 'VN', 'YE'],
    "oceania": ['AU', 'FJ', 'KI', 'MH', 'FM', 'NR', 'NZ', 'PW', 'PG', 'WS', 'SB', 'TO', 'TV', 'VU'],
    "north america": ['US', 'CA', 'MX', 'GL', 'BM', 'PM', 'BZ', 'CR', 'SV', 'GT', 'HN', 'NI', 'PA', 'BS', 'BB', 'CU', 'DM', 'DO', 'GD', 'HT', 'JM', 'KN', 'LC', 'VC', 'TT', 'AG'],
    "south america": ['AR', 'BO', 'BR', 'CL', 'CO', 'EC', 'FK', 'GF', 'GY', 'PY', 'PE', 'SR', 'UY', 'VE'],
    "latam": ['MX', 'BZ', 'CR', 'SV', 'GT', 'HN', 'NI', 'PA', 'AR', 'BO', 'BR', 'CL', 'CO', 'EC', 'GF', 'GY', 'PY', 'PE', 'SR', 'UY', 'VE', 'CU', 'DO', 'HT', 'JM', 'PR'],
    "middle east": ['BH', 'EG', 'IR', 'IQ', 'IL', 'JO', 'KW', 'LB', 'OM', 'PS', 'QA', 'SA', 'SY', 'TR', 'AE', 'YE'],
    "apac": ['AF', 'AM', 'AZ', 'BH', 'BD', 'BT', 'BN', 'KH', 'CN', 'GE', 'IN', 'ID', 'IR', 'IQ', 'IL', 'JP', 'JO', 'KZ', 'KW', 'KG', 'LA', 'LB', 'MY', 'MV', 'MN', 'MM', 'NP', 'KP', 'OM', 'PK', 'PS', 'PH', 'QA', 'SA', 'SG', 'KR', 'LK', 'SY', 'TW', 'TJ', 'TH', 'TL', 'TM', 'TR', 'AE', 'UZ', 'VN', 'YE', 'AU', 'FJ', 'KI', 'MH', 'FM', 'NR', 'NZ', 'PW', 'PG', 'WS', 'SB', 'TO', 'TV', 'VU'],
    "emea": ['AL', 'AD', 'AT', 'BY', 'BE', 'BA', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IS', 'IE', 'IT', 'XK', 'LV', 'LI', 'LT', 'LU', 'MT', 'MD', 'MC', 'ME', 'NL', 'MK', 'NO', 'PL', 'PT', 'RO', 'RU', 'SM', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH', 'UA', 'GB', 'VA', 'DZ', 'AO', 'BJ', 'BW', 'BF', 'BI', 'CV', 'CM', 'CF', 'TD', 'KM', 'CG', 'CD', 'CI', 'DJ', 'EG', 'GQ', 'ER', 'SZ', 'ET', 'GA', 'GM', 'GH', 'GN', 'GW', 'KE', 'LS', 'LR', 'LY', 'MG', 'MW', 'ML', 'MR', 'MU', 'MA', 'MZ', 'NA', 'NE', 'NG', 'RW', 'ST', 'SN', 'SC', 'SL', 'SO', 'ZA', 'SS', 'SD', 'TZ', 'TG', 'TN', 'UG', 'ZM', 'ZW', 'BH', 'IR', 'IQ', 'IL', 'JO', 'KW', 'LB', 'OM', 'PS', 'QA', 'SA', 'SY', 'TR', 'AE', 'YE'],
    "asean": ['BN', 'KH', 'ID', 'LA', 'MY', 'MM', 'PH', 'SG', 'TH', 'VN'],
    "anz": ['AU', 'NZ'],
}

REGION_ALIASES_EXTRA = {
    "europe": ["europe","european region"],
    "european union": ["eu","european union"],
    "dach": ["dach"],
    "nordics": ["nordics","nordic"],
    "benelux": ["benelux"],
    "cee": ["cee","central eastern europe","central and eastern europe"],
    "africa": ["africa"],
    "asia": ["asia"],
    "oceania": ["oceania"],
    "north america": ["north america"],
    "south america": ["south america"],
    "latam": ["latam","latin america","latin-america"],
    "middle east": ["middle east","mena middle east"],
    "apac": ["apac","asia pacific","asia-pacific"],
    "emea": ["emea","europe middle east africa"],
    "asean": ["asean","southeast asia"],
    "anz": ["anz","australia new zealand"],
}

US_STATES = {'AK': 'Alaska',
 'AL': 'Alabama',
 'AR': 'Arkansas',
 'AZ': 'Arizona',
 'CA': 'California',
 'CO': 'Colorado',
 'CT': 'Connecticut',
 'DC': 'District of Columbia',
 'DE': 'Delaware',
 'FL': 'Florida',
 'GA': 'Georgia',
 'HI': 'Hawaii',
 'IA': 'Iowa',
 'ID': 'Idaho',
 'IL': 'Illinois',
 'IN': 'Indiana',
 'KS': 'Kansas',
 'KY': 'Kentucky',
 'LA': 'Louisiana',
 'MA': 'Massachusetts',
 'MD': 'Maryland',
 'ME': 'Maine',
 'MI': 'Michigan',
 'MN': 'Minnesota',
 'MO': 'Missouri',
 'MS': 'Mississippi',
 'MT': 'Montana',
 'NC': 'North Carolina',
 'ND': 'North Dakota',
 'NE': 'Nebraska',
 'NH': 'New Hampshire',
 'NJ': 'New Jersey',
 'NM': 'New Mexico',
 'NV': 'Nevada',
 'NY': 'New York',
 'OH': 'Ohio',
 'OK': 'Oklahoma',
 'OR': 'Oregon',
 'PA': 'Pennsylvania',
 'RI': 'Rhode Island',
 'SC': 'South Carolina',
 'SD': 'South Dakota',
 'TN': 'Tennessee',
 'TX': 'Texas',
 'UT': 'Utah',
 'VA': 'Virginia',
 'VT': 'Vermont',
 'WA': 'Washington',
 'WI': 'Wisconsin',
 'WV': 'West Virginia',
 'WY': 'Wyoming'}
CANADA_PROVINCES = {'AB': 'Alberta',
 'BC': 'British Columbia',
 'MB': 'Manitoba',
 'NB': 'New Brunswick',
 'NL': 'Newfoundland and Labrador',
 'NS': 'Nova Scotia',
 'NT': 'Northwest Territories',
 'NU': 'Nunavut',
 'ON': 'Ontario',
 'PE': 'Prince Edward Island',
 'QC': 'Quebec',
 'SK': 'Saskatchewan',
 'YT': 'Yukon'}
INDIA_STATES = ['Andhra Pradesh',
 'Arunachal Pradesh',
 'Assam',
 'Bihar',
 'Chhattisgarh',
 'Goa',
 'Gujarat',
 'Haryana',
 'Himachal Pradesh',
 'Jharkhand',
 'Karnataka',
 'Kerala',
 'Madhya Pradesh',
 'Maharashtra',
 'Manipur',
 'Meghalaya',
 'Mizoram',
 'Nagaland',
 'Odisha',
 'Punjab',
 'Rajasthan',
 'Sikkim',
 'Tamil Nadu',
 'Telangana',
 'Tripura',
 'Uttar Pradesh',
 'Uttarakhand',
 'West Bengal',
 'Andaman and Nicobar Islands',
 'Chandigarh',
 'Dadra and Nagar Haveli and Daman and Diu',
 'Delhi',
 'Jammu and Kashmir',
 'Ladakh',
 'Lakshadweep',
 'Puducherry']
ADMIN_CITY_HINTS = {('canada', 'alberta'): ['calgary', 'edmonton'],
 ('canada', 'british columbia'): ['vancouver', 'burnaby', 'richmond', 'victoria'],
 ('canada', 'ontario'): ['toronto', 'ottawa', 'waterloo', 'mississauga', 'markham'],
 ('canada', 'quebec'): ['montreal', 'quebec city'],
 ('india', 'delhi'): ['delhi', 'new delhi', 'ncr'],
 ('india', 'gujarat'): ['ahmedabad', 'surat', 'vadodara'],
 ('india', 'haryana'): ['gurgaon', 'gurugram'],
 ('india', 'karnataka'): ['bengaluru', 'bangalore', 'mysuru', 'mysore'],
 ('india', 'kerala'): ['kochi', 'cochin', 'thiruvananthapuram', 'trivandrum'],
 ('india', 'maharashtra'): ['mumbai', 'pune', 'navi mumbai', 'thane', 'nagpur', 'panvel'],
 ('india', 'tamil nadu'): ['chennai', 'coimbatore'],
 ('india', 'telangana'): ['hyderabad'],
 ('india', 'uttar pradesh'): ['noida', 'greater noida', 'lucknow'],
 ('india', 'west bengal'): ['kolkata'],
 ('united states', 'california'): ['san francisco',
                                   'san jose',
                                   'los angeles',
                                   'san diego',
                                   'sacramento',
                                   'palo alto',
                                   'mountain view',
                                   'sunnyvale',
                                   'oakland',
                                   'berkeley'],
 ('united states', 'colorado'): ['denver', 'boulder'],
 ('united states', 'florida'): ['miami', 'orlando', 'tampa', 'jacksonville'],
 ('united states', 'georgia'): ['atlanta'],
 ('united states', 'illinois'): ['chicago', 'springfield illinois'],
 ('united states', 'massachusetts'): ['boston', 'cambridge', 'worcester'],
 ('united states', 'new york'): ['new york', 'new york city', 'nyc', 'buffalo', 'rochester'],
 ('united states', 'north carolina'): ['raleigh', 'durham', 'charlotte'],
 ('united states', 'texas'): ['austin', 'dallas', 'houston', 'san antonio'],
 ('united states', 'washington'): ['seattle', 'bellevue', 'redmond', 'tacoma', 'spokane']}

def _augment_planet_location_data():
    """Expand curated location data to every ISO country plus broad global city/admin coverage."""
    global REGION_DATA

    alpha2_to_country = {}
    alpha3_to_country = {}

    for alpha2, alpha3, canonical, aliases in WORLD_COUNTRY_RECORDS:
        alpha2_to_country[alpha2] = canonical
        alpha3_to_country[alpha3] = canonical
        entry = COUNTRY_DATA.setdefault(canonical, {"aliases": [], "cities": []})
        for alias in aliases + [canonical]:
            if alias and alias.lower() not in [a.lower() for a in entry["aliases"]]:
                entry["aliases"].append(alias)
        # Alpha-3 is generally safe in candidate locations; alpha-2 is parsed only as exact user input.
        if alpha3 not in entry["aliases"]:
            entry["aliases"].append(alpha3)

    # Familiar recruiter aliases.
    familiar = {
        "united states": ["usa","u.s.a.","us","u.s.","america"],
        "united kingdom": ["uk","u.k.","great britain","britain"],
        "united arab emirates": ["uae","u.a.e.","emirates"],
        "south korea": ["korea","republic of korea"],
        "russia": ["russian federation"],
        "vietnam": ["viet nam"],
        "czechia": ["czech republic"],
        "turkey": ["türkiye","turkiye"],
        "taiwan": ["taiwan"],
    }
    for country, aliases in familiar.items():
        if country in COUNTRY_DATA:
            for a in aliases:
                if a not in COUNTRY_DATA[country]["aliases"]:
                    COUNTRY_DATA[country]["aliases"].append(a)

    # Add 400+ IANA timezone city labels spread globally.
    for city, alpha2 in TIMEZONE_CITY_COUNTRY.items():
        country = alpha2_to_country.get(alpha2)
        if country and city.lower() not in [c.lower() for c in COUNTRY_DATA[country]["cities"]]:
            COUNTRY_DATA[country]["cities"].append(city.lower())

    # Rebuild recruiter regions from ISO sets so Europe/APAC/EMEA/etc. are not partial.
    REGION_DATA = {}
    for region, codes in REGION_ISO.items():
        countries = [alpha2_to_country[c] for c in codes if c in alpha2_to_country]
        REGION_DATA[region] = {
            "aliases": REGION_ALIASES_EXTRA.get(region, [region]),
            "countries": list(dict.fromkeys(countries)),
        }

    return alpha2_to_country, alpha3_to_country

ISO_ALPHA2_TO_COUNTRY, ISO_ALPHA3_TO_COUNTRY = _augment_planet_location_data()

def _build_admin_indexes():
    admin_alias = {}
    admin_city = {}

    for code, name in US_STATES.items():
        key = ("united states", name.lower())
        admin_alias[_loc_ascii(name)] = (*key, [name, code])
        admin_alias[_loc_compact(name)] = (*key, [name, code])
        # State abbreviations are useful exact inputs; e.g. CA, WA, TX.
        admin_alias[code.lower()] = (*key, [name, code])

    for code, name in CANADA_PROVINCES.items():
        key = ("canada", name.lower())
        admin_alias[_loc_ascii(name)] = (*key, [name, code])
        admin_alias[_loc_compact(name)] = (*key, [name, code])
        admin_alias[code.lower()] = (*key, [name, code])

    for name in INDIA_STATES:
        key = ("india", name.lower())
        admin_alias[_loc_ascii(name)] = (*key, [name])

    for (country, admin), cities in ADMIN_CITY_HINTS.items():
        for city in cities:
            admin_city[(_loc_ascii(country), _loc_ascii(city))] = admin

    return admin_alias, admin_city


def _build_location_indexes():
    country_alias_to_country = {}
    country_code_to_country = {}
    city_to_country = {}
    canonical_city_aliases = defaultdict(list)

    for country, data in COUNTRY_DATA.items():
        for alias in [country] + data["aliases"]:
            country_alias_to_country[_loc_ascii(alias)] = country
            country_alias_to_country[_loc_compact(alias)] = country
        for city in data["cities"]:
            city_to_country[_loc_ascii(city)] = country
            city_to_country[_loc_compact(city)] = country

    for alpha2, country in ISO_ALPHA2_TO_COUNTRY.items():
        country_code_to_country[alpha2.lower()] = country
    for alpha3, country in ISO_ALPHA3_TO_COUNTRY.items():
        country_code_to_country[alpha3.lower()] = country

    for canonical, aliases in CITY_ALIASES.items():
        for alias in [canonical] + aliases:
            canonical_city_aliases[canonical].append(alias)
            if _loc_ascii(canonical) in city_to_country:
                c = city_to_country[_loc_ascii(canonical)]
                city_to_country[_loc_ascii(alias)] = c
                city_to_country[_loc_compact(alias)] = c

    region_alias_to_region = {}
    country_to_regions = defaultdict(list)
    for region_name, region_data in REGION_DATA.items():
        for alias in [region_name] + region_data["aliases"]:
            region_alias_to_region[_loc_ascii(alias)] = region_name
            region_alias_to_region[_loc_compact(alias)] = region_name
        for country_name in region_data["countries"]:
            if region_name not in country_to_regions[country_name]:
                country_to_regions[country_name].append(region_name)

    admin_alias_index, admin_city_index = _build_admin_indexes()

    return (country_alias_to_country, country_code_to_country, city_to_country,
            canonical_city_aliases, region_alias_to_region, country_to_regions,
            admin_alias_index, admin_city_index)

(COUNTRY_ALIAS_INDEX, COUNTRY_CODE_INDEX, CITY_COUNTRY_INDEX,
 CANONICAL_CITY_ALIASES, REGION_ALIAS_INDEX, COUNTRY_TO_REGIONS,
 ADMIN_ALIAS_INDEX, ADMIN_CITY_INDEX) = _build_location_indexes()

def _canonical_city(raw):
    r1, r2 = _loc_ascii(raw), _loc_compact(raw)
    for canonical, aliases in CANONICAL_CITY_ALIASES.items():
        if any(r1 == _loc_ascii(a) or r2 == _loc_compact(a) for a in aliases):
            return canonical
    # exact known city
    for country, data in COUNTRY_DATA.items():
        for city in data["cities"]:
            if r1 == _loc_ascii(city) or r2 == _loc_compact(city):
                return city
    return _loc_ascii(raw)

def _parse_single_location(text):
    raw = (text or "").strip()
    norm = _loc_ascii(raw)
    compact = _loc_compact(raw)

    if not norm or norm in {"global","worldwide","anywhere","remote","remote global","world"}:
        return {
            "type": "GLOBAL", "raw": raw or "global", "city": None, "admin": None,
            "country": None, "region": "global", "regions": ["global"],
            "exact_terms": [], "nearby_terms": [], "country_terms": [], "region_countries": []
        }

    # Recruiter macro-region input.
    region = REGION_ALIAS_INDEX.get(norm) or REGION_ALIAS_INDEX.get(compact)
    if region:
        countries = [c for c in REGION_DATA[region]["countries"] if c in COUNTRY_DATA]
        return {
            "type": "REGION", "raw": raw, "city": None, "admin": None,
            "country": None, "region": region, "regions": [region],
            "exact_terms": [], "nearby_terms": [], "country_terms": [],
            "region_countries": countries
        }

    # Administrative area input: US states, Canadian provinces, Indian states/UTs.
    admin_hit = ADMIN_ALIAS_INDEX.get(norm) or ADMIN_ALIAS_INDEX.get(compact)
    if admin_hit:
        country, admin, aliases = admin_hit
        regions = COUNTRY_TO_REGIONS.get(country, [])
        return {
            "type": "ADMIN", "raw": raw, "city": None, "admin": admin,
            "country": country, "region": regions[0] if regions else None, "regions": regions,
            "exact_terms": list(dict.fromkeys([admin] + aliases)),
            "nearby_terms": [],
            "country_terms": list(dict.fromkeys([country] + COUNTRY_DATA[country]["aliases"] + COUNTRY_DATA[country]["cities"])),
            "region_countries": []
        }

    # Country input by normal name/alias.
    country = COUNTRY_ALIAS_INDEX.get(norm) or COUNTRY_ALIAS_INDEX.get(compact)

    # Exact ISO code input fallback. Admin abbreviations deliberately get precedence above.
    if not country and norm in COUNTRY_CODE_INDEX:
        country = COUNTRY_CODE_INDEX[norm]

    if country:
        data = COUNTRY_DATA[country]
        regions = COUNTRY_TO_REGIONS.get(country, [])
        return {
            "type": "COUNTRY", "raw": raw, "city": None, "admin": None, "country": country,
            "region": regions[0] if regions else None, "regions": regions,
            "exact_terms": [], "nearby_terms": [],
            "country_terms": list(dict.fromkeys([country] + data["aliases"] + data["cities"])),
            "region_countries": []
        }

    # City input from curated + IANA timezone city knowledge.
    city = _canonical_city(raw)
    country = CITY_COUNTRY_INDEX.get(_loc_ascii(city)) or CITY_COUNTRY_INDEX.get(_loc_compact(city))
    aliases = CANONICAL_CITY_ALIASES.get(city, [city])

    if country:
        country_data = COUNTRY_DATA[country]
        near = NEARBY_CITIES.get(city, [])
        regions = COUNTRY_TO_REGIONS.get(country, [])
        admin = ADMIN_CITY_INDEX.get((_loc_ascii(country), _loc_ascii(city)))
        return {
            "type": "CITY", "raw": raw, "city": city, "admin": admin, "country": country,
            "region": regions[0] if regions else None, "regions": regions,
            "exact_terms": list(dict.fromkeys([city] + aliases)),
            "nearby_terms": near,
            "country_terms": list(dict.fromkeys([country] + country_data["aliases"] + country_data["cities"])),
            "region_countries": []
        }

    # Open-world exact fallback. Never crash or discard an unfamiliar place.
    return {
        "type": "OPEN_LOCATION", "raw": raw, "city": norm, "admin": None, "country": None,
        "region": None, "regions": [], "exact_terms": [raw, norm], "nearby_terms": [],
        "country_terms": [], "region_countries": []
    }


def _location_rank(label):
    order = {
        "TIER_1_GLOBAL": 100,
        "TIER_1_EXACT": 98,
        "TIER_1_ADMIN": 97,
        "TIER_1_COUNTRY": 96,
        "TIER_1_REGION_COUNTRY": 95,
        "TIER_2_ADMIN_CITY": 92,
        "TIER_2_NEARBY": 90,
        "TIER_2_COUNTRY_CITY": 88,
        "TIER_2_REGION_CITY": 86,
        "TIER_3_SAME_COUNTRY": 70,
        "TIER_4_COUNTRY_KEYWORD": 60,
        "UNVERIFIED": 40,
        "NO_MATCH": 0,
    }
    return order.get(label, 0)

def _strong_location_split(raw):
    """Split recruiter/candidate multi-location text without breaking normal 'City, Country' forms."""
    parts = [p.strip() for p in re.split(r"\s*(?:/|\||;|\+|\bor\b)\s*", raw, flags=re.I) if p.strip()]
    return parts

def parse_location(text):
    """
    Parse one or many recruiter locations.
    Supports examples like:
      NYC / Gurgaon
      London OR Berlin
      India + Singapore
      US | Canada | UK
      Bangalore, Hyderabad
    while preserving normal forms like 'San Francisco, CA' and 'Berlin, Germany'.
    """
    raw = (text or "").strip()
    if not raw:
        return _parse_single_location(raw)

    # Strong separators first.
    strong = _strong_location_split(raw)
    if len(strong) > 1:
        opts = [_parse_single_location(p) for p in strong]
        if any(o["type"] == "GLOBAL" for o in opts):
            return _parse_single_location("global")
        return {
            "type": "MULTI", "raw": raw, "city": None, "admin": None, "country": None,
            "region": None, "regions": [], "options": opts,
            "exact_terms": [], "nearby_terms": [], "country_terms": [], "region_countries": []
        }

    # Comma can mean either "City, State/Country" or several allowed places.
    pieces = [p.strip() for p in raw.split(",") if p.strip()]
    if len(pieces) >= 2:
        parsed = [_parse_single_location(p) for p in pieces]

        # Keep standard "City, State/Country" together.
        if len(parsed) == 2:
            a, b = parsed
            same_country_pair = (
                a.get("country") and b.get("country") and a.get("country") == b.get("country")
                and a["type"] == "CITY" and b["type"] in {"COUNTRY", "ADMIN"}
            )
            if same_country_pair:
                return a

        # If every comma-separated piece is independently recognizable, treat as alternatives.
        if all(p["type"] != "OPEN_LOCATION" for p in parsed):
            if any(o["type"] == "GLOBAL" for o in parsed):
                return _parse_single_location("global")
            return {
                "type": "MULTI", "raw": raw, "city": None, "admin": None, "country": None,
                "region": None, "regions": [], "options": parsed,
                "exact_terms": [], "nearby_terms": [], "country_terms": [], "region_countries": []
            }

    return _parse_single_location(raw)

def _candidate_location_variants(profile_location):
    """Candidate-side normalization for messy GitHub strings such as 'NYC / London'."""
    raw = (profile_location or "").strip()
    if not raw:
        return []
    parts = _strong_location_split(raw)
    return list(dict.fromkeys([raw] + parts))

def _location_fit_single(profile_location, wanted):
    """
    High-recall global location ranking:
      exact city/admin > nearby > same country > country keyword > unverified > confirmed mismatch.
    Region and country searches remain flexible; mismatches stay visible lower in ranking.
    """
    if wanted["type"] == "GLOBAL":
        return "TIER_1_GLOBAL"
    if not profile_location:
        return "UNVERIFIED"

    loc = profile_location

    if wanted["type"] == "REGION":
        for country in wanted["region_countries"]:
            data = COUNTRY_DATA[country]
            if any(_loc_contains(loc, t) for t in [country] + data["aliases"]):
                return "TIER_1_REGION_COUNTRY"
            if any(_loc_contains(loc, city) for city in data["cities"]):
                return "TIER_2_REGION_CITY"
        return "NO_MATCH"

    if wanted["type"] == "ADMIN":
        # Exact admin/state/province wording or abbreviation.
        if any(_loc_contains(loc, t) for t in wanted["exact_terms"]):
            return "TIER_1_ADMIN"
        # Known city hints within this admin.
        for (country_key, city_key), admin in ADMIN_CITY_INDEX.items():
            if country_key == _loc_ascii(wanted["country"]) and admin == wanted["admin"]:
                if _loc_contains(loc, city_key):
                    return "TIER_2_ADMIN_CITY"
        # Same country is still useful, but lower.
        data = COUNTRY_DATA[wanted["country"]]
        if any(_loc_contains(loc, city) for city in data["cities"]):
            return "TIER_3_SAME_COUNTRY"
        if any(_loc_contains(loc, t) for t in [wanted["country"]] + data["aliases"]):
            return "TIER_4_COUNTRY_KEYWORD"
        return "NO_MATCH"

    if wanted["type"] == "COUNTRY":
        country = wanted["country"]
        data = COUNTRY_DATA[country]
        if any(_loc_contains(loc, t) for t in [country] + data["aliases"]):
            return "TIER_1_COUNTRY"
        if any(_loc_contains(loc, city) for city in data["cities"]):
            return "TIER_2_COUNTRY_CITY"
        return "NO_MATCH"

    if any(_loc_contains(loc, t) for t in wanted["exact_terms"]):
        return "TIER_1_EXACT"

    if any(_loc_contains(loc, t) for t in wanted["nearby_terms"]):
        return "TIER_2_NEARBY"

    if wanted.get("country"):
        data = COUNTRY_DATA[wanted["country"]]
        if any(_loc_contains(loc, city) for city in data["cities"]):
            return "TIER_3_SAME_COUNTRY"
        if any(_loc_contains(loc, t) for t in [wanted["country"]] + data["aliases"]):
            return "TIER_4_COUNTRY_KEYWORD"

    return "NO_MATCH"


def location_fit(profile_location, wanted):
    if wanted.get("type") == "MULTI":
        if not profile_location:
            return "UNVERIFIED"
        labels = []
        for option in wanted.get("options", []):
            for variant in _candidate_location_variants(profile_location):
                labels.append(_location_fit_single(variant, option))
        return max(labels, key=_location_rank) if labels else "NO_MATCH"

    variants = _candidate_location_variants(profile_location)
    if not variants:
        return _location_fit_single(profile_location, wanted)
    labels = [_location_fit_single(v, wanted) for v in variants]
    return max(labels, key=_location_rank)

def location_score_value(location_fit_label):
    return {
        "TIER_1_GLOBAL": 1.00,
        "TIER_1_EXACT": 1.00,
        "TIER_1_COUNTRY": 1.00,
        "TIER_1_ADMIN": 1.00,
        "TIER_1_REGION_COUNTRY": 1.00,
        "TIER_2_ADMIN_CITY": 0.92,
        "TIER_2_REGION_CITY": 0.90,
        "TIER_2_NEARBY": 0.90,
        "TIER_2_COUNTRY_CITY": 0.90,
        "TIER_3_SAME_COUNTRY": 0.75,
        "TIER_4_COUNTRY_KEYWORD": 0.65,
        "UNVERIFIED": 0.45,
    }.get(location_fit_label, 0.0)

# ------------------------- Search query generation -------------------------

def search_terms_for(skill):
    """Known skills get aliases/ecosystem; unknown skills keep recruiter wording."""
    if skill in SKILLS:
        vals = [skill] + SKILLS.get(skill, []) + RELATED.get(skill, [])[:3]
    else:
        vals = [skill]
    cleaned = []
    for x in vals:
        x = normalize(x)
        if len(x) >= 2 and x not in cleaned:
            cleaned.append(x)
    return cleaned[:5]

def _search_signal_weight(term):
    high = {
        "kubernetes": 9, "distributed systems": 9, "system design": 8, "api design": 8,
        "cloud infrastructure": 9, "platform engineering": 9, "microservices": 8,
        "grpc": 8, "terraform": 8, "docker": 7, "kafka": 7, "llm": 7, "rag": 7,
        "ai agents": 8, "model serving": 8, "observability": 7, "workflow orchestration": 7,
        "asynchronous systems": 7, "cni": 8, "networking": 6,
    }
    languages = {"python","java","go","rust","c++","c#","kotlin","scala","javascript","typescript"}
    if term in high:
        return high[term]
    if term in languages:
        return 4
    return 5

def build_discovery_queries(criteria):
    """
    Cluster-aware discovery: high-signal capabilities first, then language/core pairs,
    then semantic recall. Alternatives do not consume the entire query budget.
    """
    must = criteria["must"]
    nice = criteria.get("nice", [])
    clusters = criteria.get("must_clusters", [])

    prioritized = sorted(must, key=lambda s: (_search_signal_weight(s), -must.index(s)), reverse=True)
    queries = []

    for s in prioritized[:6]:
        term = normalize(s)
        if len(term) >= 2:
            queries.append(("CORE", f'"{term}" in:name,description,readme fork:false archived:false'))

    # Pair high-signal capability with a few language alternatives instead of language-vs-language noise.
    languages = [s for s in prioritized if s in {"python","java","go","rust","c++","c#","kotlin","scala"}]
    capabilities = [s for s in prioritized if _search_signal_weight(s) >= 7 and s not in languages]
    if capabilities:
        anchor = capabilities[0]
        for lang in languages[:3]:
            queries.append(("CORE_PAIR",
                            f'"{normalize(anchor)}" "{normalize(lang)}" in:name,description,readme fork:false archived:false'))

    # High-value NICE terms help recall, but remain NICE in scoring.
    for s in sorted(nice, key=_search_signal_weight, reverse=True)[:3]:
        if _search_signal_weight(s) >= 7:
            queries.append(("NICE_RECALL", f'"{normalize(s)}" in:name,description,readme fork:false archived:false'))

    for s in criteria.get("context", [])[:3]:
        queries.append(("SEMANTIC", f'"{normalize(s)}" in:name,description,readme fork:false archived:false'))

    seen, final = set(), []
    for layer, query in queries:
        if query not in seen:
            seen.add(query)
            final.append((layer, query))
    return final[:14]

def _country_backbone_terms(wanted):
    """
    Convert precise recruiter geography into stable country-level discovery terms.
    City/admin precision is preserved later in location_fit as a ranking bonus.
    """
    if wanted["type"] == "GLOBAL":
        return []

    if wanted["type"] == "MULTI":
        out = []
        for opt in wanted.get("options", []):
            out.extend(_country_backbone_terms(opt))
        return list(dict.fromkeys(out))

    if wanted["type"] in {"CITY", "ADMIN", "COUNTRY"} and wanted.get("country"):
        return [wanted["country"]]

    if wanted["type"] == "REGION":
        # Region search is represented by its countries. Limit is applied by caller.
        return list(wanted.get("region_countries", []))

    return []

def _location_search_terms(wanted):
    # Compatibility alias: discovery is intentionally country-first now.
    return _country_backbone_terms(wanted)

def _representative_region_countries(region_option):
    countries = list(region_option.get("region_countries", []))
    region = region_option.get("region")
    preferred = {
        "europe": ["germany", "united kingdom", "france", "netherlands"],
        "dach": ["germany", "austria", "switzerland"],
        "apac": ["india", "singapore", "japan", "australia"],
        "emea": ["germany", "united kingdom", "united arab emirates", "south africa"],
        "north america": ["united states", "canada", "mexico"],
        "latam": ["brazil", "mexico", "argentina", "colombia"],
    }.get(region, [])
    ordered = [c for c in preferred if c in countries] + [c for c in countries if c not in preferred]
    return ordered

def _balanced_location_search_countries(wanted_location, max_countries=4):
    """
    Choose country discovery terms without letting a broad region consume every slot.
    Example: Europe / India / Singapore -> keep India + Singapore + representative Europe countries.
    """
    if wanted_location.get("type") != "MULTI":
        terms = _country_backbone_terms(wanted_location)
        if wanted_location.get("type") == "REGION":
            return _representative_region_countries(wanted_location)[:max_countries]
        return terms[:max_countries]

    explicit = []
    region_opts = []
    for opt in wanted_location.get("options", []):
        if opt.get("type") == "REGION":
            region_opts.append(opt)
        else:
            explicit.extend(_country_backbone_terms(opt))

    explicit = list(dict.fromkeys(explicit))
    selected = explicit[:max_countries]

    # Fill remaining slots from each region round-robin so explicit countries are never lost.
    region_lists = [_representative_region_countries(opt) for opt in region_opts]
    pos = 0
    while len(selected) < max_countries and region_lists:
        added = False
        for countries in region_lists:
            while pos < len(countries) and countries[pos] in selected:
                pos += 1
            if pos < len(countries):
                selected.append(countries[pos])
                added = True
                if len(selected) >= max_countries:
                    break
        if not added:
            break
        pos += 1

    return selected[:max_countries]

def search_users_location_aware(criteria, wanted_location, max_queries=6):
    """
    Country-first GitHub user discovery.
    City/admin inputs source country-wide; exact geography remains a ranking bonus.
    Multi-location inputs preserve explicit countries even when mixed with broad regions.
    """
    country_terms = _balanced_location_search_countries(wanted_location, max_countries=4)
    if not country_terms:
        return []

    languages = [s for s in criteria.get("must", [])
                 if s in {"python","java","go","rust","c++","c#","kotlin","scala","javascript","typescript"}]
    languages = languages[:2] or ["python", "go"]

    found = []
    used = 0
    for country in country_terms:
        for lang in languages:
            if used >= max_queries:
                return found
            q = f'location:"{country}" language:{lang} type:user'
            data = api_get("https://api.github.com/search/users", {"q": q, "per_page": 30})
            used += 1
            for item in (data or {}).get("items", []):
                login = item.get("login")
                if login:
                    found.append((login, q))
    return found

def search_repositories(query, per_page=30):
    data = api_get("https://api.github.com/search/repositories",
                   {"q": query, "per_page": min(per_page, 100)})
    return (data or {}).get("items", [])

# ------------------------- Candidate evidence ------------------------------

def candidate_evidence(username, criteria, wanted_location, discovery_hits):
    profile = fetch_user(username)
    if not profile or profile.get("type") != "User":
        return None

    # Location is a ranking signal, not a hard rejection. Recruiter can see contradiction/unverified.
    loc_fit = location_fit(profile.get("location"), wanted_location)

    repos = fetch_user_repos(username, 30)
    bio = profile.get("bio") or ""
    orientation = technical_orientation(profile, repos)
    likeness_label, likeness_factor, likeness_reasons = candidate_likeness(profile, repos)

    # Keep authored repositories for strongest evidence. Forks remain in the profile list but
    # are not allowed to create direct technical proof.
    repo_records = [(r, repo_text(r)) for r in repos if not r.get("fork")]

    def evidence_for(skill):
        sources = []
        is_known = skill in SKILLS

        ok, alias, method = (
            match_skill(bio, skill, True)
            if is_known else
            (dynamic_term_present(bio, skill), skill, "dynamic-exact")
        )
        if ok:
            sources.append(("BIO", alias, bio[:180]))

        for r, txt in repo_records:
            ok, alias, method = (
                match_skill(txt, skill, True)
                if is_known else
                (dynamic_term_present(txt, skill), skill, "dynamic-exact")
            )
            if ok:
                sources.append(("REPO", alias, r.get("name", "")))
                if len(sources) >= 4:
                    break

        # README is a validation fallback, not the first source of truth.
        if not sources:
            related_repo_candidates = []
            terms = search_terms_for(skill)
            for r, txt in repo_records[:15]:
                signal = sum(1 for t in terms if phrase_present(txt, t))
                if signal:
                    related_repo_candidates.append((signal, r))
            for _, r in sorted(related_repo_candidates, reverse=True, key=lambda x: x[0])[:2]:
                readme = fetch_readme(username, r["name"])
                ok, alias, method = (
                    match_skill(readme, skill, True)
                    if is_known else
                    (dynamic_term_present(readme, skill), skill, "dynamic-exact")
                )
                if ok:
                    sources.append(("README", alias, r["name"]))
                    break
        return sources

    must_ev = {s: evidence_for(s) for s in criteria["must"]}
    nice_ev = {s: evidence_for(s) for s in criteria["nice"]}

    matched_must = [s for s, ev in must_ev.items() if ev]
    matched_nice = [s for s, ev in nice_ev.items() if ev]

    # Detect exact known technologies present anywhere in public profile metadata.
    # Used only for directional framework inference.
    public_text = " ".join([bio] + [txt for _, txt in repo_records])
    candidate_exact_skills = set(extract_known_skills(public_text, allow_fuzzy=False))

    inferred_must = {}
    for target in criteria["must"]:
        if target in matched_must or target not in SKILLS:
            continue
        kind, source = inferred_relation_for(target, candidate_exact_skills)
        if kind and source:
            inferred_must[target] = (kind, source)
            must_ev[target] = [(f"INFERRED_{kind}", source, f"{source} evidence")]

    inferred_nice = {}
    for target in criteria["nice"]:
        if target in matched_nice or target not in SKILLS:
            continue
        kind, source = inferred_relation_for(target, candidate_exact_skills)
        if kind and source:
            inferred_nice[target] = (kind, source)
            nice_ev[target] = [(f"INFERRED_{kind}", source, f"{source} evidence")]

    # Related context remains discovery/ranking context only.
    context_ev = {}
    for s in criteria.get("context", [])[:10]:
        ev = evidence_for(s)
        if ev:
            context_ev[s] = ev

    # Flexible pool: do not hard reject weak profiles. Discovery itself earned visibility.
    # We only exclude invalid/non-user profiles above.
    return {
        "username": username, "profile": profile, "repos": repos,
        "location_fit": loc_fit, "must_ev": must_ev, "nice_ev": nice_ev,
        "context_ev": context_ev, "matched_must": matched_must,
        "matched_nice": matched_nice, "inferred_must": inferred_must,
        "inferred_nice": inferred_nice, "candidate_exact_skills": candidate_exact_skills,
        "discovery_hits": discovery_hits,
        "technical_orientation": orientation,
        "candidate_likeness": likeness_label,
        "candidate_likeness_factor": likeness_factor,
        "candidate_likeness_reasons": likeness_reasons,
    }


def relevant_activity_freshness(c, criteria):
    """
    Summarize recency of repositories that actually supported recruiter requirements.
    Old evidence is not rejection; it only slightly affects confidence.
    """
    repo_names = set()
    for bucket in [c.get("must_ev", {}), c.get("nice_ev", {}), c.get("context_ev", {})]:
        for evs in bucket.values():
            for item in evs:
                if item and item[0] in {"REPO", "README"} and len(item) >= 3:
                    repo_names.add(item[2])

    dates = []
    for r in c.get("repos", []):
        if r.get("name") not in repo_names:
            continue
        raw = r.get("pushed_at") or r.get("updated_at")
        if not raw:
            continue
        try:
            dates.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except Exception:
            pass

    if not dates:
        return {"label": "UNKNOWN", "value": 0.50, "latest": None}

    latest = max(dates)
    now = datetime.now(timezone.utc)
    years = max(0.0, (now - latest).days / 365.25)

    if years <= 2:
        label, value = "RECENT", 1.00
    elif years <= 4:
        label, value = "ESTABLISHED", 0.75
    elif years <= 7:
        label, value = "OLDER_RELEVANT", 0.50
    else:
        label, value = "HISTORICAL", 0.30

    return {"label": label, "value": value, "latest": latest.date().isoformat()}


def _orientation_key(name):
    return {
        "PLATFORM_INFRASTRUCTURE": "PLATFORM_INFRA",
        "PLATFORM_INFRA": "PLATFORM_INFRA",
        "BACKEND": "BACKEND", "FRONTEND": "FRONTEND", "FULLSTACK": "FULLSTACK",
        "DATA": "DATA", "AI_ML": "AI_ML", "MOBILE": "MOBILE", "SECURITY": "SECURITY",
    }.get(name, name)

def candidate_role_fit(c, criteria):
    wanted = criteria.get("technical_orientation") or {}
    cand = c.get("technical_orientation") or {}
    wp = wanted.get("primary")
    if not wp or wp == "GENERAL":
        return 0.50

    cpcts = cand.get("percentages", {})
    primary_key = _orientation_key(wp)
    primary_pct = cpcts.get(primary_key, 0)
    primary_fit = min(1.0, primary_pct / 45.0)

    secondary = wanted.get("secondary")
    if secondary:
        secondary_pct = cpcts.get(_orientation_key(secondary), 0)
        secondary_fit = min(1.0, secondary_pct / 35.0)
        return 0.72 * primary_fit + 0.28 * secondary_fit
    return primary_fit

def score_candidate(c, criteria):
    must_clusters = criteria.get("must_clusters") or [{"label": s, "members": [s]} for s in criteria["must"]]
    nice_clusters = criteria.get("nice_clusters") or [{"label": s, "members": [s]} for s in criteria["nice"]]

    must_cov, must_cluster_details = cluster_coverage(
        must_clusters, set(c["matched_must"]), c.get("inferred_must", {})
    )
    nice_cov, nice_cluster_details = cluster_coverage(
        nice_clusters, set(c["matched_nice"]), c.get("inferred_nice", {})
    )

    all_req_ev = []
    for s in criteria["must"]:
        if c["must_ev"].get(s):
            all_req_ev.append(evidence_strength(c["must_ev"][s], c["repos"]))
    evidence_quality = sum(all_req_ev) / len(all_req_ev) if all_req_ev else 0.0

    context_strength = min(1.0, len(c["context_ev"]) / 4)
    location_score = location_score_value(c["location_fit"])
    hits = (c.get("discovery_hits") or {}).get("hits", 0)
    discovery_strength = min(1.0, hits / 4)
    likeness = c.get("candidate_likeness_factor", 1.0)
    freshness_value = (c.get("freshness") or {}).get("value", 0.50)
    role_fit = candidate_role_fit(c, criteria)

    # Technical requirements dominate. Role orientation comes next.
    # Location is important but primarily breaks close technical ties.
    if criteria["nice"]:
        technical = (
            52 * must_cov +
            9 * nice_cov +
            15 * evidence_quality +
            5 * context_strength +
            1 * discovery_strength
        )
        score = technical + 9 * role_fit + 7 * location_score + 2 * freshness_value
    else:
        technical = (
            61 * must_cov +
            18 * evidence_quality +
            5 * context_strength +
            1 * discovery_strength
        )
        score = technical + 9 * role_fit + 5 * location_score + 2 * freshness_value

    # Content/community accounts need a meaningful, not cosmetic, downrank.
    if likeness < 1.0:
        score *= (0.65 + 0.35 * likeness)

    score = round(max(0, min(100, score)))

    if score >= 80:
        label = "HIGH RELEVANCE"
    elif score >= 60:
        label = "GOOD RELEVANCE"
    elif score >= 40:
        label = "MODERATE RELEVANCE"
    elif score >= 20:
        label = "LOW / EXPLORATORY"
    else:
        label = "VERY LOW / DISCOVERY ONLY"

    c["must_cluster_details"] = must_cluster_details
    c["nice_cluster_details"] = nice_cluster_details
    c["must_cluster_coverage"] = must_cov
    c["nice_cluster_coverage"] = nice_cov
    c["evidence_quality"] = evidence_quality
    c["technical_score_before_location"] = technical
    c["role_fit"] = role_fit
    return score, label

def evidence_summary(ev):
    bits = []
    for typ, alias, where in ev[:3]:
        if typ == "BIO":
            bits.append(f"bio ('{alias}')")
        elif typ == "INFERRED_STRONG":
            bits.append(f"strong framework inference from {alias}")
        elif typ == "INFERRED_ECOSYSTEM":
            bits.append(f"related ecosystem signal from {alias}")
        else:
            bits.append(f"{typ.lower()} {where} ('{alias}')")
    return "; ".join(bits)

# ------------------------------ Sourcing ----------------------------------

def discover_candidates(criteria, wanted_location):
    queries = build_discovery_queries(criteria)
    owners = defaultdict(lambda: {"hits": 0, "layers": set(), "repos": set()})

    print("\nSEARCH PLAN")
    print("-" * 80)
    print(f"Discovery queries: {len(queries)} (core + semantic recall)")
    for idx, (layer, query) in enumerate(queries, 1):
        print(f"[{idx}/{len(queries)}] {layer}: {query[:100]}")
        repos = search_repositories(query, per_page=30)
        for repo in repos:
            owner = repo.get("owner") or {}
            # Repository owner can be an organization; only individuals become candidates.
            if owner.get("type") != "User":
                continue
            u = owner.get("login")
            if not u:
                continue
            if criteria.get("source") == "ICP" and u.lower() == criteria.get("icp_username", "").lower():
                continue
            owners[u]["hits"] += 1
            owners[u]["layers"].add(layer)
            owners[u]["repos"].add(repo.get("full_name", ""))

    # Supplement global repo discovery with location-aware user discovery.
    for username, q in search_users_location_aware(criteria, wanted_location):
        if criteria.get("source") == "ICP" and username.lower() == criteria.get("icp_username", "").lower():
            continue
        owners[username]["hits"] += 1
        owners[username]["layers"].add("LOCATION_USER")
        owners[username]["repos"].add("user-search:" + q)

    # Enrich a balanced pool. For a requested geography, reserve capacity for
    # location-sourced users instead of allowing global repo hits to consume all 80 slots.
    all_ranked = sorted(owners.items(), key=lambda kv: kv[1]["hits"], reverse=True)

    if wanted_location.get("type") != "GLOBAL":
        location_ranked = [
            item for item in all_ranked
            if "LOCATION_USER" in item[1]["layers"]
        ]
        technical_ranked = [
            item for item in all_ranked
            if "LOCATION_USER" not in item[1]["layers"]
        ]

        selected = []
        seen_users = set()

        # Up to 45 location-aware candidates + 35 global technical candidates.
        for item in location_ranked[:45] + technical_ranked[:35]:
            username = item[0].lower()
            if username not in seen_users:
                seen_users.add(username)
                selected.append(item)

        # Fill any unused capacity from the global ranked pool.
        if len(selected) < 80:
            for item in all_ranked:
                username = item[0].lower()
                if username in seen_users:
                    continue
                selected.append(item)
                seen_users.add(username)
                if len(selected) >= 80:
                    break

        ranked_owners = selected
        print(f"\nDiscovery pool: {len(all_ranked)} unique users | "
              f"enriching {len(ranked_owners)} "
              f"({min(len(location_ranked),45)} location-aware + technical fallback)")
    else:
        ranked_owners = all_ranked[:80]
        print(f"\nDiscovery pool: {len(all_ranked)} unique individual GitHub users")

    return ranked_owners[:80]



def location_priority_band(location_fit_label):
    """
    Final shortlist ordering for a recruiter-requested geography:
      2 = confirmed geographic match
      1 = location not public / unverifiable
      0 = confirmed mismatch
    Technical score still orders candidates inside each band.
    """
    if location_fit_label == "UNVERIFIED":
        return 1
    if location_fit_label == "NO_MATCH":
        return 0
    if str(location_fit_label).startswith("TIER_"):
        return 2
    return 0

def light_diversity_rerank(candidates, batch_size=10):
    """
    Preserve score order, but avoid flooding a batch with community/content profiles
    when similarly scored individual engineers exist nearby.
    Only swaps candidates within a 5-point relevance window.
    """
    candidates = list(candidates)
    for batch_start in range(0, len(candidates), batch_size):
        batch_end = min(batch_start + batch_size, len(candidates))
        non_individual = 0
        for i in range(batch_start, batch_end):
            if candidates[i].get("candidate_likeness") == "INDIVIDUAL":
                continue
            non_individual += 1
            if non_individual <= 2:
                continue

            # Find a nearby individual with almost the same score.
            for j in range(batch_end, min(len(candidates), batch_end + 15)):
                if candidates[j].get("candidate_likeness") != "INDIVIDUAL":
                    continue
                if candidates[i]["score"] - candidates[j]["score"] <= 5:
                    candidates[i], candidates[j] = candidates[j], candidates[i]
                    non_individual -= 1
                    break
    return candidates

def run_sourcing(criteria, wanted_location):
    discovered = discover_candidates(criteria, wanted_location)
    candidates = []

    print("\nEVIDENCE VALIDATION")
    print("-" * 80)
    for i, (username, hitdata) in enumerate(discovered, 1):
        print(f"\rValidating public GitHub evidence {i}/{len(discovered)}...", end="", flush=True)
        c = candidate_evidence(username, criteria, wanted_location, hitdata)
        if c:
            c["freshness"] = relevant_activity_freshness(c, criteria)
            c["score"], c["label"] = score_candidate(c, criteria)
            candidates.append(c)
    print()

    if wanted_location.get("type") == "GLOBAL":
        candidates.sort(
            key=lambda c: (c["score"], len(c["matched_must"]), len(c["matched_nice"])),
            reverse=True
        )
    else:
        # Requested geography is treated as a shortlist constraint:
        # confirmed matches first, unverifiable second, confirmed mismatches last.
        candidates.sort(
            key=lambda c: (
                location_priority_band(c["location_fit"]),
                c["score"],
                len(c["matched_must"]),
                len(c["matched_nice"])
            ),
            reverse=True
        )

    return light_diversity_rerank(candidates, batch_size=10)

# ------------------------------ Display -----------------------------------

def print_analysis(c):
    print("\n" + "="*100)
    print("JOB / ICP INTELLIGENCE")
    print("="*100)
    print(f"Source: {c['source']}")
    print(f"Role family: {c['domain']} ({c['domain_confidence']}% inference confidence)")
    if c.get("icp_mode_note"):
        print(f"ICP interpretation: {c['icp_mode_note']}")
    if c["specializations"]:
        print("Specialization:", ", ".join(x[0] for x in c["specializations"]))
    if c.get("technical_orientation"):
        o = c["technical_orientation"]
        print(f"Technical orientation: {o.get('primary','UNKNOWN')}"
              + (f" | secondary={o.get('secondary')}" if o.get('secondary') else ""))
        if o.get("percentages"):
            print("Orientation mix: " + ", ".join(f"{k} {v}%" for k, v in list(o["percentages"].items())[:5]))
    if c.get("experience"):
        print(f"Experience requested: {c['experience']['display']} (requirement only; GitHub cannot verify employment tenure reliably)")
    elif c.get("years") is not None:
        print(f"Experience requested: {c['years']}+ years (requirement only; GitHub cannot verify employment tenure reliably)")
    print(f"MUST ({len(c['must'])}): {', '.join(c['must']) or 'None extracted'}")
    print(f"NICE ({len(c['nice'])}): {', '.join(c['nice']) or 'None extracted'}")
    if c.get("must_unknown"):
        print("Open-world MUST entities preserved:", ", ".join(c["must_unknown"]))
    if c.get("nice_unknown"):
        print("Open-world NICE entities preserved:", ", ".join(c["nice_unknown"]))
    print(f"Semantic search context: {', '.join(c['context']) or 'None'}")
    if c.get("must_clusters"):
        print(f"Requirement groups: {len(c['must_clusters'])} MUST / {len(c.get('nice_clusters', []))} NICE")
        any_groups = [x for x in c["must_clusters"] if x.get("mode") == "ANY"]
        for group in any_groups[:4]:
            print("  ANY-OF requirement: " + " OR ".join(group["members"]))
    print("\nNote: semantic context expands discovery only. It does NOT change recruiter-entered MUST/NICE.")
    print("Scoring is flexible: weak/adjacent candidates stay visible lower in the ranking instead of being silently rejected.")
    print("For a requested geography, confirmed location matches are shortlisted first; UNVERIFIED and NO_MATCH remain visible as fallback.")

def _cluster_status(cluster, c):
    members = cluster["members"]
    direct = set(c.get("matched_must", []))
    inferred = c.get("inferred_must", {})
    matched = [m for m in members if m in direct or m in inferred]
    mode = cluster.get("mode", "ALL")
    if mode == "ANY":
        return bool(matched), matched, [m for m in members if m not in matched]
    return len(matched) == len(members), matched, [m for m in members if m not in matched]

def print_candidate(c, criteria, rank):
    p = c["profile"]
    print("\n" + "-"*100)
    print(f"{rank}. {p.get('name') or c['username']} (@{c['username']}) — {c['score']}/100 — {c['label']}")
    print(p.get("html_url") or f"https://github.com/{c['username']}")
    print(f"Location: {p.get('location') or 'Not public'} [{c['location_fit']}]")

    o = c.get("technical_orientation") or {}
    if o.get("primary"):
        mix = ", ".join(f"{k} {v}%" for k, v in list(o.get("percentages", {}).items())[:4])
        secondary = f" / {o['secondary']}" if o.get("secondary") else ""
        print(f"Orientation: {o['primary']}{secondary}" + (f" [{mix}]" if mix else ""))

    if p.get("bio"):
        print(f"Bio: {p['bio'][:180]}")

    if c.get("candidate_likeness") != "INDIVIDUAL":
        reasons = ", ".join(c.get("candidate_likeness_reasons") or [])
        print(f"Profile-type signal: {c.get('candidate_likeness')} — downranked"
              + (f" ({reasons})" if reasons else ""))

    print("Core requirement groups:")
    for cluster in criteria.get("must_clusters", []):
        satisfied, matched, missing = _cluster_status(cluster, c)
        mode = cluster.get("mode", "ALL")
        symbol = "✓" if satisfied else ("◐" if matched else "?")
        if mode == "ANY":
            member_text = " OR ".join(cluster["members"])
            if matched:
                print(f"  {symbol} ANY [{member_text}] → verified: {', '.join(matched)}")
            else:
                print(f"  {symbol} ANY [{member_text}] → not verified")
        else:
            label = cluster["label"]
            if matched:
                print(f"  {symbol} {label} → verified: {', '.join(matched)}"
                      + (f" | missing: {', '.join(missing)}" if missing else ""))
            else:
                print(f"  {symbol} {label} → not verified")

    nice_matches = [s for s in criteria["nice"]
                    if s in c["matched_nice"] or s in c.get("inferred_nice", {})]
    if nice_matches:
        print("Supporting/NICE verified: " + ", ".join(nice_matches[:8]))

    if c.get("context_ev"):
        print("Related ecosystem: " + ", ".join(list(c["context_ev"].keys())[:6]))

    freshness = c.get("freshness") or {}
    if freshness:
        latest = f" | latest relevant repo activity: {freshness['latest']}" if freshness.get("latest") else ""
        print(f"Relevant activity: {freshness.get('label','UNKNOWN')}{latest}")

    hitdata = c.get("discovery_hits") or {}
    layers = sorted(hitdata.get("layers") or [])
    repos = sorted(r for r in (hitdata.get("repos") or []) if r)[:2]
    if layers:
        print("Found via: " + ", ".join(layers) + (f" | discovery refs: {', '.join(repos)}" if repos else ""))

    print(
        "Why this score: "
        f"MUST groups {round(c.get('must_cluster_coverage',0)*100)}% | "
        f"NICE {round(c.get('nice_cluster_coverage',0)*100)}% | "
        f"evidence {round(c.get('evidence_quality',0)*100)}% | "
        f"role-fit {round(c.get('role_fit',0)*100)}% | "
        f"location {c['location_fit']}."
    )
    print("Note: 'not verified' means public GitHub evidence was not found; it does not prove the skill is absent.")

def paginate(candidates, criteria, batch=10):
    if not candidates:
        print("\nNo individual GitHub candidates were discovered for the generated queries. Try broader search terms or location.")
        return
    print(f"\nRanked candidates: {len(candidates)}")
    start = 0
    while start < len(candidates):
        end = min(start + batch, len(candidates))
        print("\n" + "="*100)
        print(f"RESULTS {start+1}-{end} OF {len(candidates)}")
        print("="*100)
        for i in range(start, end):
            print_candidate(candidates[i], criteria, i+1)
        start = end
        if start >= len(candidates):
            break
        ans = input(f"\nShow next {min(batch, len(candidates)-start)}? (y/n): ").strip().lower()
        if ans not in {"y", "yes"}:
            break

# ------------------------------- Main -------------------------------------

def read_multiline():
    print("Paste requirement. Finish with a line containing only END:")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()

def username_from_input(value):
    value = value.strip().rstrip("/")
    if "github.com/" in value:
        return value.split("github.com/", 1)[1].split("/", 1)[0]
    return value.lstrip("@")


ROLE_WIZARD_PRESETS = {
    "1": {
        "name": "Frontend",
        "must": ["react", "typescript"],
        "suggestions": ["next.js", "vue", "angular", "svelte", "graphql", "design systems"],
    },
    "2": {
        "name": "Backend",
        "must": [],
        "suggestions": ["python", "java", "go", "c#", "rust", "distributed systems", "system design", "api design"],
    },
    "3": {
        "name": "Fullstack",
        "must": [],
        "suggestions": ["react", "typescript", "node.js", "python", "java", "go", "postgresql"],
    },
    "4": {
        "name": "Platform / Infrastructure",
        "must": [],
        "suggestions": ["kubernetes", "terraform", "linux", "aws", "gcp", "azure", "helm", "gitops", "networking"],
    },
    "5": {
        "name": "Data",
        "must": [],
        "suggestions": ["sql", "spark", "kafka", "airflow", "dbt", "snowflake", "databricks"],
    },
    "6": {
        "name": "AI / ML",
        "must": [],
        "suggestions": ["python", "pytorch", "tensorflow", "llm", "rag", "hugging face", "mlops", "ai agents"],
    },
    "7": {
        "name": "Mobile",
        "must": [],
        "suggestions": ["swift", "kotlin", "ios", "android", "flutter", "react native"],
    },
    "8": {
        "name": "Security",
        "must": [],
        "suggestions": ["application security", "cloud security", "kubernetes security", "iam", "owasp"],
    },
    "9": {
        "name": "Custom / Other",
        "must": [],
        "suggestions": [],
    },
}

def _split_csv_input(raw):
    return [x.strip() for x in re.split(r"[,;]", raw or "") if x.strip()]

def build_universal_wizard_brief():
    print("\nROLE FAMILY")
    print("-" * 80)
    print("1. Frontend")
    print("2. Backend")
    print("3. Fullstack")
    print("4. Platform / Infrastructure")
    print("5. Data")
    print("6. AI / ML")
    print("7. Mobile")
    print("8. Security")
    print("9. Custom / Other")

    choice = input("\nChoose role family 1-9: ").strip()
    preset = ROLE_WIZARD_PRESETS.get(choice)
    if not preset:
        print("Invalid role choice.")
        return None, None

    role_name = preset["name"]
    role_title = input(f"\nRole title [{role_name}]: ").strip() or role_name

    if preset["suggestions"]:
        print("\nUseful examples for this role:")
        print(", ".join(preset["suggestions"]))

    print("\nEnter MUST-HAVE skills/capabilities separated by commas.")
    print("Examples: React, TypeScript, Next.js  OR  Kubernetes, Terraform, Go")
    must_raw = input("MUST HAVE: ").strip()
    must_items = _split_csv_input(must_raw)

    if not must_items and preset["must"]:
        must_items = list(preset["must"])

    if not must_items:
        print("At least one MUST-HAVE capability is required.")
        return None, None

    nice_raw = input("\nNICE TO HAVE (comma-separated, optional): ").strip()
    nice_items = _split_csv_input(nice_raw)

    location = input(
        "\nLocation (city / state / country / region / multi-location / global): "
    ).strip() or "global"

    lines = [f"Role: {role_title}", "", "MUST HAVE:"]
    for item in must_items:
        lines.append(f"- {item}")

    if nice_items:
        lines.extend(["", "NICE TO HAVE:"])
        for item in nice_items:
            lines.append(f"- {item}")

    return "\n".join(lines), location

def main():
    print("\n" + "="*100)
    print("UNIVERSAL GITHUB SOURCING ENGINE v1.0 — ROLE-AGNOSTIC")
    print("="*100)
    if not TOKEN:
        print("⚠️ GITHUB_TOKEN is not set. Public API limits will be much lower.")
    show_rate_limit()

    print("\n1. Universal Role Wizard")
    print("2. Ideal GitHub Profile (ICP → reference capability bar)")
    print("3. Recruiter Brief (explicit MUST / NICE)")
    choice = input("\nChoose 1, 2 or 3: ").strip()

    location_raw = None

    if choice == "1":
        brief, location_raw = build_universal_wizard_brief()
        if not brief:
            return
        criteria = analyze_brief(brief, source="WIZARD")

    elif choice == "2":
        raw = input("\nGitHub username or profile URL: ").strip()
        username = username_from_input(raw)
        print(f"\nAnalyzing public GitHub evidence for @{username}...")
        criteria = profile_identity(username)
        if not criteria:
            print("Could not analyze that individual public GitHub profile.")
            return

    elif choice == "3":
        print("\nRecommended brief format:")
        print("Role: <role title>")
        print("MUST HAVE:")
        print("- <core requirement>")
        print("NICE TO HAVE:")
        print("- <supporting requirement>")
        brief = read_multiline()
        if not brief:
            print("No requirement entered.")
            return
        criteria = analyze_brief(brief, source="BRIEF")

    else:
        print("Invalid choice.")
        return

    print_analysis(criteria)

    if not criteria["must"]:
        print("\n⚠️ No reliable core technical requirements were extracted.")
        return

    if not location_raw:
        location_raw = input(
            "\nLocation (city / state / country / region / multi-location / global): "
        ).strip() or "global"

    wanted_location = parse_location(location_raw)

    print(f"Location mode: {wanted_location['type']} — input={wanted_location['raw']} | "
          f"city={wanted_location.get('city') or '-'} | "
          f"admin={wanted_location.get('admin') or '-'} | "
          f"country={wanted_location.get('country') or '-'} | "
          f"region={wanted_location.get('region') or '-'}")

    if wanted_location.get("type") == "MULTI":
        resolved = []
        for opt in wanted_location.get("options", []):
            resolved.append(
                f"{opt.get('raw')}→{opt.get('city') or opt.get('admin') or opt.get('country') or opt.get('region') or opt.get('type')}"
            )
        print("Accepted locations: " + " | ".join(resolved))

    backbone = _country_backbone_terms(wanted_location)
    if backbone:
        shown = backbone[:8]
        suffix = " ..." if len(backbone) > len(shown) else ""
        print("Country-first discovery backbone: " + ", ".join(shown) + suffix)

    confirm = input("\nRun GitHub sourcing with this analysis? (y/n): ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("Stopped before search.")
        return

    candidates = run_sourcing(criteria, wanted_location)
    paginate(candidates, criteria, batch=10)

if __name__ == "__main__":
    main()
