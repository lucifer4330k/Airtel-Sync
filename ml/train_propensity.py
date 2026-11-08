"""Train the lead propensity model (P(outcome == Activated)).

Run from apps/api (uses its venv and the rules engine):
    uv sync --extra ml
    uv run python ../../ml/train_propensity.py

Features use only what is known when the lead arrives. Stage dates, drop
reason, bundle, value, churn, NPS, follow-up calls and acquisition cost are
excluded: they are recorded after the fact and would leak the answer.

Writes:
  apps/api/app/services/propensity_model.json   served by the API (no sklearn at runtime)
  ml/report.json                                ROC-AUC of both models + top coefficients
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.catalogue import SEGMENT_CODES, get_catalogue  # noqa: E402
from app.services.eligibility import BusinessProfile, eligible  # noqa: E402
from app.services.registry import gstin_is_active  # noqa: E402

CATEGORICAL = [
    "segment",
    "business_type",
    "lead_source",
    "city_tier",
    "preferred_language",
    "annual_turnover_band",
    "current_internet",
]
NUMERIC = [
    "log_employees",
    "log_sites",
    "log_spend",
    "n_products",
    "has_gstin",
    "has_udyam",
    "any_ineligible",
]
LEAKY = [
    "stage_reached",
    "drop_reason",
    "contacted_date",
    "needs_assessed_date",
    "quote_accepted_date",
    "kyc_complete_date",
    "activated_date",
    "days_lead_to_activation",
    "customer_follow_up_calls",
    "bundle_products",
    "monthly_bundle_value_inr",
    "one_time_setup_inr",
    "contract_months",
    "churned_within_6_months",
    "nps_score",
    "acquisition_cost_inr",
]


def features(df: pd.DataFrame) -> pd.DataFrame:
    catalogue = get_catalogue()
    out = pd.DataFrame(index=df.index)
    for c in CATEGORICAL:
        out[c] = df[c].astype(str)
    out["log_employees"] = np.log1p(df["employee_count"].astype(float))
    out["log_sites"] = np.log1p(df["num_sites"].astype(float))
    out["log_spend"] = np.log1p(df["monthly_telecom_spend_inr"].fillna(0).astype(float))
    asked = df["products_of_interest"].fillna("").str.split(";")
    out["n_products"] = asked.map(lambda xs: len([x for x in xs if x]))
    out["has_gstin"] = (df["has_gstin"] == "Y").astype(int)
    out["has_udyam"] = (df["has_udyam"] == "Y").astype(int)

    def ineligible(row) -> int:
        biz = BusinessProfile(
            segment=SEGMENT_CODES[row["segment"]],
            city_tier=int(row["city_tier"]),
            employees=int(row["employee_count"]),
            sites=int(row["num_sites"]),
            gstin_active=gstin_is_active(row["gstin"] or None),
        )
        return int(
            any(not eligible(catalogue[p], biz).ok for p in row["products_of_interest"].split(";") if p)
        )

    out["any_ineligible"] = df.fillna("").apply(ineligible, axis=1)
    return out


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "smb_leads.csv", dtype=str, keep_default_na=False)
    for c in ("employee_count", "num_sites", "monthly_telecom_spend_inr"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    y = (df["outcome"] == "Activated").astype(int).to_numpy()
    X = features(df.drop(columns=LEAKY))

    X_oh = pd.get_dummies(X, columns=CATEGORICAL, dtype=float)
    Xtr, Xte, ytr, yte = train_test_split(X_oh, y, test_size=0.25, random_state=42, stratify=y)
    mean, std = Xtr[NUMERIC].mean(), Xtr[NUMERIC].std().replace(0, 1)
    scale = lambda d: d.assign(**{c: (d[c] - mean[c]) / std[c] for c in NUMERIC})  # noqa: E731

    lr = LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced")
    lr.fit(scale(Xtr), ytr)
    auc_lr = roc_auc_score(yte, lr.predict_proba(scale(Xte))[:, 1])

    import lightgbm as lgb

    Xc = X.copy()
    for c in CATEGORICAL:
        Xc[c] = Xc[c].astype("category")
    Xtr_c, Xte_c = Xc.loc[Xtr.index], Xc.loc[Xte.index]
    gbm = lgb.LGBMClassifier(
        n_estimators=300,
        learning_rate=0.03,
        num_leaves=15,
        min_child_samples=40,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        verbose=-1,
        random_state=42,
    )
    gbm.fit(Xtr_c, ytr)
    auc_gbm = roc_auc_score(yte, gbm.predict_proba(Xte_c)[:, 1])

    # Serve the logistic model: within reach of LightGBM here, exact additive
    # reasons (coef x scaled value is its SHAP value), and no sklearn at runtime.
    coefs = dict(zip(X_oh.columns, lr.coef_[0], strict=True))
    model = {
        "type": "logistic",
        "intercept": float(lr.intercept_[0]),
        "numeric": {
            c: {"mean": float(mean[c]), "std": float(std[c]), "coef": float(coefs[c])} for c in NUMERIC
        },
        "categorical": {
            c: {k.split(f"{c}_", 1)[1]: float(v) for k, v in coefs.items() if k.startswith(f"{c}_")}
            for c in CATEGORICAL
        },
        # expected value of each one-hot column in training data (baseline for reasons)
        "baseline": {k: float(Xtr[k].mean()) for k in X_oh.columns if k not in NUMERIC},
        "auc": {"logistic": round(auc_lr, 4), "lightgbm": round(auc_gbm, 4)},
        "base_rate": float(y.mean()),
    }
    out = ROOT / "apps" / "api" / "app" / "services" / "propensity_model.json"
    out.write_text(json.dumps(model, indent=1))
    top = sorted(coefs.items(), key=lambda kv: -abs(kv[1]))[:15]
    report = {
        "rows": int(len(df)),
        "activated_rate": round(float(y.mean()), 4),
        "test_rows": int(len(yte)),
        "roc_auc": model["auc"],
        "served": "logistic",
        "top_coefficients": {k: round(float(v), 3) for k, v in top},
        "excluded_as_leaky": LEAKY,
    }
    (ROOT / "ml" / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report["roc_auc"]), "->", out)


if __name__ == "__main__":
    main()
