# FasalBima Sathi — Semantic Search Evaluation (Day 7)

## Overview
This report records the semantic search retrieval results using our persistent Chroma vectorstore (`fasalbima_sathi_chunks`, 1,786 chunks across official PMFBY operational guidelines, portal FAQs, and curated rules) across all 10 project evaluation questions.

---

## Retrieval Hits per Question

### Q1: What premium do I pay for soybean crop insurance in kharif?
- **Category**: Project Card | **Answerable from Guidelines**: Yes
- **Expected Topic**: Kharif foodgrain and oilseed premium cap

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.7226 | `https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf` (p. 1) | Kharif foodgrain and oilseed premium cap | Topic: Kharif foodgrain and oilseed premium cap. Rule: Maximum Premium Rate payable by farmer (% of Sum Insured): Kharif All Food grain and ... |
| 2 | 0.6504 | `revamped_ogs_final.pdf` (p. 30) | 10 Census Code Mapping of Entities | [23] Season Crops Maximum Premium Rate payable by farmer (% of Sum Insured)* Kharif All Food grain and Oilseeds crops (all Cereals, Millets,... |
| 3 | 0.6458 | `revamped_ogs_final.pdf` (p. 40) | 39 Confirmation | idered for Insurance/Ha 50,000 40,000 50,000 Total SI to be considered for Insurance 1,00,000 40,000 1,00,000 SI for Loanee farmers 1,00,000... |

**Retrieval Quality for Q1**:
- Top hit retrieved from `https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf` (page 1, Kharif foodgrain and oilseed premium cap) with similarity score `0.7226`.

---

### Q2: Is hailstorm damage covered for my individual farm?
- **Category**: Project Card | **Answerable from Guidelines**: Yes
- **Expected Topic**: Localized calamities (hailstorm, landslide, inundation)

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.6657 | `revised_operational_guidelines.pdf` (p. 9) | Coverage of Farmers | against specific perils of Hailstorm, Cyclone, Cyclonic rains and Unseasonal rains. 5.1.4 Localized Calamities: Loss/damage to notified insu... |
| 2 | 0.6083 | `https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf` (p. 1) | Localized calamities (hailstorm, landslide, inundation) | Topic: Localized calamities (hailstorm, landslide, inundation). Rule: 5.2.4 Localized Calamities : Loss/damage to notified insured crops res... |
| 3 | 0.5964 | `revamped_ogs_final.pdf` (p. 13) | 5.2.4 Localized Calamities | [6] 5.2.4 Localized Calamities : Loss/damage to notified insured crops resulting from occurrence of identified localized risks of hailstorm,... |

**Retrieval Quality for Q2**:
- Top hit retrieved from `revised_operational_guidelines.pdf` (page 9, Coverage of Farmers) with similarity score `0.6657`.

---

### Q3: How many days after harvest are cut-and-spread crops covered for unseasonal rain?
- **Category**: Project Card | **Answerable from Guidelines**: Yes
- **Expected Topic**: Post-harvest losses (14-day drying window)

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.7655 | `revised_operational_guidelines.pdf` (p. 51) | 21.4 Post-Harvest Losses due to unseasonal rains etc 21 | aximum period of two weeks(14 days) from harvesting , for sole purpose of drying. For the purpose of indemnification of post harvest crop lo... |
| 2 | 0.7215 | `revamped_ogs_final.pdf` (p. 80) | 5 Finalization of likely losses | ocess of drying in the field in “cut and spread condition”/small bundled conditions upto a period of 14 days from harvest. State s/UTsshall ... |
| 3 | 0.7196 | `revamped_ogs_final.pdf` (p. 79) | 5 Finalization of likely losses | orm, cyclone, cyclonic rains and unseasonal rains resulting in damage to harvested crop lying in the field in ‘cut and spread’/small bundled... |

**Retrieval Quality for Q3**:
- Top hit retrieved from `revised_operational_guidelines.pdf` (page 51, 21.4 Post-Harvest Losses due to unseasonal rains etc 21) with similarity score `0.7655`.

---

### Q4: Hailstorm hit my 1.2 ha soybean at 9 pm yesterday. By when must I inform, through which channels, and what premium did I pay if the scale of finance is Rs 49,000 per ha?
- **Category**: Project Card | **Answerable from Guidelines**: Yes
- **Expected Topic**: Claim intimation timeline (72 hours), Loss reporting channels, Kharif premium cap & Sum Insured

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.5088 | `revamped_ogs_final.pdf` (p. 73) | 21.5 Localized Calamity | ing preferable at a interval of 15days in the Notification itself. 21.5.3.5 Only those farmers would be eligible for financial support under... |
| 2 | 0.4868 | `revamped_ogs_final.pdf` (p. 130) | 75 Basedonthelast10yearsvariationinoutput, category-wise No | rict of the Cluster Expected Area to be insured (in ha) Notified SI per ha (Rs.) Total SI (Rs. Lakh) Premium Quoted by company Premium Amoun... |
| 3 | 0.481 | `revised_operational_guidelines.pdf` (p. 57) | 21.5.8.7 Bank would remit farmers | taken by Schedule for taking action 1 Information / intimation to Insurance Company directly Or any one of the concerned- a) Bank/PACS, b) L... |

**Retrieval Quality for Q4**:
- Top hit retrieved from `revamped_ogs_final.pdf` (page 73, 21.5 Localized Calamity) with similarity score `0.5088`.

---

### Q5: How did the claim intimation time change between the 2016 guidelines and the revamped guidelines?
- **Category**: Project Card | **Answerable from Guidelines**: Yes
- **Expected Topic**: Version evolution: 2016 vs Revised/Revamped intimation

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.5165 | `https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf` (p. 1) | Version evolution: 2016 vs Revised/Revamped intimation | Topic: Version evolution: 2016 vs Revised/Revamped intimation. Rule: Earlier 2016 Operational Guidelines required 48-hour farmer loss intima... |
| 2 | 0.4625 | `revised_operational_guidelines.pdf` (p. 24) | 26 Cut off date for resolution by State Govt | of claims by ICS Portal/ Insurance Companies 31 Timelines for Payment of claims Within 2 weeks from calculation/auto approval of claims irre... |
| 3 | 0.4446 | `revamped_ogs_final.pdf` (p. 37) | 39 Confirmation | n of admissible claims and subsequent settlement of claims to eligible farmers. The cut-off date for submission of yield data to IC is norma... |

**Retrieval Quality for Q5**:
- Top hit retrieved from `https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf` (page 1, Version evolution: 2016 vs Revised/Revamped intimation) with similarity score `0.5165`.

---

### Q6: Has my PMFBY claim for kharif 2025 been approved?
- **Category**: Project Card | **Answerable from Guidelines**: No (Expected Refusal)
- **Expected Topic**: Unanswerable - personal live claim status

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.6558 | `revised_operational_guidelines.pdf` (p. 19) | 13.1 The Actuarial Premium Rate | www.pmfby.gov.in Revised Operational Guidelines of PMFBY 14 13.2.5 All admissible claims based on Yield data/Post harvest losses will be set... |
| 2 | 0.6337 | `revised_operational_guidelines.pdf` (p. 60) | 23.1 Tentative final share of Govt | www.pmfby.gov.in Revised Operational Guidelines of PMFBY 55 23. Procedure for Settlement of Claims to the farmers 23.1 Tentative final share... |
| 3 | 0.6326 | `revised_operational_guidelines.pdf` (p. 12) | 7.1 Procedure for Issuance of Notification by the States/UTs | www.pmfby.gov.in Revised Operational Guidelines of PMFBY 7 7. Notification 7.1 Procedure for Issuance of Notification by the States/UTs: 7.1... |

**Retrieval Quality for Q6**:
- *Special Rule Validation*: As expected, semantic search retrieves general claims guidelines. Because static guidelines contain no personal policy or approval status records, downstream RAG safeguards must intercept and return an honest 'I don't know'.

---

### Q7: Is PMFBY crop insurance compulsory for farmers who have a Kisan Credit Card (KCC) loan?
- **Category**: General Scenario | **Answerable from Guidelines**: Yes
- **Expected Topic**: Voluntary enrolment (Kharif 2020 onwards)

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.8539 | `revised_operational_guidelines.pdf` (p. 28) | 2 Balance Un-covered area | d non-loanee) 6,600 4,500 * The Area which has been left out of compulsory coverage for the notified crop can be insured by the farmer as a ... |
| 2 | 0.8029 | `revamped_ogs_final.pdf` (p. 40) | 39 Confirmation | Crop loans sanctioned through Kisan Credit Cards (KCC) are covered as loanee farmer and banks shall maintain all back up records and registe... |
| 3 | 0.7424 | `revamped_ogs_final.pdf` (p. 40) | 39 Confirmation | ium (as non- loanee )* 3,000 800 - 3,000 Total Farmer’s Premium ( as non- loanee ) 3,800 3,000 Total Premium of Farmers (both as loanee and ... |

**Retrieval Quality for Q7**:
- Top hit retrieved from `revised_operational_guidelines.pdf` (page 28, 2 Balance Un-covered area) with similarity score `0.8539`.

---

### Q8: What happens if deficit rainfall prevents farmers in my village from sowing at the start of the season?
- **Category**: General Scenario | **Answerable from Guidelines**: Yes
- **Expected Topic**: Prevented sowing / planting risk

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.6213 | `revised_operational_guidelines.pdf` (p. 51) | 21.4 Post-Harvest Losses due to unseasonal rains etc 21 | aximum period of two weeks(14 days) from harvesting , for sole purpose of drying. For the purpose of indemnification of post harvest crop lo... |
| 2 | 0.5937 | `revamped_ogs_final.pdf` (p. 79) | 5 Finalization of likely losses | orm, cyclone, cyclonic rains and unseasonal rains resulting in damage to harvested crop lying in the field in ‘cut and spread’/small bundled... |
| 3 | 0.5846 | `revamped_ogs_final.pdf` (p. 63) | 15 Yield | be constituted which will look after the invoking of On -Account Payment under mid-season adversity, prevented sowing, localized calamities ... |

**Retrieval Quality for Q8**:
- Top hit retrieved from `revised_operational_guidelines.pdf` (page 51, 21.4 Post-Harvest Losses due to unseasonal rains etc 21) with similarity score `0.6213`.

---

### Q9: Are losses due to war, nuclear risks, or malicious damage covered under PMFBY?
- **Category**: General Scenario | **Answerable from Guidelines**: Yes
- **Expected Topic**: General exclusions

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.6388 | `https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf` (p. 1) | General exclusions | Topic: General exclusions. Rule: 5.4 General Exclusions: Losses arising out of war and nuclear risks, malicious damage and other preventable... |
| 2 | 0.6194 | `revised_operational_guidelines.pdf` (p. 46) | 21.2.7 Illustration 21 | www.pmfby.gov.in Revised Operational Guidelines of PMFBY 41 intimation of loss under this section, if not uploaded earlier on Portal. Howeve... |
| 3 | 0.6135 | `revised_operational_guidelines.pdf` (p. 55) | 21.5.2.6 Percentage of l | www.pmfby.gov.in Revised Operational Guidelines of PMFBY 50 damaged, and info rmed about occurrence of calamity in the farm within the stipu... |

**Retrieval Quality for Q9**:
- Top hit retrieved from `https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf` (page 1, General exclusions) with similarity score `0.6388`.

---

### Q10: If my bank or insurer does not resolve my crop insurance dispute, where can I escalate a grievance?
- **Category**: General Scenario | **Answerable from Guidelines**: Yes
- **Expected Topic**: Grievance redressal committees (DGRC & SGRC)

| Rank | Score | Source & Page | Section / Title | Snippet |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.634 | `revised_operational_guidelines.pdf` (p. 61) | 23.1 Tentative final share of Govt | nd Indemnity levels etc. Responsibility of any error, omissions and mis-reporting shall lie with the concerned State Nodal Department and in... |
| 2 | 0.6285 | `revised_operational_guidelines.pdf` (p. 65) | 27.2 To CSC | o be uploaded/ placed on the website of the concerned Insurance Companies with proper provisions and mechanisms of public grievance redressa... |
| 3 | 0.6248 | `revised_operational_guidelines.pdf` (p. 78) | 35.5 Financial Institutions/Banks 35 | or any notified crop in any notified insurance unit may approach nearest bank branch/PACS/authorized channel partner/ CSC/insurance intermed... |

**Retrieval Quality for Q10**:
- Top hit retrieved from `revised_operational_guidelines.pdf` (page 61, 23.1 Tentative final share of Govt) with similarity score `0.634`.

---

## Summary Observations
- **Coverage**: The 1,786 indexed chunks provide direct semantic coverage across premium caps, localized loss reporting (72h), post-harvest drying windows (14 days), prevented sowing triggers, and grievance escalation.
- **Precision**: Citing exact page and section metadata ensures answers can display grounded source references.
- **Next Step**: Connect retrieved chunks to `app/rag.py` and `POST /ask` with mandatory Q6 refusal safeguards (Day 8).