import networkx as nx
import logging

logger = logging.getLogger(__name__)

class DAGEngine:
    def __init__(self):
        self.graph = nx.DiGraph()
        
    def parse_nodes(self, nodes_data, edges_data):
        for node in nodes_data:
            self.graph.add_node(node['id'], **node)
        for edge in edges_data:
            self.graph.add_edge(edge['source'], edge['target'])
            
        if not nx.is_directed_acyclic_graph(self.graph):
            raise ValueError("Workflow must be directed acyclic graph (no infinite loops).")
            
    def execute(self, initial_context: dict):
        try:
            # Topological sort guarantees parent nodes run before children
            execution_order = list(nx.topological_sort(self.graph))
            context = initial_context.copy()
            
            for node_id in execution_order:
                node_data = self.graph.nodes[node_id]
                node_type = node_data.get('type')
                logger.info(f"Executing Node: {node_type} ({node_id})")
                
                # Mock execution logic based on type
                if node_type == 'QueryRAGNode':
                    context['rag_result'] = "Simulated RAG output injected into context"
                elif node_type == 'AskAgentNode':
                    prompt = node_data.get('prompt', 'Assess context')
                    context['agent_response'] = f"Agent analyzed: {prompt}. Context: {context.get('rag_result')}"
                elif node_type == 'SlackMessageNode':
                    logger.info(f"WOULD SEND SLACK MESSAGE: {context.get('agent_response')}")
                    
            return {"status": "success", "final_context": context}
        except nx.NetworkXUnfeasible:
             return {"status": "error", "error": "Graph validation failed."}
        except Exception as e:
             return {"status": "error", "error": str(e)}
