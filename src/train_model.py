"""
Phase 3: ML-powered stopping-rule model.

Trains a small classifier to predict recovery probability for a failed
transaction, based on synthetic historical patterns. This replaces a
fixed "retry 3 times then stop" rule with a case-specific decision.

Note: root cause and action selection remain rule-based (see
rules_engine.py) — only the STOPPING decision uses ML, since that's a
genuine pattern-learning problem rather than a fixed business policy.
"""

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import precision_score, recall_score, accuracy_score, confusion_matrix

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.rules_engine import get_root_cause


def load_and_prepare_data(csv_path="data/failed_transactions.csv"):
    df = pd.read_csv(csv_path)

    # add root_cause using our rule-based engine, since the model
    # should learn on root cause, not raw failure code
    df["root_cause"] = df["failure_code"].apply(get_root_cause)

    return df


def build_pipeline():
    """Builds a preprocessing + model pipeline. One-hot encodes the
    categorical columns, leaves numeric columns as-is, then feeds
    into Logistic Regression."""
    categorical_features = ["payment_method", "root_cause"]
    numeric_features = ["amount", "attempt_number"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ],
        remainder="passthrough",  # keeps numeric_features as-is
    )

    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(max_iter=1000)),
    ])

    return pipeline, categorical_features + numeric_features


def train_and_evaluate():
    df = load_and_prepare_data()

    feature_cols = ["payment_method", "root_cause", "amount", "attempt_number"]
    X = df[feature_cols]
    y = df["recovered"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline, _ = build_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)

    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    accuracy = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)

    print("Model evaluation on held-out test set:\n")
    print(f"  Accuracy:  {accuracy:.2%}")
    print(f"  Precision: {precision:.2%}  (of predicted-recoverable, how many actually recovered)")
    print(f"  Recall:    {recall:.2%}  (of actually-recoverable, how many we caught)")
    print(f"\n  Confusion matrix:")
    print(f"    {cm}")

    # save the trained pipeline (includes preprocessing + model)
    os.makedirs("models", exist_ok=True)
    joblib.dump(pipeline, "models/stopping_model.pkl")
    print("\nModel saved to models/stopping_model.pkl")

    return pipeline, {"accuracy": accuracy, "precision": precision, "recall": recall}


def predict_recovery_probability(pipeline, payment_method, root_cause, amount, attempt_number):
    """Given a single transaction's details, predict the probability
    that retrying will succeed. Used later in the batch runner (Phase 5)
    to decide stop vs continue."""
    input_df = pd.DataFrame([{
        "payment_method": payment_method,
        "root_cause": root_cause,
        "amount": amount,
        "attempt_number": attempt_number,
    }])
    probability = pipeline.predict_proba(input_df)[0][1]  # probability of class "1" (recovered)
    return probability


if __name__ == "__main__":
    pipeline, metrics = train_and_evaluate()

    # quick sanity test — predict on a couple of made-up examples
    print("\n--- Sample predictions ---")
    prob1 = predict_recovery_probability(pipeline, "UPI", "bank_server_delay", 1500, 1)
    print(f"UPI, bank_server_delay, ₹1500, attempt 1  -> recovery probability: {prob1:.1%}")

    prob2 = predict_recovery_probability(pipeline, "Credit Card", "card_issue", 8000, 3)
    print(f"Credit Card, card_issue, ₹8000, attempt 3  -> recovery probability: {prob2:.1%}")