#
# Copyright (c) Simple Things, Inc.
#
# All rights reserved.
#

import asyncio
import os
import pathlib

import pytest_asyncio
from autobahn.asyncio.component import Component
from autobahn.wamp.auth import AuthCryptoSign
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

env_path = os.path.join(pathlib.Path(__file__).parent, ".env")
load_dotenv(env_path)

from sample_app import models
from sample_app.database import SessionLocal, engine


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    # Create the database
    async with SessionLocal() as session:
        async with engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.drop_all)
            await conn.run_sync(models.Base.metadata.create_all)

        yield session
    # Clean database
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def wamp_session(event_loop):
    auth = AuthCryptoSign(
        privkey=os.environ.get("WAMP_API_PRIVKEY"),
        authid=os.environ.get("WAMP_API_AUTH_ID"),
    )
    router_url = os.environ.get("WAMP_API_ROUTER_URL")
    router_realm = os.environ.get("WAMP_API_ROUTER_REALM")

    component = Component(
        transports=router_url, realm=router_realm, authentication={"cryptosign": auth}
    )
    f: asyncio.Future = asyncio.Future()

    @component.on_join
    async def on_join(session, details):
        f.set_result(session)

    component.start(loop=event_loop)
    yield await f
    await component.stop()
