from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse
)
from app.services.project_service import (
    create_project as create_project_service,
    get_user_projects as get_user_projects_service,
    get_project_by_id as get_project_by_id_service,
    update_project as update_project_service,
    delete_project as delete_project_service
)

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"]
)


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED
)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return create_project_service(
        db=db,
        user_id=current_user.id,
        project_data=project_data
    )


@router.get(
    "/",
    response_model=list[ProjectResponse]
)
def get_user_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_user_projects_service(
        db=db,
        user_id=current_user.id
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse
)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_project_by_id_service(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )


@router.put(
    "/{project_id}",
    response_model=ProjectResponse
)
def update_project(
    project_id: UUID,
    update_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_by_id_service(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    return update_project_service(
        db=db,
        project=project,
        update_data=update_data
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_200_OK
)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_by_id_service(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    delete_project_service(
        db=db,
        project=project
    )

    return {
        "message": "Project deleted successfully"
    }