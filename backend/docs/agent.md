# Australian Legal Agent – Professional Workflow Design

## 1. Document Purpose

This document defines a **complete, professional-grade Legal Agent workflow** for an Australian legal consultation application.

The Legal Agent is **not a virtual lawyer**.  
Its purpose is to replicate the **reasoning structure of a real Australian lawyer during early-stage consultations**, while remaining compliant with Australian legal and regulatory constraints.

The workflow is designed to:
- Handle **complex, multi-issue legal scenarios**
- Structure unorganised user narratives into legal facts
- Reduce legal uncertainty and surface risk
- Support decision-making without providing legal advice
- Seamlessly escalate complex matters to qualified lawyers

---

## 2. Core Design Philosophy

> A professional legal agent does not decide outcomes.  
> It **identifies legal issues**, **tests legal elements**, **assesses risk**, and **guides lawful next steps**.

This mirrors how real lawyers think and advise in practice.

Key principles:
- Explain uncertainty, not certainty
- Separate facts from conclusions
- Prefer structured reasoning over free-text answers
- Always allow escalation to human professionals

---

## 3. High-Level Workflow Overview

[0] Intake & Safety Gate (Compliance)
↓
[1] Legal Issue Identification (Multi-label)
↓
[2] Jurisdiction & Applicable Law Resolution
↓
[3] Fact Structuring & Timeline Construction
↓
[4] Legal Elements Mapping (Rule-based)
↓
[5] Case & Precedent Reasoning (Pattern-based)
↓
[6] Risk, Defence & Counterfactual Analysis
↓
[7] Strategy & Pathway Recommendation
↓
[8] Escalation & Lawyer Handoff


Each stage corresponds directly to a real-world lawyer’s mental workflow.

---

## 4. Detailed Workflow Stages

---

## [0] Intake & Safety Gate – Compliance Layer

### Purpose
Identify scenarios that **cannot be safely handled by an automated legal agent**.

### Typical High-Risk Scenarios
- Criminal charges or police involvement
- Family violence or personal safety risk
- Urgent court deadlines or limitation periods
- Active litigation requiring legal representation

### Agent Behaviour
- Stop legal reasoning immediately
- Display clear disclaimers
- Redirect to emergency services, community legal centres, or lawyers

This layer protects users, lawyers, and the platform.

---

## [1] Legal Issue Identification – Legal Triage

### Purpose
Translate user narratives into **structured legal problem definitions**.

### Key Characteristics
- Multi-label classification (one case may involve many legal issues)
- Separation of *primary* and *secondary* issues
- Neutral framing (no blame, no conclusions)

### Example Output
Primary Legal Area: Employment Law

Identified Issues:

Unfair dismissal

Underpayment of wages

Procedural fairness concerns


This mirrors how lawyers frame causes of action.

---

## [2] Jurisdiction & Applicable Law Resolution

### Purpose
Determine **which laws and forums apply**.

### Factors Considered
- State or Territory location
- Commonwealth vs State legislation
- Subject-matter specific statutes
- Legislative hierarchy (statute > common law > equity)

### Example Output
Jurisdiction: Victoria

Applicable Law:

Fair Work Act 2009 (Cth)

Fair Work Regulations

Likely Forum:

Fair Work Commission


Correct jurisdiction resolution is foundational to all later reasoning.

---

## [3] Fact Structuring & Timeline Construction

### Purpose
Convert unstructured narratives into **legally usable facts**.

### Key Outputs
- Chronological timeline
- Identified parties and roles
- Evidence availability and strength
- Missing or unclear information

### Example
Timeline:

3 Mar 2024: Employment commenced

15 Apr 2024: Partial wage payment

30 Apr 2024: Termination notice issued

Evidence:

Employment contract: Yes

Payslips: Partial

Emails / messages: Yes

This step enables the system to handle **complex, multi-event cases**.

---

## [4] Legal Elements Mapping – Rule-Based Reasoning

### Purpose
Test whether **legal elements required by law are satisfied**, without drawing conclusions.

### Method
- Load predefined legal element schemas
- Map structured facts to each element
- Track confidence and uncertainty

### Example
Unfair Dismissal – Legal Elements

[✓] Employment relationship exists
[?] Minimum employment period unclear
[✓] Dismissal occurred
[✗] Procedural fairness evidence missing


The agent reports **coverage**, not outcomes.

---

## [5] Case & Precedent Reasoning – Pattern-Based Analysis

### Purpose
Use historical cases to **identify trends and patterns**, not to provide legal opinions.

### Method
- Retrieve factually similar cases from database
- Cluster by outcomes and key factors
- Extract common success and failure indicators

### Example
Comparable Cases (VIC, past 5 years):

3 similar cases identified

Outcomes: 2 successful, 1 unsuccessful

Observed Patterns:

Success often linked to lack of written notice

Failure often linked to short employment duration


This reflects how lawyers reason with precedent in practice.

---

## [6] Risk, Defence & Counterfactual Analysis

### Purpose
Assess **legal and practical risk** by reasoning from the opposing side.

### Outputs
- Possible counterarguments or defences
- Evidence weaknesses
- Cost and procedural risk

### Example
Potential Employer Defences:

Employee did not meet minimum service period

Termination based on misconduct

Risk Assessment:

Legal Risk: Medium

Evidence Risk: High

Cost Risk: Medium


This stage is critical for professional credibility.

---

## [7] Strategy & Pathway Recommendation

### Purpose
Provide **lawful, non-prescriptive next steps**, not legal advice.

### Output Style
- Multiple options
- Trade-offs clearly explained
- No guaranteed outcomes

### Example
Available Pathways:

Option A: Lodge claim with Fair Work Commission

Cost: Low

Timeframe: Medium

Risk: Medium

Option B: Engage an employment lawyer

Cost: High

Risk reduction: High


This mirrors real lawyer consultations.

---

## [8] Escalation & Lawyer Handoff

### Purpose
Ensure smooth transition from AI-assisted triage to human legal advice.

### Lawyer Brief Pack Includes
- Identified legal issues
- Structured timeline
- Evidence summary
- Risk and uncertainty map
- Outstanding factual gaps

This significantly reduces lawyer intake time.

---

## 5. Compliance Boundary

The Legal Agent provides:
- Legal information
- Risk identification
- Process and pathway guidance

The Legal Agent does NOT provide:
- Legal advice
- Outcome predictions
- Representation or drafting of legal documents

Clear disclaimers must be displayed at all stages.

---

## 6. Indicators of Professional Quality

A legal agent is considered professional if it can:
1. Explain why a legal outcome is uncertain
2. Identify where risks originate
3. Present multiple lawful pathways
4. Support escalation to human lawyers

---

## 7. Summary

This workflow aligns:
- Australian legal reasoning
- Software architecture principles
- Regulatory and ethical constraints

It enables scalable, compliant legal triage while respecting the limits of automated legal systems.
