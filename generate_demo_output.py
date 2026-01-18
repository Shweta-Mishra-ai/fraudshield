import time
from src.generator import TransactionGenerator
from src.detector import FraudDetector

def generate_demo_logs():
    generator = TransactionGenerator()
    detector = FraudDetector()
    stream = generator.generate_stream()
    
    with open("DEMO_OUTPUT.md", "w", encoding="utf-8") as f:
        f.write("# 🔍 Real-time Fraud Detection Log Capture\n")
        f.write(f"**Generated on:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n")
        
        f.write("Starting transaction stream analysis...\n\n")
        
        # Run for a fixed number of transactions to generate a log
        for i in range(1, 21):
            tx = next(stream)
            result = detector.analyze(tx)
            
            icon = "🔴" if result.is_fraud else "🟢"
            status = "FRAUD DETECTED" if result.is_fraud else "SAFE"
            
            f.write(f"### Transaction #{i}\n")
            f.write(f"`{tx.transaction_id}`\n")
            f.write(f"- **User**: {tx.user_id}\n")
            f.write(f"- **Amount**: ${tx.amount:,.2f}\n")
            f.write(f"- **Location**: {tx.location}\n")
            f.write(f"- **Status**: {icon} **{status}**\n")
            if result.is_fraud:
                f.write(f"- **Risk Score**: {result.score}\n")
                f.write(f"- **Reasons**: {', '.join(result.reasons)}\n")
                if result.rule_triggered:
                    f.write(f"- **Triggered Rule**: {result.rule_triggered}\n")
            f.write("\n---\n")

if __name__ == "__main__":
    generate_demo_logs()
