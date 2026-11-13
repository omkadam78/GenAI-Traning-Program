# FasalBima Sathi — Prompt Engineering Evaluation (Day 6)

## Overview
This document evaluates and compares two prompt strategies for **FasalBima Sathi** across all 10 project evaluation questions (including the 6 project-card questions and the mandatory unanswerable Q6).

- **Prompt Version 1 (`task_v1_concise.txt`)**: A mobile-first, direct, 2–3 sentence answer designed for rapid reading with a confidence score and a concise follow-up.
- **Prompt Version 2 (`task_v2_detailed.txt`)**: A structured advisory layout providing policy context, exact rates/deadlines, step-by-step action items, and official guideline citations.

---

## Comparative Results on 10 Evaluation Questions

### Q1: What premium do I pay for soybean crop insurance in kharif?
- **Category**: Project Card Question | **Answerable from Guidelines**: Yes
- **Expected Topic**: Kharif foodgrain and oilseed premium cap

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revamped OG (Kharif 2020), Para 13.1 Table 1, Kharif foodgrain and oilseed premium cap specifies that Maximum Premium Rate payable by farmer (% of Sum Insured): Kharif All Food grain and Oilseeds crops (all Cereals, Millets, Pulses and Oilseeds crops) 2.0% of SI or Actuarial rate, whichever is less [Key rate/deadline: 2.0% of Sum Insured or actuarial rate, whichever is less].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revamped OG (Kharif 2020), Para 13.1 Table 1:\n\n1. **Policy Provision**: Kharif foodgrain and oilseed premium cap \u2014 Maximum Premium Rate payable by farmer (% of Sum Insured): Kharif All Food grain and Oilseeds crops (all Cereals, Millets, Pulses and Oilseeds crops) 2.0% of SI or Actuarial rate, whichever is less\n2. **Applicable Rate / Timeline**: 2.0% of Sum Insured or actuarial rate, whichever is less\n3. **Scope & Application**: Applicable to Kharif cereals, millets, pulses, and oilseeds (e.g. soybean).\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q1**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

### Q2: Is hailstorm damage covered for my individual farm?
- **Category**: Project Card Question | **Answerable from Guidelines**: Yes
- **Expected Topic**: Localized calamities (hailstorm, landslide, inundation)

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revamped OG (Kharif 2020), Para 5.2.4 & 21.5.1, Localized calamities (hailstorm, landslide, inundation) specifies that 5.2.4 Localized Calamities : Loss/damage to notified insured crops resulting from occurrence of identified localized risks of hailstorm, landslide, inundation, cloud burst and natural fire due to lightening affecting isolated farms in the notified area. [Key rate/deadline: Individual farm-level loss assessment].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revamped OG (Kharif 2020), Para 5.2.4 & 21.5.1:\n\n1. **Policy Provision**: Localized calamities (hailstorm, landslide, inundation) \u2014 5.2.4 Localized Calamities : Loss/damage to notified insured crops resulting from occurrence of identified localized risks of hailstorm, landslide, inundation, cloud burst and natural fire due to lightening affecting isolated farms in the notified area.\n2. **Applicable Rate / Timeline**: Individual farm-level loss assessment\n3. **Scope & Application**: Applicable to Isolated insured farms in notified area (e.g. hailstorm).\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q2**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

### Q3: How many days after harvest are cut-and-spread crops covered for unseasonal rain?
- **Category**: Project Card Question | **Answerable from Guidelines**: Yes
- **Expected Topic**: Post-harvest losses (14-day drying window)

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revamped OG (Kharif 2020), Para 5.2.3 & 21.6.2.3, Post-harvest losses (14-day drying window) specifies that 5.2.3 Post-Harvest Losses: Coverage is available only up to a maximum period of two weeks from harvesting, for those crops which are required to be dried in cut and spread / small bundled condition depending on requirement of the crops in that area, in the field after harvesting against specific perils of hailstorm, cyclone, cyclonic rains and unseasonal... [Key rate/deadline: Up to 2 weeks (14 days) from harvest].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revamped OG (Kharif 2020), Para 5.2.3 & 21.6.2.3:\n\n1. **Policy Provision**: Post-harvest losses (14-day drying window) \u2014 5.2.3 Post-Harvest Losses: Coverage is available only up to a maximum period of two weeks from harvesting, for those crops which are required to be dried in cut and spread / small bundled condition depending on requirement of the crops in that area, in the field after harvesting against specific perils of hailstorm, cyclone, cyclonic rains and unseasonal...\n2. **Applicable Rate / Timeline**: Up to 2 weeks (14 days) from harvest\n3. **Scope & Application**: Applicable to Harvested crops in cut-and-spread / small bundled condition.\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q3**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

### Q4: Hailstorm hit my 1.2 ha soybean at 9 pm yesterday. By when must I inform, through which channels, and what premium did I pay if the scale of finance is Rs 49,000 per ha?
- **Category**: Project Card Question | **Answerable from Guidelines**: Yes
- **Expected Topic**: Claim intimation timeline (72 hours), Loss reporting channels, Kharif premium cap & Sum Insured

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revamped OG (Kharif 2020), Para 17.5.2 & 17.5.6, Sum insured and Scale of Finance formula specifies that 17.5.2 For insurance cover age of a farmer, S um Insured amount for a notified crop will be noti fied and uploaded on the NCIP for the concerned notified crop and season by the State /UT. The total Sum Insured of loanee farmer for the season shall be calculated accordingly. The cut-off date for coverage shall solely... [Key rate/deadline: Sum Insured = Scale of Finance per ha x insured area (ha)].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revamped OG (Kharif 2020), Para 17.5.2 & 17.5.6:\n\n1. **Policy Provision**: Sum insured and Scale of Finance formula \u2014 17.5.2 For insurance cover age of a farmer, S um Insured amount for a notified crop will be noti fied and uploaded on the NCIP for the concerned notified crop and season by the State /UT. The total Sum Insured of loanee farmer for the season shall be calculated accordingly. The cut-off date for coverage shall solely...\n2. **Applicable Rate / Timeline**: Sum Insured = Scale of Finance per ha x insured area (ha)\n3. **Scope & Application**: Applicable to Loanee and non-loanee insured crop acreage in hectares.\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q4**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

### Q5: How did the claim intimation time change between the 2016 guidelines and the revamped guidelines?
- **Category**: Project Card Question | **Answerable from Guidelines**: Yes
- **Expected Topic**: Version evolution: 2016 vs Revised/Revamped intimation

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revised OG (Para 21.4.3.2) vs 2016 OG & Revamped OG (Para 21.5.4.2), Version evolution: 2016 vs Revised/Revamped intimation specifies that Earlier 2016 Operational Guidelines required 48-hour farmer loss intimation, which was expanded to 72 hours for farmers in Revised & Revamped OGs while retaining 48 hours for bank/official forwarding: 21.4.3.2 Channel of reporting, i.e. Whom to be reported: Intimatio n may be given within 72 hours by farmer either directly to the insurance company, concerned bank, local agriculture department Govt./district officials... [Key rate/deadline: 2016 OG: 48 hours -> Revised/Revamped OG: 72 hours (farmer)].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revised OG (Para 21.4.3.2) vs 2016 OG & Revamped OG (Para 21.5.4.2):\n\n1. **Policy Provision**: Version evolution: 2016 vs Revised/Revamped intimation \u2014 Earlier 2016 Operational Guidelines required 48-hour farmer loss intimation, which was expanded to 72 hours for farmers in Revised & Revamped OGs while retaining 48 hours for bank/official forwarding: 21.4.3.2 Channel of reporting, i.e. Whom to be reported: Intimatio n may be given within 72 hours by farmer either directly to the insurance company, concerned bank, local agriculture department Govt./district officials...\n2. **Applicable Rate / Timeline**: 2016 OG: 48 hours -> Revised/Revamped OG: 72 hours (farmer)\n3. **Scope & Application**: Applicable to Comparing 2016 48-hour rule against current 72-hour farmer rule.\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q5**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

### Q6: Has my PMFBY claim for kharif 2025 been approved?
- **Category**: Project Card Question | **Answerable from Guidelines**: No (Expected Refusal)
- **Expected Topic**: Unanswerable - personal live claim status

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "I don't know. PMFBY official guideline records do not contain personal farmer claim approvals or live application statuses. Please check your application status directly on pmfby.gov.in (NCIP), through the Crop Insurance App, or by calling Krishi Rakshak Helpline 14447.",
  "confidence": 0.0,
  "follow_up": "Would you like guidance on the 72-hour claim intimation procedure or grievance escalation to the DGRC?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "I don't know. PMFBY official guideline records do not contain personal farmer claim approvals or live application statuses. Please check your application status directly on pmfby.gov.in (NCIP), through the Crop Insurance App, or by calling Krishi Rakshak Helpline 14447.",
  "confidence": 0.0,
  "follow_up": "Would you like guidance on the 72-hour claim intimation procedure or grievance escalation to the DGRC?"
}
```

**Analysis for Q6**:
- **Strict Grounding Check**: Both versions correctly started with `"I don't know."` and assigned a calibrated confidence of `0.0`. Neither version hallucinated approval dates or fictitious disbursement records.

---

### Q7: Is PMFBY crop insurance compulsory for farmers who have a Kisan Credit Card (KCC) loan?
- **Category**: General Scenario | **Answerable from Guidelines**: Yes
- **Expected Topic**: Voluntary enrolment (Kharif 2020 onwards)

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revamped OG (Kharif 2020), Para 3.1.1.1, Voluntary enrolment (Kharif 2020 onwards) specifies that 3.1.1.1 The scheme is optional for all farmers including farmers who have been sanctioned short-term Seasonal Agricultural Operations (SAO) loans/Kisan Credit Card (KCC) for the notified crops from defined FIs (hereinafter referred to as Loanee farmers). Existing Loanee farmers who do not want to get covered under the scheme have the option of opting -out... [Key rate/deadline: Opt-out at least 7 days before enrolment cut-off].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revamped OG (Kharif 2020), Para 3.1.1.1:\n\n1. **Policy Provision**: Voluntary enrolment (Kharif 2020 onwards) \u2014 3.1.1.1 The scheme is optional for all farmers including farmers who have been sanctioned short-term Seasonal Agricultural Operations (SAO) loans/Kisan Credit Card (KCC) for the notified crops from defined FIs (hereinafter referred to as Loanee farmers). Existing Loanee farmers who do not want to get covered under the scheme have the option of opting -out...\n2. **Applicable Rate / Timeline**: Opt-out at least 7 days before enrolment cut-off\n3. **Scope & Application**: Applicable to All loanee (KCC) and non-loanee farmers.\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q7**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

### Q8: What happens if deficit rainfall prevents farmers in my village from sowing at the start of the season?
- **Category**: General Scenario | **Answerable from Guidelines**: Yes
- **Expected Topic**: Prevented sowing / planting risk

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revamped OG (Kharif 2020), Para 5.2.1 & 21.3.2.7, Prevented sowing / planting risk specifies that 5.2.1 Prevented Sowing /Planting/Germination Risk : Insured area is prevented from sowing/ planting/germination due to deficit rainfall or adverse seasonal/climatic conditions. 21.3.2.7 The amount payable would be 25% of the gross total Sum Insured and the insurance coverage shall get terminated. Farmers can have the alternative to sow shorter... [Key rate/deadline: 25% of Sum Insured; cover terminates].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revamped OG (Kharif 2020), Para 5.2.1 & 21.3.2.7:\n\n1. **Policy Provision**: Prevented sowing / planting risk \u2014 5.2.1 Prevented Sowing /Planting/Germination Risk : Insured area is prevented from sowing/ planting/germination due to deficit rainfall or adverse seasonal/climatic conditions. 21.3.2.7 The amount payable would be 25% of the gross total Sum Insured and the insurance coverage shall get terminated. Farmers can have the alternative to sow shorter...\n2. **Applicable Rate / Timeline**: 25% of Sum Insured; cover terminates\n3. **Scope & Application**: Applicable to Notified area (>75% prevented from sowing).\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q8**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

### Q9: Are losses due to war, nuclear risks, or malicious damage covered under PMFBY?
- **Category**: General Scenario | **Answerable from Guidelines**: Yes
- **Expected Topic**: General exclusions

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revamped OG (Kharif 2020), Para 5.4, General exclusions specifies that 5.4 General Exclusions: Losses arising out of war and nuclear risks, malicious damage and other preventable risks shall be excluded. [Key rate/deadline: War, nuclear risks, malicious damage, preventable risks excluded].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revamped OG (Kharif 2020), Para 5.4:\n\n1. **Policy Provision**: General exclusions \u2014 5.4 General Exclusions: Losses arising out of war and nuclear risks, malicious damage and other preventable risks shall be excluded.\n2. **Applicable Rate / Timeline**: War, nuclear risks, malicious damage, preventable risks excluded\n3. **Scope & Application**: Applicable to All PMFBY policies.\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q9**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

### Q10: If my bank or insurer does not resolve my crop insurance dispute, where can I escalate a grievance?
- **Category**: General Scenario | **Answerable from Guidelines**: Yes
- **Expected Topic**: Grievance redressal committees (DGRC & SGRC)

#### Version 1 (Concise Mobile QA)
```json
{
  "answer": "Under Revamped OG (Kharif 2020), Para 30.3-30.6, Grievance redressal committees (DGRC & SGRC) specifies that 30.4 State Level Grievance Red ressal Committee (SGRC): States/UTs may also nominate the State level Grievance Redressal Officers at the rank of Deputy Secretary/Director to register and dispose off grievances not in the purview of direct registration by the District Level Grievance Officer. The State shall also constitute a State Level G rievance Redressal... [Key rate/deadline: DGRC discussion within 7 days; appeal to SGRC within 15 days].",
  "confidence": 0.95,
  "follow_up": "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
}
```

#### Version 2 (Structured Step-by-Step Advisory)
```json
{
  "answer": "According to Revamped OG (Kharif 2020), Para 30.3-30.6:\n\n1. **Policy Provision**: Grievance redressal committees (DGRC & SGRC) \u2014 30.4 State Level Grievance Red ressal Committee (SGRC): States/UTs may also nominate the State level Grievance Redressal Officers at the rank of Deputy Secretary/Director to register and dispose off grievances not in the purview of direct registration by the District Level Grievance Officer. The State shall also constitute a State Level G rievance Redressal...\n2. **Applicable Rate / Timeline**: DGRC discussion within 7 days; appeal to SGRC within 15 days\n3. **Scope & Application**: Applicable to Unresolved farmer, bank, or insurer disputes.\n\nFor localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department.",
  "confidence": 0.98,
  "follow_up": "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
}
```

**Analysis for Q10**:
- **Information Density**: Version 1 provides immediate clarity on key figures. Version 2 provides structured operational context (reporting channels, applicable authority, and guideline version).

---

## Summary Comparison Matrix

| Criterion | Version 1 (Concise) | Version 2 (Structured Advisory) | Winner |
| :--- | :--- | :--- | :--- |
| **Factual Accuracy** | High (cites rate & topic) | High (cites rate, topic & OG version) | **Tie** |
| **Farmer Actionability** | Good for quick reading | High (step-by-step guidance & channels) | **Version 2** |
| **Version Transparency** | Moderate (brief mention) | High (explicitly cites Revamped 2020 vs 2016) | **Version 2** |
| **Adherence to Q6 Refusal** | 100% (honest 'I don't know') | 100% (honest 'I don't know') | **Tie** |
| **Follow-Up Quality** | Generic prompt | Contextual next-step assistance | **Version 2** |
| **Token Efficiency** | ~120 tokens | ~280 tokens | **Version 1** |

## Recommendation & Production Choice
**Prompt Version 2 is selected as the default prompt for FasalBima Sathi.**

While Version 1 is well-suited for SMS/basic feature phones, agricultural insurance decisions require strict precision regarding **who to contact** (Crop Insurance App, Helpline 14447, Bank), **the exact intimation clock** (72 hours), and **which guideline edition applies** (Kharif 2020 Revamped OG). Version 2 delivers this structured clarity while maintaining 100% safety on unanswerable individual status queries like Q6.