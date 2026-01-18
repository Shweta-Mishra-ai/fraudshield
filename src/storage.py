import sqlite3
import json
from .models import Transaction, FraudResult

class Storage:
    def __init__(self, db_path="fraud_data.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                amount REAL,
                location TEXT,
                timestamp REAL,
                fraud_score REAL,
                is_fraud INTEGER,
                reasons TEXT
            )
        ''')
        self.conn.commit()

    def save_transaction(self, tx: Transaction, result: FraudResult):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (id, user_id, amount, location, timestamp, fraud_score, is_fraud, reasons)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tx.transaction_id, 
            tx.user_id, 
            tx.amount, 
            tx.location, 
            tx.timestamp, 
            result.score, 
            1 if result.is_fraud else 0, 
            json.dumps(result.reasons)
        ))
        self.conn.commit()

    def get_recent_transactions(self, limit=50):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?', (limit,))
        return cursor.fetchall()
