from typing import List
from .models import Transaction, FraudResult

class Rule:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def evaluate(self, transaction: Transaction, history: List[Transaction]) -> float:
        raise NotImplementedError

class HighAmountRule(Rule):
    def evaluate(self, transaction: Transaction, history: List[Transaction]) -> float:
        if transaction.amount > 10000:
            return 1.0 # High probability
        if transaction.amount > 5000:
            return 0.7
        return 0.0

class LocationAnomalyRule(Rule):
    def evaluate(self, transaction: Transaction, history: List[Transaction]) -> float:
        # Simplified: if user jumps location rapidly. 
        # In a real app, we'd check previous transaction for THIS user.
        user_txs = [tx for tx in history if tx.user_id == transaction.user_id]
        if not user_txs:
            return 0.0
            
        last_tx = user_txs[-1]
        if last_tx.location != transaction.location:
            # Simple check: different country
            return 0.8
        return 0.0

class FraudDetector:
    def __init__(self):
        self.rules = [
            HighAmountRule("High Value", "Transaction amount exceeds threshold"),
            LocationAnomalyRule("Location Jump", "User location changed rapidly")
        ]
        self.history: List[Transaction] = []

    def analyze(self, transaction: Transaction) -> FraudResult:
        score = 0.0
        reasons = []
        triggered_rule = None

        for rule in self.rules:
            rule_score = rule.evaluate(transaction, self.history)
            if rule_score > 0:
                score = max(score, rule_score) # Take the highest risk
                reasons.append(f"{rule.name}: {rule.description}")
                if score >= 0.8:
                    triggered_rule = rule.name

        # Update history
        self.history.append(transaction)
        # Keep history manageable
        if len(self.history) > 1000:
            self.history.pop(0)

        return FraudResult(
            is_fraud=score > 0.5,
            score=score,
            reasons=reasons,
            rule_triggered=triggered_rule
        )
