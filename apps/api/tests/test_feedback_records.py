import asyncio

from sqlmodel import Session, SQLModel, create_engine

import src.routers.assets as assets_router
from src.models.settings import WorkspaceRecord


def test_feedback_record_lifecycle():
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(WorkspaceRecord(id='workspace-feedback', title='Feedback'))
        db.commit()

        created = assets_router.create_feedback(
            'workspace-feedback',
            assets_router.FeedbackCreate(
                feedbackId='3405', customerId='customer-a', message='提亮脸部', status='open',
            ),
            db,
        )
        assert created.feedbackId == '3405'
        assert created.status == 'open'

        updated = assets_router.update_feedback(
            'workspace-feedback',
            created.id,
            assets_router.FeedbackUpdate(status='processing', message='已开始处理'),
            db,
        )
        assert updated.status == 'processing'
        assert updated.message == '已开始处理'

        listed = assets_router.list_feedback('workspace-feedback', 'customer-a', db)
        assert [item.id for item in listed] == [created.id]

        removed = assets_router.delete_feedback('workspace-feedback', created.id, db)
        assert removed['removed'] is True
