#
# Copyright (c) Simple Things, Inc.
#
# All rights reserved.
#

import pytest

from wampapi import utils
from sample_app import api


@pytest.mark.api
@pytest.mark.asyncio
async def test_register_bulk_success(wamp_session, db):
    await utils.register_bulk(wamp_session, api.Accounts)

    test_create = await wamp_session.call("create", email="john@test.com", password="password")
    test_get = await wamp_session.call("get", email="john@test.com", password="password")
    test_list = await wamp_session.call("list")
    test_echo = await wamp_session.call("echo", "test-echo")

    assert test_create.get("email") == "john@test.com"
    assert isinstance(test_get, dict)
    assert isinstance(test_list, list)
    assert test_echo == "test-echo"

