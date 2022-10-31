#
# Copyright (c) Simple Things, Inc.
#
# All rights reserved.
#

from sqlalchemy import Boolean, Column, Integer, String

from sample_app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    is_active = Column(Boolean, default=True)
