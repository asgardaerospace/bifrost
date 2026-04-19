from fastapi import APIRouter

router = APIRouter()


@router.get("/runs")
def list_workflow_runs() -> list:
    return []
