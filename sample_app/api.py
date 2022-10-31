#
# Copyright (c) Simple Things, Inc.
#
# All rights reserved.
#

from autobahn.wamp import ApplicationError, CallDetails
from sqlalchemy.ext.asyncio import AsyncSession

from wampapi import Depends, register
from sample_app import backend, models, database, schemas


async def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        await db.close()


class Accounts:
    @register(response_schema=schemas.UserGet)
    async def create(
        self,
        user: schemas.UserCreate,
        session: AsyncSession = Depends(get_db),
        details: CallDetails | None = None,
    ):
        db_account = await backend.get_user_by_email(session, user.email)
        if db_account:
            raise ApplicationError("com.thing.error.already_exists", "Email already registered")

        return await backend.create_user(session, user)

    @register(response_schema=schemas.UserGet, allowed_roles=["anonymous"])
    async def get(
        self,
        user: schemas.UserCreate,
        session: AsyncSession = Depends(get_db),
        details: CallDetails | None = None,
    ):
        db_account: models.User = await backend.get_user_by_email(session, user.email)
        if not db_account:
            raise ApplicationError("com.thing.error.not_found", "Account does not exist")

        if db_account.password != user.password:
            raise ApplicationError("com.thing.error.not_authorized", "dude that's wrong password")

        return db_account

    @register(response_schema=schemas.UserGet)
    async def list(
        self, session: AsyncSession = Depends(get_db), details: CallDetails | None = None
    ):
        return await backend.get_users(session)

    @register()
    async def echo(self, first_name: str, details: CallDetails | None = None):
        return first_name
