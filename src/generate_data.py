"""
Phase 1: Generate synthetic failed-payment transactions.

This creates fake but realistic-looking data for testing the
recovery pipeline. No real Razorpay data is used or needed.
"""

import pandas as pd
import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker("en_IN")
random.seed(42)  # reproducible results

# Failure reasons with realistic distribution
FAILURE_CODES = {
    "UPI_TIMEOUT": 0.35,
    "INSUFFICIENT_FUNDS": 0.30,
    "WRONG_OTP": 0.15,
    "CARD_EXPIRED": 0.10,
    "BANK_SERVER_DOWN": 0.10,
}

PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Net Banking"]

# Ground-truth "recovered" label used only to train the ML stopping-rule
# model later. Encodes a believable pattern: timeouts/server issues
# recover well on retry, insufficient funds recovers less well, wrong
# OTP recovers well if retried soon, expired cards almost never recover.
RECOVERY_PROBABILITY_BY_CAUSE = {
    "UPI_TIMEOUT": 0.75,
    "BANK_SERVER_DOWN": 0.65,
    "WRONG_OTP": 0.55,
    "INSUFFICIENT_FUNDS": 0.30,
    "CARD_EXPIRED": 0.05,
}


def pick_failure_code():
    codes = list(FAILURE_CODES.keys())
    weights = list(FAILURE_CODES.values())
    return random.choices(codes, weights=weights, k=1)[0]


def generate_transactions(n=600):
    rows = []
    for i in range(n):
        failure_code = pick_failure_code()
        amount = round(random.uniform(199, 15000), 2)
        payment_method = random.choice(PAYMENT_METHODS)
        attempt_number = random.choices([1, 2, 3, 4], weights=[0.55, 0.25, 0.12, 0.08])[0]
        timestamp = fake.date_time_between(start_date="-30d", end_date="now")

        base_prob = RECOVERY_PROBABILITY_BY_CAUSE[failure_code]
        adjusted_prob = max(0.02, base_prob - (attempt_number - 1) * 0.12)
        recovered = 1 if random.random() < adjusted_prob else 0

        rows.append({
            "transaction_id": f"TXN{10000 + i}",
            "customer_id": f"CUST{random.randint(1000, 9999)}",
            "amount": amount,
            "payment_method": payment_method,
            "failure_code": failure_code,
            "attempt_number": attempt_number,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "recovered": recovered,
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate_transactions(600)
    df.to_csv("data/failed_transactions.csv", index=False)
    print(f"Generated {len(df)} transactions -> data/failed_transactions.csv")
    print("\nFailure code distribution:")
    print(df["failure_code"].value_counts())
    print(f"\nOverall recovery rate in synthetic history: {df['recovered'].mean():.1%}")