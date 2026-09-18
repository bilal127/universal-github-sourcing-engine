
# AI-Assisted GitHub Sourcing Engine
The engine runs locally in the terminal and fetches results from public/open-source GitHub data using API queries only - no scraping. It can be demonstrated live.

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


<img width="729" height="829" alt="Screenshot 2026-09-19 at 1 11 00 AM" src="https://github.com/user-attachments/assets/5f9d711d-3d1b-4d7b-90ef-1ac6c0c85896" />


### The strongest difference between manual Github sourcing VS Github engine sourcing:

Manual GitHub search
= find profiles

Your engine
= understand requirement
  + expand discovery
  + search
  + validate evidence
  + compare
  + rank
  + explain

So instead of just searching:

Kubernetes + Go + Terraform (usually light weight search made by recruiters)

the engine can also understand that things like:

EKS
GKE
Helm
CNI
ArgoCD
all are related to infrastructure, kuberenetes on scale

may be useful discovery signals, while still keeping the recruiter's original MUST/NICE requirements unchanged.

And after discovery, engine does something manual GitHub search does not give you automatically:

MUST coverage
NICE coverage
Evidence quality
Role fit
Location fit
Freshness
Why this candidate matched.

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
## What I learned

This project helped me understand how to convert a recruiting workflow into product logic:

Recruiting judgment
        ↓
Rules + search strategy
        ↓
Evidence model
        ↓
Scoring logic
        ↓
Working software

It also helped me think more deeply about explainability in AI-assisted recruiting workflows.

## Built with

Python 3
GitHub REST API
GitHub repository / user search
Requirement parsing
Skill + framework relationships
Location-aware discovery
Evidence-based scoring
AI-assisted coding

## Setup & Configuration

This project runs locally with Python and connects to GitHub through the official GitHub REST API.

1) Requirements

You need:

Python 3
A GitHub account
A GitHub Personal Access Token
Internet access

Check Python:

python3 --version

2) Install dependency

The engine uses the requests Python package.

Install it once:

python3 -m pip install requests

3) Create a GitHub API token

Create a GitHub Personal Access Token from your GitHub account settings.

The token is used only to authenticate API requests and increase GitHub API/search limits.

Do not paste the token into the Python source code.

Do not commit the token to GitHub.

4) Add the token locally

macOS / Linux:

export GITHUB_TOKEN='YOUR_GITHUB_TOKEN'

Check that it is loaded:

python3 -c "import os; print(bool(os.getenv('GITHUB_TOKEN')))"

Expected output:

True

The engine reads the token through:

os.getenv("GITHUB_TOKEN")

This keeps credentials outside the codebase.

5) Run the engine

From the folder containing the Python file:

python3 universal_sourcing_engine.py

Example:

cd ~/Documents
python3 universal_sourcing_engine.py

If authentication is working, the terminal should show something similar to:

API: authenticated | core 5000/5000 | search 30/30

If no token is loaded, the engine can still run with much lower public GitHub API limits.

## Authentication & Security

Recommended approach:

GitHub token
    ↓
Local environment variable
    ↓
Python engine
    ↓
GitHub API

The repository should never contain:

GitHub Personal Access Tokens
Passwords
API secrets
.env files containing credentials

Recommended .gitignore:

.env
.DS_Store
__pycache__/
*.pyc

If a token is ever accidentally committed or shared publicly, revoke it immediately and create a new one.

## GitHub API Notes

The engine uses authenticated GitHub API requests for:

User profiles
Repositories
README evidence
Repository search
User/location search
Rate-limit checks

Authentication improves API limits compared with anonymous access.

GitHub still applies separate limits to different API resources, so very large sourcing runs may eventually need to wait for rate-limit reset.

## Recommended Repository Structure

universal-github-sourcing-engine/
│
├── universal_sourcing_engine.py
├── README.md
└── .gitignore

Optional export-enabled versions can also include:

sourcing_run_latest.json
sourcing_candidates_latest.csv

Avoid committing candidate-result files if they contain data you do not want publicly available.

## Quick Start

git clone https://github.com/YOUR_USERNAME/universal-github-sourcing-engine.git
cd universal-github-sourcing-engine
python3 -m pip install requests
export GITHUB_TOKEN='YOUR_GITHUB_TOKEN'
python3 universal_sourcing_engine.py

That is enough to run the project locally.

## Current limitation

GitHub only shows public information.

The engine therefore cannot reliably know:

private repository work
complete professional experience
skills that are not publicly visible
verified years of experience

So GitHub evidence is used as a **sourcing signal**, not as a final hiring decision.
