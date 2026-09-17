# AI-Assisted GitHub Sourcing Engine

### Turning a recruiter's manual GitHub sourcing process into a repeatable sourcing workflow

I built this project around one question:

> **Can the way a recruiter manually searches GitHub be converted into a transparent sourcing engine without giving up recruiter control?**

I used **AI-assisted coding** to help turn my recruiting ideas into Python, test edge cases, debug issues, and iterate faster. The sourcing logic itself came from how I manually think about roles, search strategy, evidence, and candidate relevance.

---

## The idea in one picture

```text
Recruiter gives input
        ↓
Understand the hiring need
        ↓
Expand the search intelligently
        ↓
Query GitHub public data
        ↓
Validate candidate evidence
        ↓
Rank + explain results
        ↓
Recruiter makes the decision
```

---

## 3 ways a recruiter can start

### 1) Guided Role Builder
Choose the role family and enter:

```text
Role title
MUST HAVE skills
NICE TO HAVE skills
Location
```

### 2) Ideal GitHub Profile / ICP
Paste a public GitHub profile.

The engine analyzes repeated technical signals and creates a **reference capability bar**, then looks for candidates with similar, adjacent, or stronger evidence.

### 3) Recruiter Brief
Paste a simple structured brief:

```text
Role: Senior Platform Engineer

MUST HAVE:
- Kubernetes
- Go
- Terraform

NICE TO HAVE:
- Helm
- ArgoCD
- Prometheus
```

The recruiter's MUST / NICE requirements remain the source of truth.

---

## What happens behind the scenes?

### Step 1 — Job Intelligence

The engine does more than read keywords. It interprets:

```text
What type of role is this?
What is mandatory?
What is optional?
What technologies are related?
What location should be prioritized?
```

Example:

```text
Input:
Docker

Discovery context may also include:
containerd
Podman
```

Those related technologies improve discovery, but they do **not** silently become recruiter requirements.

---

### Step 2 — GitHub Search

The engine uses the **GitHub API and GitHub search queries**.

Instead of one giant Boolean-style search, it creates multiple focused searches around:

```text
Core skills
Capabilities
Related technologies
Location
Supporting / NICE skills
```

---

### Step 3 — Evidence Validation

Finding a profile is only discovery.

The engine then checks public GitHub evidence such as:

```text
Profile bio
Authored repositories
Repo names / descriptions
Technology signals
README evidence
Relevant activity
Technical orientation
```

Evidence is shown as:

```text
VERIFIED
INFERRED
NOT VERIFIED
```

**Not verified** does not mean the candidate lacks the skill. It only means enough public GitHub evidence was not found.

---

### Step 4 — Transparent Ranking

Candidates are ranked using signals such as:

```text
MUST coverage
NICE coverage
Evidence quality
Role fit
Location fit
Relevant activity
```

The engine also explains why the score was given.

Example:

```text
Candidate: @example
Score: 78/100

MUST coverage: 75%
NICE coverage: 50%
Evidence quality: 82%
Role fit: 90%
```

---

## Where AI helped

This project is **AI-assisted, not AI-dependent**.

I used AI mainly to help me:

```text
turn recruiter ideas into Python
structure the logic
debug problems
test edge cases
refactor code
speed up implementation
```

The important decisions remained recruiter-led:

```text
How should requirements be defined?
What should count as evidence?
What can be inferred?
What should stay recruiter-controlled?
How should discovery broaden without changing intent?
```

The engine does not need an LLM to make a hiring decision.

---

## What I learned

This project helped me understand how to convert a recruiting workflow into product logic:

```text
Recruiting judgment
        ↓
Rules + search strategy
        ↓
Evidence model
        ↓
Scoring logic
        ↓
Working software
```

It also helped me think more deeply about explainability in AI-assisted recruiting workflows.

---

## Built with

```text
Python 3
GitHub REST API
GitHub repository / user search
Requirement parsing
Skill + framework relationships
Location-aware discovery
Evidence-based scoring
AI-assisted coding
```

---

## Why this project matters

The goal is **not to replace recruiter judgment**.

The goal is to make technical sourcing:

- faster
- more repeatable
- easier to explain
- more evidence-based
- still recruiter-controlled

---

## Run locally

```bash
export GITHUB_TOKEN='YOUR_TOKEN'
python3 universal_sourcing_engine.py
```

Never hardcode or commit your GitHub token.

---

## Current limitation

GitHub only shows public information.

The engine therefore cannot reliably know:

```text
private repository work
complete professional experience
skills that are not publicly visible
verified years of experience
```

So GitHub evidence is used as a **sourcing signal**, not as a final hiring decision.
