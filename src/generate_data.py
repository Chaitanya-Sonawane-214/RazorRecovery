"""
Phase 1 (Extended): Generate synthetic failed-payment transactions
across all 4 recovery directions.

Original: payment_failure only (600 transactions, 5 failure codes).
Extended: + checkout_abandonment, subscription_lapsed, b2b_receivable
          → 1000 transactions total, 16 failure codes.

Direction split (realistic production distribution):
  60% payment_failure  → core Razorpay use case
  20% checkout_abandonment → high-volume e-commerce problem
  10% subscription_lapsed  → recurring revenue problem
  10% b2b_receivable       → enterprise collections

Ground-truth 'recovered' label still used only for ML training.
"""

import pandas as pd
import random
from faker import Faker
from datetime import datetime, timedelta

from src.rules_engine import (
    FAILURE_CODE_TO_DIRECTION,
    DIRECTION_PAYMENT,
    DIRECTION_CHECKOUT,
    DIRECTION_SUBSCRIPTION,
    DIRECTION_B2B,
)

fake = Faker("en_IN")
random.seed(42)  # reproducible

# --- Payment failure codes (original) ---
PAYMENT_FAILURE_CODES = {
    "UPI_TIMEOUT":        0.35,
    "INSUFFICIENT_FUNDS": 0.30,
    "WRONG_OTP":          0.15,
    "CARD_EXPIRED":       0.10,
    "BANK_SERVER_DOWN":   0.10,
}

# --- Checkout abandonment codes ---
CHECKOUT_CODES = {
    "CART_ABANDONED":     0.50,
    "CHECKOUT_TIMEOUT":   0.25,
    "SHIPPING_CONFUSION": 0.15,
    "PROMO_INVALID":      0.10,
}

# --- Subscription lapsed codes ---
SUBSCRIPTION_CODES = {
    "MANDATE_EXPIRED":    0.40,
    "MANDATE_REVOKED":    0.25,
    "SUBSCRIPTION_PAUSED":0.20,
    "PLAN_UPGRADE_FAILED":0.15,
}

# --- B2B receivable codes ---
B2B_CODES = {
    "INVOICE_OVERDUE":    0.50,
    "CREDIT_LIMIT_HIT":   0.30,
    "PAYMENT_DISPUTE":    0.20,
}

# --- Recovery probability by failure code (ground truth for ML) ---
RECOVERY_PROBABILITY_BY_CODE = {
    # Payment failures
    "UPI_TIMEOUT":         0.75,
    "BANK_SERVER_DOWN":    0.65,
    "WRONG_OTP":           0.55,
    "INSUFFICIENT_FUNDS":  0.30,
    "CARD_EXPIRED":        0.05,

    # Checkout abandonment (recovers well with the right nudge)
    "CART_ABANDONED":      0.45,
    "CHECKOUT_TIMEOUT":    0.60,
    "SHIPPING_CONFUSION":  0.40,
    "PROMO_INVALID":       0.55,

    # Subscription lapsed (mandate renewal can be tricky)
    "MANDATE_EXPIRED":     0.50,
    "MANDATE_REVOKED":     0.20,
    "SUBSCRIPTION_PAUSED": 0.65,
    "PLAN_UPGRADE_FAILED": 0.35,

    # B2B receivables (slowest recovery, needs escalation often)
    "INVOICE_OVERDUE":     0.40,
    "CREDIT_LIMIT_HIT":    0.15,
    "PAYMENT_DISPUTE":     0.25,
}

PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Net Banking"]

# Direction → amount ranges (B2B deals are larger)
AMOUNT_RANGE_BY_DIRECTION = {
    DIRECTION_PAYMENT:      (199, 15_000),
    DIRECTION_CHECKOUT:     (299, 8_000),
    DIRECTION_SUBSCRIPTION: (99, 2_999),
    DIRECTION_B2B:          (5_000, 500_000),
}


def _pick_code(code_dict: dict) -> str:
    codes = list(code_dict.keys())
    weights = list(code_dict.values())
    return random.choices(codes, weights=weights, k=1)[0]


def _generate_direction_rows(direction: str, n: int) -> list:
    if direction == DIRECTION_PAYMENT:
        code_dict = PAYMENT_FAILURE_CODES
    elif direction == DIRECTION_CHECKOUT:
        code_dict = CHECKOUT_CODES
    elif direction == DIRECTION_SUBSCRIPTION:
        code_dict = SUBSCRIPTION_CODES
    else:
        code_dict = B2B_CODES

    amount_min, amount_max = AMOUNT_RANGE_BY_DIRECTION[direction]
    rows = []

    for _ in range(n):
        failure_code = _pick_code(code_dict)
        amount = round(random.uniform(amount_min, amount_max), 2)
        payment_method = random.choice(PAYMENT_METHODS)
        attempt_number = random.choices(
            [1, 2, 3, 4], weights=[0.55, 0.25, 0.12, 0.08]
        )[0]
        timestamp = fake.date_time_between(start_date="-30d", end_date="now")

        base_prob = RECOVERY_PROBABILITY_BY_CODE[failure_code]
        adjusted_prob = max(0.02, base_prob - (attempt_number - 1) * 0.12)
        recovered = 1 if random.random() < adjusted_prob else 0

        rows.append({
            "transaction_id": None,   # filled in after merge
            "customer_id": f"CUST{random.randint(1000, 9999)}",
            "amount": amount,
            "payment_method": payment_method,
            "failure_code": failure_code,
            "direction": direction,
            "attempt_number": attempt_number,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "recovered": recovered,
        })

    return rows


def generate_transactions(n: int = 1000) -> pd.DataFrame:
    # Direction split: 60 / 20 / 10 / 10
    n_payment      = int(n * 0.60)
    n_checkout     = int(n * 0.20)
    n_subscription = int(n * 0.10)
    n_b2b          = n - n_payment - n_checkout - n_subscription

    all_rows = (
        _generate_direction_rows(DIRECTION_PAYMENT,      n_payment)
        + _generate_direction_rows(DIRECTION_CHECKOUT,    n_checkout)
        + _generate_direction_rows(DIRECTION_SUBSCRIPTION, n_subscription)
        + _generate_direction_rows(DIRECTION_B2B,         n_b2b)
    )

    random.shuffle(all_rows)  # mix directions so batch isn't sorted

    # Assign sequential transaction IDs after shuffle
    for i, row in enumerate(all_rows):
        row["transaction_id"] = f"TXN{10000 + i}"

    return pd.DataFrame(all_rows)


if __name__ == "__main__":
    df = generate_transactions(1000)
    df.to_csv("data/failed_transactions.csv", index=False)
    print(f"Generated {len(df)} transactions -> data/failed_transactions.csv")
    print("\nDirection distribution:")
    print(df["direction"].value_counts())
    print("\nFailure code distribution:")
    print(df["failure_code"].value_counts())
    print(f"\nOverall recovery rate: {df['recovered'].mean():.1%}")