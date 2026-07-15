from __future__ import annotations


PREREGISTRATION_OUTPUTS = {
    "queue": "reports/candidate_validation_queue.json",
    "deduplication": "reports/candidate_deduplication_report.json",
    "preregistrationJson": "reports/candidate_locked_validation_preregistration.json",
    "preregistrationMarkdown": "reports/candidate_locked_validation_preregistration.md",
}

VALIDATION_OUTPUTS = {
    "dataManifest": "reports/candidate_validation_data_manifest.json",
    "costModels": "reports/candidate_validation_cost_models.json",
    "riskModels": "reports/candidate_validation_risk_models.json",
    "signalLayer": "reports/candidate_signal_layer_report.json",
    "lockedSample": "reports/candidate_locked_sample_report.json",
    "walkForward": "reports/candidate_walk_forward_report.json",
    "costStress": "reports/candidate_cost_stress_report.json",
    "riskModel": "reports/candidate_risk_model_report.json",
    "monteCarlo": "reports/candidate_monte_carlo_report.json",
    "portfolioRisk": "reports/candidate_portfolio_risk_report.json",
    "closure": "reports/candidate_evidence_closure_report.json",
    "summary": "reports/candidate_evidence_closure_summary.md",
    "leaderboard": "reports/candidate_evidence_closure_leaderboard.csv",
    "continueArchive": "reports/candidate_continue_archive.json",
    "recommendations": "reports/candidate_new_version_recommendations.json",
}
