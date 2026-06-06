from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.report import (
    ReportCreate,
    ReportUpdate,
    ReportResponse,
    ReportListResponse
)
from app.services.project_service import verify_project_ownership
from app.services.report_service import (
    create_report,
    get_project_reports,
    get_report_by_id,
    update_report,
    delete_report
)

router = APIRouter(prefix="/api/v1", tags=["Reports"])

@router.post(
    "/projects/{project_id}/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED
)
def create_new_report(
    project_id: UUID,
    report_data: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_project_ownership(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    report = create_report(
        db=db,
        project_id=project_id,
        report_data=report_data
    )

    return report

@router.get(
    "/projects/{project_id}/reports",
    response_model=ReportListResponse
)
def list_project_reports(
    project_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_project_ownership(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    reports = get_project_reports(
        db=db,
        project_id=project_id,
        skip=skip,
        limit=limit,
    )

    return {
        "reports": reports
    }

@router.get(
    "/reports/{report_id}",
    response_model=ReportResponse
)
def get_report_details(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = get_report_by_id(
        db=db,
        report_id=report_id
    )

    verify_project_ownership(
        db=db,
        project_id=report.project_id,
        user_id=current_user.id
    )

    return report

@router.put(
    "/reports/{report_id}",
    response_model=ReportResponse
)
def update_existing_report(
    report_id: UUID,
    report_data: ReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = get_report_by_id(
        db=db,
        report_id=report_id
    )

    verify_project_ownership(
        db=db,
        project_id=report.project_id,
        user_id=current_user.id
    )

    return update_report(
        db=db,
        report=report,
        update_data=report_data
    )

@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_existing_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = get_report_by_id(
        db=db,
        report_id=report_id
    )

    verify_project_ownership(
        db=db,
        project_id=report.project_id,
        user_id=current_user.id
    )

    delete_report(
        db=db,
        report=report
    )

    return None

@router.post(
    "/reports/{report_id}/export"
)
def export_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = get_report_by_id(
        db=db,
        report_id=report_id
    )

    verify_project_ownership(
        db=db,
        project_id=report.project_id,
        user_id=current_user.id 
    )

    return {
        "message": f"Export report {report_id}"
    }


@router.get(
    "/reports/{report_id}/download/{format}"
)
def download_report(
    report_id: UUID,
    format: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = get_report_by_id(
        db=db,
        report_id=report_id
    )

    verify_project_ownership(
        db=db,
        project_id=report.project_id,
        user_id=current_user.id 
    )

    return {
        "message": f"Download report endpoint {report_id} as {format}"
    }
