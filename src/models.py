from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Transaction:
    transaction_id: str
    user_id: str
    amount: float
    currency: str
    timestamp: float
    merchant_id: str
    location: str  # e.g., "US", "IN"
    device_id: str
    ip_address: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "timestamp": self.timestamp,
            "merchant_id": self.merchant_id,
            "location": self.location,
            "device_id": self.device_id,
            "ip_address": self.ip_address
        }

@dataclass
class FraudResult:
    is_fraud: bool
    score: float
    reasons: list[str]
    rule_triggered: Optional[str] = None
