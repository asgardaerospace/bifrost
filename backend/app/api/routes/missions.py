"""Mission HTTP routes — canonical doctrine surface."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.mission import (
    MissionCreate,
    MissionDependencies,
    MissionEntityCreate,
    MissionEntityRead,
    MissionPressure,
    MissionRead,
    MissionTimeline,
    MissionUpdate,
)
from app.services import mission as mission_service

router = APIRouter()


@router.get("/missions", response_model=list[MissionRead])
def list_missions(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    owner_user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> list[MissionRead]:
    rows = mission_service.list_missions(
        db,
        status=status_filter,
        priority=priority,
        owner_user_id=owner_user_id,
    )
    return [MissionRead.model_validate(r) for r in rows]


@router.post(
    "/missions", response_model=MissionRead, status_code=status.HTTP_201_CREATED
)
def create_mission(
    payload: MissionCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> MissionRead:
    mission = mission_service.create_mission(db, payload, actor=user.email)
    return MissionRead.model_validate(mission)


@router.get("/missions/{mission_id}", response_model=MissionRead)
def get_mission(mission_id: int, db: Session = Depends(get_db)) -> MissionRead:
    mission = mission_service.get_mission(db, mission_id)
    return MissionRead.model_validate(mission)


@router.patch("/missions/{mission_id}", response_model=MissionRead)
def update_mission(
    mission_id: int,
    payload: MissionUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> MissionRead:
    mission = mission_service.update_mission(db, mission_id, payload, actor=user.email)
    return MissionRead.model_validate(mission)


@router.delete("/missions/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    mission_service.soft_delete_mission(db, mission_id, actor=user.email)


@router.get(
    "/missions/{mission_id}/pressure", response_model=MissionPressure
)
def mission_pressure(
    mission_id: int, db: Session = Depends(get_db)
) -> MissionPressure:
    return mission_service.build_pressure(db, mission_id)


@router.get(
    "/missions/{mission_id}/dependencies", response_model=MissionDependencies
)
def mission_dependencies(
    mission_id: int, db: Session = Depends(get_db)
) -> MissionDependencies:
    return mission_service.build_dependencies(db, mission_id)


@router.get(
    "/missions/{mission_id}/timeline", response_model=MissionTimeline
)
def mission_timeline(
    mission_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> MissionTimeline:
    return mission_service.build_timeline(db, mission_id, limit=limit)


@router.get(
    "/missions/{mission_id}/entities",
    response_model=list[MissionEntityRead],
)
def mission_entities(
    mission_id: int, db: Session = Depends(get_db)
) -> list[MissionEntityRead]:
    rows = mission_service.list_entities(db, mission_id)
    return [MissionEntityRead.model_validate(r) for r in rows]


@router.post(
    "/missions/{mission_id}/entities",
    response_model=MissionEntityRead,
    status_code=status.HTTP_201_CREATED,
)
def link_mission_entity(
    mission_id: int,
    payload: MissionEntityCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> MissionEntityRead:
    link = mission_service.link_entity(db, mission_id, payload, actor=user.email)
    return MissionEntityRead.model_validate(link)


@router.delete(
    "/missions/{mission_id}/entities/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_mission_entity(
    mission_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    mission_service.unlink_entity(db, mission_id, link_id, actor=user.email)


@router.get(
    "/missions/{mission_id}/entities/grouped",
    response_model=dict[str, list[MissionEntityRead]],
)
def mission_entities_grouped(
    mission_id: int, db: Session = Depends(get_db)
) -> dict[str, list[MissionEntityRead]]:
    """Linked entities grouped by entity_type — one query per group, used by
    the mission detail tabs."""
    grouped = mission_service.list_linked_entities_grouped(db, mission_id)
    return {
        et: [MissionEntityRead.model_validate(r) for r in rows]
        for et, rows in grouped.items()
    }
