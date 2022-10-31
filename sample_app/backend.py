#
# Copyright (c) Simple Things, Inc.
#
# All rights reserved.
#

from sqlalchemy import select
from sqlalchemy.engine import ChunkedIteratorResult
from sqlalchemy.ext.asyncio import AsyncSession

from sample_app import models, schemas


async def get_user(db: AsyncSession, user_id: int):
    stmt = select(models.User).where(models.User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar()


async def get_user_by_email(db: AsyncSession, email: str):
    stmt = select(models.User).where(models.User.email == email)
    result = await db.execute(stmt)
    return result.scalar()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = select(models.User).offset(skip).limit(limit)
    result: ChunkedIteratorResult = await db.execute(stmt)
    return [item[0] for item in result]


async def create_user(db: AsyncSession, user: schemas.UserCreate):
    db_user = models.User(email=user.email, password=user.password)
    db.add(db_user)

    await db.commit()
    await db.refresh(db_user)

    return db_user
