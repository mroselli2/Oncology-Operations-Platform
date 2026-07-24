"""Markdown executive report, capped for readability at cohort scale."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from .excel_report import build_cohort_summary

TOP_N_DETAILED = 25


def generate_markdown_report(
    analysis_df: pd.DataFrame, today: datetime, scenario_name: str,
    analysis_file_name: str, llm_summary: dict | None = None,
) -> str:
    high = analysis_df[analysis_df["risk_level"] == "High"].sort_values("risk_score", ascending=False)
    moderate = analysis_df[analysis_df["risk_level"] == "Moderate"]
    delayed = analysis_df[analysis_df["scheduling_status"] == "Delayed"]

    lines = [
        "# Oncology Pipeline -- Operational Analysis Report",
        "",
        f"**Generated:** {today.strftime('%Y-%m-%d')}  ",
        f"**Scenario:** {scenario_name}  ",
        f"**Records analyzed:** {len(analysis_df)} synthetic patients  ",
        f"**High-risk patients:** {len(high)}  ",
        f"**Moderate-risk patients:** {len(moderate)}  ",
        f"**Currently delayed:** {len(delayed)}  ",
        "",
        "---",
        "",
        "## Executive Snapshot",
        "",
        "This report is generated entirely from **100% synthetic data** (ONC-* identifiers; no real "
        "PHI, MRNs, NPIs, or member IDs anywhere) across a consolidated deterministic oncology "
        "scheduling/authorization/network platform. All risk scores, milestone checks, bottleneck "
        "classifications, network determinations, and slot recommendations below are calculated "
        "deterministically in Python before any optional LLM narrative layer runs.",
        "",
        "### Key Findings",
        f"- {len(high)} patients scored **High** risk.",
        "- Most common primary bottlenecks observed in this cohort:",
    ]

    for b, c in analysis_df["primary_bottleneck"].value_counts().head(8).items():
        lines.append(f"  - {b}: {c} patients")

    lines += ["", "### Cohort Composition"]
    for label, col in [("Treatment pathway", "treatment_modality_pathway"), ("Stage", "stage"), ("Payer type", "payer_type")]:
        lines.append(f"- **{label}:** " + ", ".join(f"{k} ({v})" for k, v in analysis_df[col].value_counts().items()))

    lines += ["", "---", "", f"## High-Risk Patients (Action List, top {min(TOP_N_DETAILED, len(high))} by risk score)", ""]

    if high.empty:
        lines.append("_No high-risk patients in this run._")
    else:
        for _, r in high.head(TOP_N_DETAILED).iterrows():
            lines += [
                f"### {r['mrn']} — {r['first_name']} {r['last_name']}",
                f"- **Diagnosis / Stage / Pathway:** {r['diagnosis_type']} / {r['stage']} / {r['treatment_modality_pathway']}  ",
                f"- **Priority / Risk:** {r['priority_level']} / **{r['risk_level']}** (score {r['risk_score']})  ",
                f"- **Payer / Facility / Coordinator:** {r['payer_type']} / {r['facility_name']} / {r['assigned_coordinator_name']}  ",
                f"- **Projected days (referral → definitive treatment):** ~{r['projected_total_days']}  ",
                f"- **Primary bottleneck:** {r['primary_bottleneck']}  ",
                f"- **Missing / flags:** {r['missing_items']}  ",
                f"- **Recommended action:** {r['recommended_action']}  ",
                "",
                "<details><summary>Internal draft note (copy-paste ready)</summary>",
                "",
                "```",
                r["internal_draft_note"],
                "```",
                "</details>",
                "",
            ]
        if len(high) > TOP_N_DETAILED:
            lines.append(f"_{len(high) - TOP_N_DETAILED} additional high-risk patients omitted for brevity — see `{analysis_file_name}`._")
            lines.append("")

    lines += ["---", "", "## Cohort Summary (Aggregate)", "", "| Dimension | Value | Patients | Avg Risk | Delayed | High Risk |", "|---|---|---|---|---|---|"]
    for _, r in build_cohort_summary(analysis_df).iterrows():
        lines.append(f"| {r['dimension']} | {r['value']} | {r['patient_count']} | {r['avg_risk_score']} | {r['delayed_count']} | {r['high_risk_count']} |")

    lines += ["", "---", "", "## LLM Usage Summary", ""]
    if llm_summary:
        lines += [
            f"- API calls: {llm_summary.get('api_calls', 0)}",
            f"- Cache hits: {llm_summary.get('cache_hits', 0)}",
            f"- Deterministic fallbacks: {llm_summary.get('fallbacks', 0)}",
            f"- Total reported cost: ${llm_summary.get('total_cost', 0.0):.4f}",
        ]
    else:
        lines.append("_LLM layer not invoked this run (deterministic templates only)._")

    lines += [
        "",
        "---",
        "",
        "## How the Platform Works",
        "",
        "1. **Deterministic intelligence layer** — synthetic data generation, pathway/milestone "
        "checks, interval calculations, risk scoring, bottleneck detection, network/authorization "
        "checks, and slot matching. All computed in Python before any LLM call.",
        "2. **LLM-assisted communication layer (optional, bounded)** — OpenRouter provides a "
        "schema-constrained language layer for selected high-priority cases and cohort summaries "
        "only. It never computes scores, alters pathways, or takes action.",
        "",
        "All data in this report is fully synthetic; no real patient, provider, payer, or facility "
        "information is used or represented.",
        "",
    ]
    return "\n".join(lines)
