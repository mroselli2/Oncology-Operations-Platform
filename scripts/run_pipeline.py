#!/usr/bin/env python3
"""CLI entrypoint for the consolidated oncology pipeline.

Deterministic generation -> SQLite -> agents -> slot matching -> optional
bounded OpenRouter narrative layer (--llm-mode auto|on|off) -> reports.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from oncology_pipeline.agents.orchestrator import run_full_analysis
from oncology_pipeline.config import Settings, has_openrouter_key
from oncology_pipeline.db.loader import build_database
from oncology_pipeline.db.queries import connect
from oncology_pipeline.generation.cohort import build_cohort
from oncology_pipeline.reports.excel_report import save_analysis_excel
from oncology_pipeline.reports.markdown_report import generate_markdown_report
from oncology_pipeline.reports.operational_reports import write_operational_reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the consolidated oncology pipeline.")
    parser.add_argument("--llm-mode", choices=["auto", "on", "off"], default=None)
    parser.add_argument("--scenario", default=None, help="Scenario preset name (default: baseline)")
    parser.add_argument("--llm-max-cases", type=int, default=None)
    parser.add_argument("--llm-budget-usd", type=float, default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--refresh-llm-cache", action="store_true", default=None)
    parser.add_argument("--cohort-size", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env().apply_cli_overrides(
        llm_mode=args.llm_mode,
        scenario_name=args.scenario,
        llm_max_cases=args.llm_max_cases,
        llm_run_budget_usd=args.llm_budget_usd,
        openrouter_model=args.llm_model,
        refresh_llm_cache=args.refresh_llm_cache,
        cohort_size=args.cohort_size,
        run_id=args.run_id,
    )

    print("=" * 70)
    print("Oncology Pipeline")
    print("=" * 70)
    print(f"Scenario: {settings.scenario_name} | LLM mode: {settings.llm_mode} | Cohort size: {settings.cohort_size}")

    if settings.llm_mode in ("auto", "on"):
        if has_openrouter_key():
            print(f"Note: OPENROUTER_API_KEY is present. Will attempt up to {settings.llm_max_cases} case "
                  f"narratives + 1 cohort synthesis via {settings.openrouter_model}, budget ${settings.llm_run_budget_usd:.2f}.")
        else:
            print("Note: OPENROUTER_API_KEY is not set -- all narratives will use deterministic templates.")

    print("\n[1] Generating synthetic cohort...")
    data = build_cohort(
        scenario_name=settings.scenario_name, cohort_size=settings.cohort_size,
        random_seed=settings.random_seed, run_id=settings.run_id,
    )
    for table, rows in data.items():
        print(f"    {table}: {len(rows)} rows")

    print("\n[2] Loading into SQLite...")
    build_database(data, settings.db_path)
    print(f"    -> {settings.db_path}")

    print("\n[3] Running deterministic agents + slot matching...")
    conn = connect(settings.db_path)
    from datetime import datetime
    today = datetime(2026, 7, 23)
    analysis_df = run_full_analysis(conn, today, settings.run_id)
    print(f"    {len(analysis_df)} patients analyzed")

    llm_summary = None
    if settings.llm_mode != "off":
        print("\n[3b] Running bounded LLM narrative layer...")
        from oncology_pipeline.agents.llm_layer import run_llm_layer
        from oncology_pipeline.llm.ledger import summarize as summarize_ledger

        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        llm_result = run_llm_layer(conn, analysis_df, settings, settings.run_id)
        if llm_result["attempted"]:
            print(f"    cases attempted: {llm_result['cases_attempted']} | succeeded: {llm_result['cases_succeeded']}")
            print(f"    cohort synthesis: {llm_result['cohort_synthesis_status']}")
            print(f"    budget spent: ${llm_result['budget_spent_usd']:.4f} | calls made: {llm_result['calls_made']}")
        ledger_path = settings.outputs_dir / "llm_usage_ledger.csv"
        llm_summary = summarize_ledger(ledger_path, settings.run_id)

    print("\n[4] Writing reports...")
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    analysis_file = settings.outputs_dir / "oncology_pipeline_analysis.xlsx"
    report_file = settings.outputs_dir / "oncology_pipeline_report.md"

    # Reflect any LLM upgrades from agent_outputs in the report data.
    import pandas as pd
    updated_cols = pd.read_sql_query(
        "SELECT patient_id, internal_draft_note, recommended_action, narrative_source FROM agent_outputs WHERE run_id = ?",
        conn, params=(settings.run_id,),
    )
    analysis_df = analysis_df.drop(columns=["internal_draft_note", "recommended_action", "narrative_source"]).merge(
        updated_cols, on="patient_id", how="left",
    )

    save_analysis_excel(conn, analysis_df, analysis_file)
    print(f"    -> {analysis_file}")

    md = generate_markdown_report(analysis_df, today, settings.scenario_name, analysis_file.name, llm_summary)
    report_file.write_text(md, encoding="utf-8")
    print(f"    -> {report_file}")

    write_operational_reports(conn, analysis_df, settings.outputs_dir)
    print(f"    -> operational reports in {settings.outputs_dir}")

    import pandas as pd
    slot_df = pd.read_sql_query("SELECT * FROM slot_recommendations", conn)
    slot_df.to_csv(settings.outputs_dir / "slot_recommendations.csv", index=False)
    print(f"    -> {settings.outputs_dir / 'slot_recommendations.csv'} ({len(slot_df)} rows)")

    conn.close()

    print("\n" + "-" * 70)
    print("Risk level counts:")
    print(analysis_df["risk_level"].value_counts().to_string())
    print("\nDone.")
    print("=" * 70)


if __name__ == "__main__":
    main()
