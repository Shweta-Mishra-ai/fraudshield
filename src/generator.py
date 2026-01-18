import random
import time
import uuid
from typing import Generator
from .models import Transaction

class TransactionGenerator:
    def __init__(self):
        self.users = [f"User_{i}" for i in range(1, 101)]
        self.merchants = [f"Merch_{i}" for i in range(1, 21)]
        self.locations = ["US", "IN", "UK", "CA", "AU", "DE", "JP"]
        
    def generate_stream(self) -> Generator[Transaction, None, None]:
        while True:
            user = random.choice(self.users)
            
            # Simulate patterns: specific users might have anomalies
            if user == "User_13":
                amount = random.uniform(5000, 20000) # High value anomaly
            else:
                amount = random.uniform(10, 1000)
            
            yield Transaction(
                transaction_id=str(uuid.uuid4()),
                user_id=user,
                amount=round(amount, 2),
                currency="USD",
                timestamp=time.time(),
                merchant_id=random.choice(self.merchants),
                location=random.choice(self.locations),
                device_id=f"Dev_{random.randint(1, 50)}",
                ip_address=f"192.168.1.{random.randint(1, 255)}"
            )
            time.sleep(random.uniform(0.1, 1.0)) # Simulate variable network delay
