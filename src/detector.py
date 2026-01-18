from typing import List
import numpy as np
from sklearn.ensemble import IsolationForest
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

class MLAnomalyRule(Rule):
    """ML-based anomaly detection using Isolation Forest"""
    def __init__(self):
        super().__init__("ML Anomaly", "Machine learning detected unusual pattern")
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.is_trained = False
        
    def evaluate(self, transaction: Transaction, history: List[Transaction]) -> float:
        # Need at least 50 transactions to train
        if len(history) < 50:
            return 0.0
            
        # Extract features from history
        features = self._extract_features(history + [transaction])
        
        # Train model if not already trained, or retrain periodically
        if not self.is_trained or len(history) % 100 == 0:
            self.model.fit(features[:-1])  # Train on history
            self.is_trained = True
        
        # Predict on current transaction
        current_features = features[-1:]
        prediction = self.model.predict(current_features)
        score = self.model.score_samples(current_features)
        
        # prediction == -1 means anomaly
        if prediction[0] == -1:
            # Normalize score to 0-1 range
            normalized_score = min(abs(score[0]) / 2, 1.0)
            return normalized_score
        return 0.0
    
    def _extract_features(self, transactions: List[Transaction]) -> np.ndarray:
        """Extract numerical features from transactions"""
        features = []
        location_map = {}  # Simple encoding for location
        
        for tx in transactions:
            # Get or create location encoding
            if tx.location not in location_map:
                location_map[tx.location] = len(location_map)
            
            features.append([
                tx.amount,
                location_map[tx.location],
                hash(tx.device_id) % 1000,  # Simple hash for device
                hash(tx.ip_address) % 1000   # Simple hash for IP
            ])
        
        return np.array(features)

class FraudDetector:
    def __init__(self):
        self.rules = [
            HighAmountRule("High Value", "Transaction amount exceeds threshold"),
            LocationAnomalyRule("Location Jump", "User location changed rapidly"),
            MLAnomalyRule()
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
