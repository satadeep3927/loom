import ast
import inspect
from typing import Dict, List, Any, Optional

from ..schemas.graph import WorkflowDefinitionGraph, GraphNode, GraphEdge
from .workflow import Workflow


class WorkflowAnalyzer:
    """Analyzes workflow definitions to extract structure and dependencies."""
    
    @staticmethod
    def analyze_workflow_definition(workflow_class: type[Workflow]) -> WorkflowDefinitionGraph:
        """Analyze workflow class to generate definition graph.
        
        Args:
            workflow_class: The workflow class to analyze
            
        Returns:
            WorkflowDefinitionGraph: Graph representation of the workflow structure
        """
        graph = WorkflowDefinitionGraph(
            nodes=[],
            edges=[],
            metadata={
                "workflow_name": getattr(workflow_class, "_workflow_name", workflow_class.__name__),
                "workflow_version": getattr(workflow_class, "_workflow_version", "1.0.0"),
                "workflow_description": getattr(workflow_class, "_workflow_description", ""),
            }
        )
        
        # Get compiled workflow to extract step information
        try:
            workflow_instance = workflow_class()
            compiled = workflow_instance._compile_instance()
        except Exception as e:
            raise ValueError(f"Failed to compile workflow {workflow_class.__name__}: {e}")
        
        previous_step_id = None
        
        # Analyze each step
        for step_info in compiled.steps:
            step_id = f"step_{step_info['name']}"
            
            # Add step node
            step_node = GraphNode(
                id=step_id,
                type="step",
                label=step_info["name"],
                metadata={
                    "description": step_info["description"],
                    "function": step_info["fn"]
                }
            )
            graph.nodes.append(step_node)
            
            # Add sequence edge from previous step
            if previous_step_id:
                sequence_edge = GraphEdge(**{
                    "from": previous_step_id,
                    "to": step_id,
                    "type": "sequence",
                    "label": "then"
                })
                graph.edges.append(sequence_edge)
            
            # Analyze step method for dependencies
            step_method = getattr(workflow_instance, step_info["fn"])
            dependencies = WorkflowAnalyzer._analyze_step_dependencies(step_method)
            
            # Add activity nodes and edges
            for activity_name in dependencies.get("activities", []):
                activity_id = f"activity_{activity_name}_{step_info['name']}"
                activity_node = GraphNode(
                    id=activity_id,
                    type="activity",
                    label=activity_name,
                    metadata={"called_from_step": step_info["name"]}
                )
                graph.nodes.append(activity_node)
                
                activity_edge = GraphEdge(**{
                    "from": step_id,
                    "to": activity_id,
                    "type": "calls",
                    "label": "executes"
                })
                graph.edges.append(activity_edge)
            
            # Add timer nodes
            for i, timer_info in enumerate(dependencies.get("timers", [])):
                timer_id = f"timer_{step_info['name']}_{i}"
                timer_node = GraphNode(
                    id=timer_id,
                    type="timer",
                    label=f"Sleep {timer_info}",
                    metadata={"step": step_info["name"]}
                )
                graph.nodes.append(timer_node)
                
                timer_edge = GraphEdge(**{
                    "from": step_id,
                    "to": timer_id,
                    "type": "waits",
                    "label": "pauses for"
                })
                graph.edges.append(timer_edge)
            
            # Add state dependency edges
            for state_key in dependencies.get("state_reads", []):
                state_id = f"state_{state_key}"
                
                # Add state node if not exists
                if not any(n.id == state_id for n in graph.nodes):
                    state_node = GraphNode(
                        id=state_id,
                        type="state",
                        label=f"state.{state_key}",
                        metadata={"key": state_key}
                    )
                    graph.nodes.append(state_node)
                
                read_edge = GraphEdge(**{
                    "from": state_id,
                    "to": step_id,
                    "type": "reads",
                    "label": "reads"
                })
                graph.edges.append(read_edge)
            
            for state_key in dependencies.get("state_writes", []):
                state_id = f"state_{state_key}"
                
                # Add state node if not exists  
                if not any(n.id == state_id for n in graph.nodes):
                    state_node = GraphNode(
                        id=state_id,
                        type="state",
                        label=f"state.{state_key}",
                        metadata={"key": state_key}
                    )
                    graph.nodes.append(state_node)
                    
                write_edge = GraphEdge(**{
                    "from": step_id,
                    "to": state_id,
                    "type": "writes",
                    "label": "updates"
                })
                graph.edges.append(write_edge)
            
            previous_step_id = step_id
        
        return graph
    
    @staticmethod
    def _analyze_step_dependencies(method) -> Dict[str, List[str]]:
        """Analyze step method source code to find dependencies.
        
        Args:
            method: The step method to analyze
            
        Returns:
            Dict containing lists of activities, timers, state reads/writes
        """
        dependencies = {
            "activities": [],
            "timers": [],
            "state_reads": [],
            "state_writes": []
        }
        
        try:
            # Get source code and parse AST
            source = inspect.getsource(method)
            
            # Remove common indentation to make it parseable
            import textwrap
            source = textwrap.dedent(source)
            
            # Remove decorators - find the first 'async def' or 'def' line
            lines = source.split('\n')
            def_line_idx = None
            for i, line in enumerate(lines):
                if 'def ' in line and ('async def' in line or line.strip().startswith('def')):
                    def_line_idx = i
                    break
            
            if def_line_idx is not None:
                # Keep only the function definition and body
                source = '\n'.join(lines[def_line_idx:])
            
            tree = ast.parse(source)
            
            class DependencyVisitor(ast.NodeVisitor):
                def visit_Call(self, node):
                    # Only handle non-awaited calls here
                    # Look for ctx.state.get() calls (non-awaited)
                    if (isinstance(node.func, ast.Attribute) and
                        isinstance(node.func.value, ast.Attribute) and
                        isinstance(node.func.value.value, ast.Name) and
                        node.func.value.value.id == "ctx" and
                        node.func.value.attr == "state" and
                        node.func.attr == "get"):
                        
                        # Extract state key from first argument
                        if (node.args and isinstance(node.args[0], ast.Constant)):
                            state_key = node.args[0].value
                            dependencies["state_reads"].append(state_key)
                    
                    self.generic_visit(node)
                    
                def visit_Await(self, node):
                    # Handle await ctx.activity(), await ctx.sleep(), await ctx.state.set()
                    if isinstance(node.value, ast.Call):
                        call_node = node.value
                        
                        # Check for await ctx.activity() 
                        if (isinstance(call_node.func, ast.Attribute) and
                            isinstance(call_node.func.value, ast.Name) and
                            call_node.func.value.id == "ctx" and
                            call_node.func.attr == "activity"):
                            
                            if call_node.args and isinstance(call_node.args[0], ast.Name):
                                activity_name = call_node.args[0].id
                                dependencies["activities"].append(activity_name)
                        
                        # Check for await ctx.sleep()
                        elif (isinstance(call_node.func, ast.Attribute) and
                              isinstance(call_node.func.value, ast.Name) and
                              call_node.func.value.id == "ctx" and
                              call_node.func.attr == "sleep"):
                            dependencies["timers"].append("sleep")
                        
                        # Check for await ctx.state.set()
                        elif (isinstance(call_node.func, ast.Attribute) and
                              isinstance(call_node.func.value, ast.Attribute) and
                              isinstance(call_node.func.value.value, ast.Name) and
                              call_node.func.value.value.id == "ctx" and
                              call_node.func.value.attr == "state" and
                              call_node.func.attr == "set"):
                            
                            if (call_node.args and isinstance(call_node.args[0], ast.Constant)):
                                state_key = call_node.args[0].value
                                dependencies["state_writes"].append(state_key)
                        
                        # Check for await ctx.state.update()
                        elif (isinstance(call_node.func, ast.Attribute) and
                              isinstance(call_node.func.value, ast.Attribute) and
                              isinstance(call_node.func.value.value, ast.Name) and
                              call_node.func.value.value.id == "ctx" and
                              call_node.func.value.attr == "state" and
                              call_node.func.attr == "update"):
                            dependencies["state_writes"].append("bulk_update")
                    
                    self.generic_visit(node)
                    
                def visit_Attribute(self, node):
                    # Look for ctx.state.get('key') reads (non-await calls)  
                    if (isinstance(node.value, ast.Attribute) and
                        isinstance(node.value.value, ast.Name) and
                        node.value.value.id == "ctx" and
                        node.value.attr == "state" and
                        node.attr == "get"):
                        
                        # This is a ctx.state.get access - we need to find the parent call
                        # For now, we'll skip this complex case
                        pass
                    
                    self.generic_visit(node)
            
            visitor = DependencyVisitor()
            visitor.visit(tree)
            
        except Exception as e:
            # If source analysis fails, return empty dependencies
            print(f"Warning: Could not analyze step method: {e}")
        
        return dependencies


def generate_mermaid_graph(graph: WorkflowDefinitionGraph) -> str:
    """Generate Mermaid diagram from definition graph.
    
    Args:
        graph: The workflow definition graph
        
    Returns:
        String containing Mermaid diagram syntax
    """
    lines = ["graph TD"]
    
    # Add nodes with appropriate shapes
    for node in graph.nodes:
        if node.type == "step":
            lines.append(f'    {node.id}["{node.label}"]')
        elif node.type == "activity":
            lines.append(f'    {node.id}("{node.label}")')
        elif node.type == "timer":
            lines.append(f'    {node.id}[["{node.label}"]]')
        elif node.type == "state":
            lines.append(f'    {node.id}{{{node.label}}}')
    
    # Add edges with appropriate styles
    for edge in graph.edges:
        if edge.type == "sequence":
            lines.append(f'    {edge.from_node} --> {edge.to_node}')
        elif edge.type == "calls":
            lines.append(f'    {edge.from_node} --> {edge.to_node}')
        elif edge.type == "reads":
            lines.append(f'    {edge.from_node} -.-> {edge.to_node}')
        elif edge.type == "writes":
            lines.append(f'    {edge.from_node} --> {edge.to_node}')
        elif edge.type == "waits":
            lines.append(f'    {edge.from_node} -.-> {edge.to_node}')
    
    return "\n".join(lines)


def generate_graphviz_dot(graph: WorkflowDefinitionGraph) -> str:
    """Generate GraphViz DOT format from definition graph.
    
    Args:
        graph: The workflow definition graph
        
    Returns:
        String containing DOT format graph
    """
    lines = [
        "digraph workflow {",
        "  rankdir=TD;",
        "  node [fontname=\"Arial\"]"
    ]
    
    # Add nodes with shapes and colors
    for node in graph.nodes:
        if node.type == "step":
            lines.append(f'  {node.id} [label="{node.label}" shape=box style=filled fillcolor=lightblue];')
        elif node.type == "activity":
            lines.append(f'  {node.id} [label="{node.label}" shape=ellipse style=filled fillcolor=lightgreen];')
        elif node.type == "timer":
            lines.append(f'  {node.id} [label="{node.label}" shape=diamond style=filled fillcolor=lightyellow];')
        elif node.type == "state":
            lines.append(f'  {node.id} [label="{node.label}" shape=hexagon style=filled fillcolor=lightcoral];')
    
    # Add edges with styles
    for edge in graph.edges:
        if edge.type == "sequence":
            lines.append(f'  {edge.from_node} -> {edge.to_node} [style=solid];')
        elif edge.type == "calls":
            lines.append(f'  {edge.from_node} -> {edge.to_node} [style=solid];')
        elif edge.type == "reads":
            lines.append(f'  {edge.from_node} -> {edge.to_node} [style=dashed];')
        elif edge.type == "writes":
            lines.append(f'  {edge.from_node} -> {edge.to_node} [style=solid];')
        elif edge.type == "waits":
            lines.append(f'  {edge.from_node} -> {edge.to_node} [style=dotted];')
    
    lines.append("}")
    return "\n".join(lines)