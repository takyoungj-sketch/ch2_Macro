"""Export aggregate-only pilot results for the lab; never include parcel identifiers."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "docs/lab"


def main():
    report = json.loads((LAB / "cheongju_regression_pilot_20261004.json").read_text(encoding="utf-8"))
    links = json.loads((LAB / "cheongju_ledger_link_pilot_20261004.json").read_text(encoding="utf-8"))
    quality = json.loads((LAB / "cheongju_ledger_link_quality_20261004.json").read_text(encoding="utf-8"))
    fields = ("policy", "test_year", "model", "n_train", "n_test", "train_adj_r2", "test_log_rmse",
              "test_actual_mean_10k_sqm", "test_predicted_mean_10k_sqm", "mean_ci95_approx",
              "cell_mean_mae_n20_10k_sqm", "cells_n20")
    output = {key: report[key] for key in ("run_date", "sample", "conflicting_pnu_excluded", "positive_filter_excluded")}
    output.update(transaction_rows=links["transaction_rows"], source_join=links["source_join"],
                  counts=links["counts"], annual_unique=quality["annual_unique"], prior_unique=quality["prior_unique"],
                  results=[{key: row[key] for key in fields} for row in report["results"]])
    for row in output["results"]:
        if row["policy"] == "observed_before_trade":
            row["policy"] = "prior"
    assert len(output["results"]) == 20
    for policy in ("annual", "prior"):
        for year in (2025, 2026):
            rows = [r for r in output["results"] if r["policy"] == policy and r["test_year"] == year]
            assert len(rows) == 5 and len({(r["n_train"], r["n_test"]) for r in rows}) == 1
    (LAB / "cheongju_ledger_lab_summary.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
