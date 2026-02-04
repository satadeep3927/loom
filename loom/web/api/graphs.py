"""Graph API Endpoints

Provides REST endpoints for generating workflow definition graphs.
"""

from enum import Enum
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from ...common.workflow import workflow_registry
from ...core.graph import (
    WorkflowAnalyzer,
    generate_graphviz_dot,
    generate_mermaid_graph,
)
from ...database.db import Database
from ...schemas.graph import GraphResponse, WorkflowDefinitionGraph
from ..schemas import ErrorResponse

router = APIRouter()


async def get_db():
    """Database dependency"""
    async with Database[Any, Any]() as db:
        yield db


class GraphFormatEnum(str, Enum):
    """Supported graph output formats"""
    JSON = "json"
    MERMAID = "mermaid"
    DOT = "dot"


@router.get(
    "/workflow/{workflow_id}/definition",
    response_model=WorkflowDefinitionGraph,
    summary="Get workflow definition graph",
    description="""
    Generate a static workflow definition graph showing the structure of steps,
    activities, timers, and state dependencies as defined in the workflow code.

    This is similar to Airflow's DAG view - it shows the workflow structure
    based on code analysis, not runtime execution.

    **Features:**
    - Step sequence and dependencies
    - Activity calls within each step
    - Timer/sleep operations
    - State read/write dependencies
    - Workflow metadata

    **Node Types:**
    - `step`: Workflow steps (blue boxes)
    - `activity`: Activity calls (green circles)
    - `timer`: Sleep/delay operations (yellow diamonds)
    - `state`: State variables (red hexagons)

    **Edge Types:**
    - `sequence`: Step-to-step flow
    - `calls`: Step calls activity
    - `reads`: Reads from state
    - `writes`: Writes to state
    - `waits`: Step waits on timer
    """,
    responses={
        404: {"model": ErrorResponse, "description": "Workflow not found"},
        400: {"model": ErrorResponse, "description": "Invalid workflow definition"},
        500: {"model": ErrorResponse, "description": "Analysis failed"}
    }
)
async def get_workflow_definition_graph(workflow_id: str, db: Database = Depends(get_db)):
    """Get workflow definition graph as structured data"""
    try:
        # Get workflow info from database
        workflow_info = await db.get_workflow_info(workflow_id)
        if not workflow_info:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow with ID '{workflow_id}' not found"
            )

        # Get workflow class using module and name from database
        workflow_class = workflow_registry(workflow_info["module"], workflow_info["name"])

        # Analyze workflow definition
        graph = WorkflowAnalyzer.analyze_workflow_definition(workflow_class)

        return graph

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ModuleNotFoundError, AttributeError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Failed to load workflow class: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze workflow: {str(e)}"
        )


@router.get(
    "/workflow/{workflow_id}/definition/render",
    response_model=GraphResponse,
    summary="Render workflow definition graph",
    description="""
    Generate a workflow definition graph in various output formats for visualization.

    **Supported Formats:**
    - `json`: Structured JSON data (same as /definition endpoint)
    - `mermaid`: Mermaid diagram syntax for rendering
    - `dot`: GraphViz DOT format for advanced visualization

    **Usage Examples:**
    - Use `mermaid` format to render in web UIs or documentation
    - Use `dot` format for GraphViz tools (dot, neato, fdp, etc.)
    - Use `json` format for custom visualization libraries

    **Mermaid Example:**
    ```
    graph TD
        step_process["Process Order"]
        activity_payment("process_payment")
        state_paid{state.payment_confirmed}
        step_process --> activity_payment
        step_process --> state_paid
    ```
    """,
    responses={
        404: {"model": ErrorResponse, "description": "Workflow not found"},
        400: {"model": ErrorResponse, "description": "Invalid format or workflow"},
        500: {"model": ErrorResponse, "description": "Rendering failed"}
    }
)
async def render_workflow_definition_graph(
    workflow_id: str,
    format: GraphFormatEnum = Query(
        GraphFormatEnum.MERMAID,
        description="Output format for the graph"
    ),
    db: Database = Depends(get_db)
):
    """Render workflow definition graph in specified format"""
    try:
        # Get workflow info from database
        workflow_info = await db.get_workflow_info(workflow_id)
        if not workflow_info:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow with ID '{workflow_id}' not found"
            )

        # Get workflow class using module and name from database
        workflow_class = workflow_registry(workflow_info["module"], workflow_info["name"])

        # Analyze workflow definition
        graph = WorkflowAnalyzer.analyze_workflow_definition(workflow_class)

        # Generate output based on format
        if format == GraphFormatEnum.JSON:
            content = graph.json(indent=2)
        elif format == GraphFormatEnum.MERMAID:
            content = generate_mermaid_graph(graph)
        elif format == GraphFormatEnum.DOT:
            content = generate_graphviz_dot(graph)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {format}"
            )

        return GraphResponse(
            format=format.value,
            content=content,
            metadata={
                "workflow_id": workflow_id,
                "workflow_name": workflow_info["name"],
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                **graph.metadata
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ModuleNotFoundError, AttributeError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Failed to load workflow class: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to render graph: {str(e)}"
        )


@router.get(
    "/workflows/",
    response_model=Dict[str, Any],
    summary="List workflows for graph generation",
    description="""
    Get a list of all workflows in the database that can be analyzed for graphs.

    Returns workflow IDs, names, versions, and basic metadata for each workflow.
    Use the workflow ID with the graph endpoints to generate visualizations.
    """
)
async def list_workflows_for_graphs(db: Database = Depends(get_db)):
    """List all workflows available for graph generation"""
    try:
        # Get all workflows from database
        workflows_sql = """
            SELECT id, name, description, version, module, status, created_at, updated_at
            FROM workflows
            ORDER BY created_at DESC
        """
        workflows = await db.query(workflows_sql)

        workflow_list = []
        for workflow in workflows:
            workflow_list.append({
                "id": workflow["id"],
                "name": workflow["name"],
                "description": workflow["description"] or "",
                "version": workflow["version"],
                "module": workflow["module"],
                "status": workflow["status"],
                "created_at": workflow["created_at"],
                "updated_at": workflow["updated_at"]
            })

        return {
            "total_count": len(workflow_list),
            "workflows": workflow_list
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list workflows: {str(e)}"
        )
