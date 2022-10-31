#
# Copyright (c) Simple Things, Inc.
#
# All rights reserved.
#

from pydantic import BaseModel, Extra


class UserFilter(BaseModel, extra=Extra.forbid):
    email: str


class UserCreate(UserFilter, extra=Extra.forbid):
    password: str


class UserGet(UserFilter):
    is_active: bool
    id: int

    class Config:
        orm_mode = True
