from uuid import UUID
from fastapi import HTTPException, status 
from sqlalchemy import select 
from sqlalchemy.orm import Session, defer, load_only
from app.utils.logger import logger 
from app.models.project import Project 
from app.models.document import Document
from app.schemas.document import DocumentCreate,  DocumentUpdate

def create_document(
    db: Session,
    project_id: UUID,
    document_data: DocumentCreate
) -> Document:

    logger.info(
        f"Creating document '{document_data.title}' "
        f"for project: {project_id}"
    )

    try:
        new_document = Document(
            project_id=project_id,
            **document_data.model_dump()
        )

        db.add(new_document)
        db.commit()
        db.refresh(new_document)

        logger.success(
            f"Document created successfully: "
            f"{new_document.id}"
        )

        return new_document

    except Exception as e:
        db.rollback()

        logger.error(
            f"Document creation failed: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def get_project_documents(
    db: Session,
    project_id: UUID
) -> list[Document]:
    logger.info(
        f"Fetching documents for project: {project_id}"
    )

    try:
        result = db.execute(
            select(Document)
            .options(
                defer(Document.content),
                defer(Document.raw_content),
                defer(Document.document_metadata),
            )
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )

        documents = result.scalars().all()

        logger.info(
            f"Retrieved {len(documents)} documents "
            f"for project: {project_id}"
        )

        return documents

    except Exception as e:

        logger.error(
            f"Failed to fetch documents "
            f"for project {project_id}: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def get_user_documents(
    db: Session,
    user_id: UUID
) -> list[Document]:
    logger.info(f"Fetching all documents for user: {user_id}")

    try:
        result = db.execute(
            select(Document)
            .join(Project, Project.id == Document.project_id)
            .options(
                defer(Document.content),
                defer(Document.raw_content),
                defer(Document.document_metadata),
            )
            .where(Project.user_id == user_id)
            .order_by(Document.created_at.desc())
        )
        documents = result.scalars().all()
        logger.info(
            f"Retrieved {len(documents)} documents for user: {user_id}"
        )
        return documents

    except Exception as e:
        logger.error(
            f"Failed to fetch documents for user {user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

def get_document_by_id(
    db: Session,
    document_id: UUID
) -> Document:

    logger.info(
        f"Fetching document: {document_id}"
    )

    result = db.execute(
        select(Document).where(
            Document.id == document_id
        )
    )

    document = result.scalar_one_or_none()
    if not document:

        logger.warning(
            f"Document not found: {document_id}"
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return document

def verify_document_ownership(
    db: Session,
    document_id: UUID,
    user_id: UUID
) -> Document:

    logger.info(
        f"Verifying ownership for document "
        f"{document_id} and user {user_id}"
    )

    result = db.execute(
        select(Document)
        .join(Project)
        .where(
            Document.id == document_id,
            Project.user_id == user_id
        )
    )

    document = result.scalar_one_or_none()

    if not document:

        logger.warning(
            f"Unauthorized document access attempt. "
            f"Document: {document_id}, User: {user_id}"
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return document

def update_document(
    db: Session,
    document: Document,
    update_data: DocumentUpdate
) -> Document:

    logger.info(
        f"Updating document: {document.id}"
    )

    update_dict = update_data.model_dump(
        exclude_unset=True
    )

    try:
        for key, value in update_dict.items():
            setattr(document, key, value)

        db.commit()
        db.refresh(document)

        logger.success(
            f"Document updated successfully: "
            f"{document.id}"
        )

        return document

    except Exception as e:
        db.rollback()

        logger.error(
            f"Document update failed "
            f"for {document.id}: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


def delete_document(
    db: Session,
    document: Document
) -> None:

    logger.info(
        f"Deleting document: {document.id}"
    )

    try:
        db.delete(document)
        db.commit()

        logger.success(
            f"Document deleted successfully: "
            f"{document.id}"
        )

    except Exception as e:
        db.rollback()

        logger.error(
            f"Document deletion failed "
            f"for {document.id}: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )