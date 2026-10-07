# Product Requirements

## Problem
India's lower courts have a very large backlog. Litigants, lawyers and policymakers have little
data-driven sense of *how long* a given kind of case will take in a given place, or which
structural factors drive delay.

## Goal
Estimate the **distribution of case duration** (filing → decision) for Maharashtra district-court
cases, accounting correctly for cases still pending at data collection (censoring), and explain
which factors speed cases up or slow them down.

## Users
- Portfolio reviewers / interviewers (primary): show sound data handling, statistics, modelling, shipping.
- Curious public / legal-policy readers: an interactive "how long will this take?" tool.

## Core deliverables
1. **Clean survival table** for one state: one row per case with duration, event flag, features.
2. **EDA insights**: slowest districts, civil vs criminal, slowest acts, trends 2010–2018.
3. **Survival analysis**: Kaplan-Meier curves by segment; Cox PH model with interpretable hazard ratios.
4. **Prediction models**: baseline (median per case type) vs Cox vs gradient-boosted survival model,
   compared on concordance index (and integrated Brier score).
5. **Explainability**: SHAP for the best model.
6. **Demo app**: pick district + case type (+ act) and see P(still pending after 1/2/5 years) curve,
   plus an insights page.
7. **README write-up** explaining censoring and results.

## Success criteria
- Pipeline reproduces the processed table from raw files with one command.
- Best model beats the baseline on held-out C-index (time-based split: train on earlier filings).
- A reader can understand censoring from the README in under 2 minutes.

## Out of scope
- Predicting case *outcomes* (who wins), or scoring individual judges/litigants.
- All 81M cases / all states (possible later extension).
- Free-text judgments/NLP.

## Responsible framing
Gender fields exist in the data. They may be used in EDA to study disparities in *system delay*,
but the demo app does not take party gender as input.
