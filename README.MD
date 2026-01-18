# 🛡️ Real-time Fraud Pathway AI

> **Advanced Anomaly Detection & AML Explainability Engine**

A production-ready, modular real-time fraud detection system built for the Pathway Hackathon. This project demonstrates high-throughput transaction monitoring, rule-based fraud detection, and interactive visual analytics.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🚀 Key Features

*   **Real-time Processing**: Simulates a high-velocity stream of financial transactions.
*   **Modular Architecture**: Clean separation of concerns with `Generator`, `Detector`, and `Storage` modules.
*   **Advanced Fraud Detection**:
    *   **Rule-Based Engine**: Easily extensible Python classes for defining fraud logic.
    *   **Behavioral Profiling**: Detects anomalies like "Location Jumps" and "High Velocity" spending.
*   **Persistent Storage**: SQLite integration for logging transaction history and audit trails.
*   **Interactive Dashboard**:
    *   **Live Metrics**: Monitor fraud rates and transaction volume in real-time.
    *   **Geospatial Heatmaps**: Visualize global fraud hotspots.
    *   **Scatter Plots**: Analyze transaction patterns (Safe vs. Fraud).

---

## 🏗️ Project Structure

```bash
├── src/
│   ├── detector.py    # Fraud detection rules engine
│   ├── generator.py   # Synthetic transaction stream generator
│   ├── models.py      # Data classes (Transaction, FraudResult)
│   └── storage.py     # SQLite persistence layer
├── app.py             # Main Streamlit dashboard application
├── requirements.txt   # Python dependencies
└── README.md          # Project documentation
```

---

## 🛠️ Installation & Setup

1.  **Clone the repository**
    ```bash
    git clone https://github.com/Shwetam77777/realtime-fraud-pathway.git
    cd realtime-fraud-pathway
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application**
    ```bash
    streamlit run app.py
    ```

---

## 🧠 How It Works

1.  **Data Generation**: The `TransactionGenerator` creates a realistic stream of diverse user transactions, injecting occasional anomalies (e.g., rapid high-value purchases).
2.  **Detection**: The `FraudDetector` evaluates each transaction against a set of rules (`HighAmountRule`, `LocationAnomalyRule`).
3.  **Scoring**: Each transaction receives a risk score (0-1). Scores above a threshold trigger alerts.
4.  **Visualization**: The Streamlit dashboard consumes the processed stream, updating charts and metrics live.

---

## 🔮 Future Roadmap

*   [ ] Integration with Kafka for production-grade streaming.
*   [ ] Machine Learning model (Random Forest/XGBoost) for predictive scoring.
*   [ ] API endpoint for external system integration.

---

Built with ❤️ by [Shweta Mishra]
