import networkx as nx
from typing import List, Dict, Set
from .models import Transaction

class FraudGraph:
    def __init__(self):
        self.graph = nx.Graph()
        
    def add_transaction(self, tx: Transaction):
        """Build a multi-modal graph connecting users, devices, IPs, and merchants"""
        user_node = f"User:{tx.user_id}"
        device_node = f"Device:{tx.device_id}"
        ip_node = f"IP:{tx.ip_address}"
        
        # Add nodes
        self.graph.add_node(user_node, type="user")
        self.graph.add_node(device_node, type="device")
        self.graph.add_node(ip_node, type="ip")
        
        # Add edges
        self.graph.add_edge(user_node, device_node, weight=tx.amount)
        self.graph.add_edge(user_node, ip_node, weight=tx.amount)
        self.graph.add_edge(device_node, ip_node, weight=tx.amount)
    
    def detect_fraud_rings(self) -> List[Dict]:
        """Identify suspicious clusters based on shared resources"""
        fraud_rings = []
        
        # Find devices/IPs connected to multiple users
        for node in self.graph.nodes():
            if node.startswith("Device:") or node.startswith("IP:"):
                neighbors = list(self.graph.neighbors(node))
                user_neighbors = [n for n in neighbors if n.startswith("User:")]
                
                # If more than 3 users share a device/IP, flag it
                if len(user_neighbors) >= 3:
                    fraud_rings.append({
                        "resource": node,
                        "users": user_neighbors,
                        "risk_score": min(len(user_neighbors) / 10.0, 1.0),
                        "type": "Shared Resource"
                    })
        
        return fraud_rings
    
    def get_network_stats(self) -> Dict:
        """Return graph statistics"""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "connected_components": nx.number_connected_components(self.graph)
        }
    
    def get_graph_data(self) -> Dict:
        """Export graph for visualization"""
        nodes = []
        edges = []
        
        for node in self.graph.nodes(data=True):
            node_type = node[1].get('type', 'unknown')
            nodes.append({
                "id": node[0],
                "type": node_type,
                "label": node[0].split(':')[1] if ':' in node[0] else node[0]
            })
        
        for edge in self.graph.edges(data=True):
            edges.append({
                "source": edge[0],
                "target": edge[1],
                "weight": edge[2].get('weight', 1)
            })
        
        return {"nodes": nodes, "edges": edges}
