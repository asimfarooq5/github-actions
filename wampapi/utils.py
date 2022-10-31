#
# Copyright (c) Simple Things, Inc.
#
# All rights reserved.
#

import contextlib
import inspect
import functools
import json
import types
from dataclasses import dataclass
from typing import Type, Union, Callable

from autobahn.wamp import ApplicationError, CallDetails, RegisterOptions
from pydantic import BaseModel, ValidationError


async def register_bulk(
    session, api_class, prefix: str | None = None, options: RegisterOptions | None = None
):
    apis = api_class()
    for method in dir(apis):
        if method.startswith("__"):
            continue

        func = getattr(apis, method)
        if not hasattr(func, "__wampapi_meta__"):
            continue

        meta: dict = func.__wampapi_meta__

        if prefix is not None:
            uri = f"{prefix}{meta['uri']}"
        else:
            uri = meta["uri"]

        try:
            reg = await session.register(func, uri, options=options)
            print(f"registered procedure {reg.procedure}")
        except ApplicationError as e:
            print(f"failed to register procedure {uri}:", e.error)


class Depends:
    def __init__(self, func: Callable) -> None:
        super().__init__()
        self.func_to_call = self._setup(func)

    def _setup(self, func: Callable):
        if not inspect.isasyncgenfunction(func) and not inspect.iscoroutinefunction(func):
            raise ValueError("func must be a coroutine or async generator")

        return contextlib.asynccontextmanager(func)

    def __call__(self):
        return self.func_to_call()


def append_wamp_meta(uri, func: Callable, response_schema: Type[BaseModel] | None = None):
    uri = func.__name__ if uri is None else uri

    if not hasattr(func, "__wampapi_meta__"):
        func.__wampapi_meta__ = {}  # type: ignore

    if response_schema is not None:
        func.__wampapi_meta__.update(  # type: ignore
            {"response_fields": response_schema.__fields__}
        )

    func.__wampapi_meta__.update({"uri": uri})  # type: ignore


def serialize(data, schema: Type[BaseModel]):
    try:
        if isinstance(data, list):
            return [json.loads(schema.from_orm(item).json()) for item in data]

        return json.loads(schema.from_orm(data).json())
    except Exception as e:
        raise ApplicationError("com.thing.error.unknown_payload", e.args)


@dataclass
class FuncMeta:
    request_schema: Type[BaseModel]
    schema_param_name: str
    arg_names: list
    kwarg_names: list
    depends: dict
    call_details_in_sig: bool


def validate_signature(func):
    # Get names of all the parameters of the function
    arg_names = []
    kwarg_names = []
    depends = {}
    for key, value in inspect.signature(func).parameters.items():
        # a parameter with an empty default value is a positional arg
        if value.default == inspect._empty:
            arg_names.append(key)
        else:
            if isinstance(value.default, Depends):
                depends.update({key: value.default})

            kwarg_names.append(key)

    spec = inspect.getfullargspec(func)
    arguments = spec.args
    # Remove the "self" if it's a method, it's convenient.
    if len(arguments) > 0 and arguments[0] == "self":
        arg_names.pop(0)
        arguments.pop(0)

    # Ensure all parameters of the function have type hints
    if len(spec.annotations.keys()) != len(arguments):
        raise ValueError(f"func={func.__name__}: all parameters must have type hints")

    # In case a pydantic schema is declared in the arguments,
    # ensure that there is exactly one such parameter.
    # We also want to make sure only 1 CallDetails argument is used.
    schema_count = 0
    call_details_count = 0
    request_schema: Type[BaseModel] | None = None
    schema_parameter = None
    for name, hint in spec.annotations.items():
        if not inspect.isclass(hint):
            continue
        elif issubclass(hint, BaseModel):
            schema_count += 1
            request_schema = hint
            schema_parameter = name
        elif issubclass(hint, CallDetails):
            call_details_count += 1

        if schema_count > 1:
            msg = (
                f"func={func.__name__}: must only provide a single pydantic schema in "
                f"function arguments"
            )
            raise ValueError(msg)
        elif call_details_count > 1:
            msg = f"func={func.__name__}: must only provide CallDetails once in function arguments"
            raise ValueError(msg)

    return FuncMeta(
        request_schema=request_schema,
        schema_param_name=schema_parameter,
        arg_names=arg_names,
        kwarg_names=kwarg_names,
        depends=depends,
        call_details_in_sig=call_details_count == 1,
    )


def authorize_caller(
    allowed_roles: list[str] | None, role_delimiter: str, call_details: CallDetails
):
    if allowed_roles is None:
        return

    if call_details is None:
        raise ApplicationError(
            "com.thing.error.unauthorized",
            f"call details not disclosed. hence can't check role. expected one of {allowed_roles}",
        )
    elif call_details.caller_authrole is None:
        raise ApplicationError(
            "com.thing.error.unauthorized",
            f"call details does not contain caller_authrole. expected one of {allowed_roles}",
        )

    roles = call_details.caller_authrole.split(role_delimiter)
    allowed = False
    for role in allowed_roles:
        if role in roles:
            allowed = True
            break

    if not allowed:
        raise ApplicationError(
            "com.thing.error.unauthorized", f"authrole={roles}, expected one of {allowed_roles}"
        )


def register(
    uri: str | None = None,
    response_schema: Type[BaseModel] | None = None,
    allowed_roles: list[str] | None = None,
    role_delimiter=",",
):

    if uri is not None and not isinstance(uri, str) and len(uri) == 0:
        raise ValueError("uri should be None or of type str")

    if response_schema is not None and not issubclass(response_schema, BaseModel):
        raise ValueError("response_schema must be pydantic schema")

    if allowed_roles is not None and not isinstance(allowed_roles, list):
        raise ValueError("allowed_roles should be None or a list of string")

    def validate(func):
        func_meta = validate_signature(func)

        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            schema_kwargs = {}
            extra_kwargs = {}
            call_details: CallDetails | None = None
            for k, v in kwargs.items():
                if isinstance(v, CallDetails):
                    call_details = v
                    continue

                # if we have the pydantic schema defined for the request
                # lets gather all the kwargs that are required for it.
                if (
                    func_meta.request_schema is not None
                    and k in func_meta.request_schema.__fields__
                ):
                    schema_kwargs.update({k: v})
                else:
                    extra_kwargs.update({k: v})

            # if the router sent the CallDetails, use the information
            # inside it to authorize the call
            if call_details is not None:
                authorize_caller(allowed_roles, role_delimiter, call_details)

            # strip kwargs to only include CallDetails
            if func_meta.call_details_in_sig:
                kwargs = {k: v for k, v in kwargs.items() if isinstance(v, CallDetails)}
            else:
                kwargs = {}

            if func_meta.request_schema is not None:
                try:
                    model = func_meta.request_schema(**schema_kwargs)
                except ValidationError as e:
                    raise ApplicationError("com.thing.system.error.invalid_argument", e.json())

                kwargs.update({func_meta.schema_param_name: model})

            # Validate non-pydantic schema arguments
            arguments = inspect.getcallargs(func, *args, **kwargs, **extra_kwargs)
            errors = []

            for name, kind in wrapped.__annotations__.items():
                # If it's a dependency, no need to validate
                if isinstance(arguments[name], Depends):
                    continue

                # If it's a pydantic serializer, no need to validate
                if isinstance(arguments[name], BaseModel):
                    continue

                # if a "type" has __origin__ attribute it is a
                # parameterized generic.
                # https://stackoverflow.com/a/50080269
                if getattr(kind, "__origin__", None) == Union or isinstance(kind, types.UnionType):
                    expected_types = [arg.__name__ for arg in kind.__args__]
                    if not isinstance(arguments[name], kind.__args__):
                        errors.append(
                            "'{}' expected types={} got={}".format(
                                name, expected_types, type(arguments[name]).__name__
                            )
                        )

                elif not isinstance(arguments[name], kind):
                    errors.append(
                        "'{}' expected type={} got={}".format(
                            name, kind.__name__, type(arguments[name]).__name__
                        )
                    )

            if len(errors) > 0:
                raise ApplicationError("com.thing.error.invalid_params", errors)

            # let's inject the dependencies if any
            if len(func_meta.depends) > 0:
                async with contextlib.AsyncExitStack() as stack:
                    for k, v in func_meta.depends.items():
                        r = await stack.enter_async_context(v())
                        kwargs.update({k: r})

                    # TODO: catch any exception here and raise manually
                    result = await func(*args, **kwargs)

                    if response_schema is not None:
                        return serialize(result, response_schema)

                    return result
            else:
                # TODO: catch any exception here and raise manually
                result = await func(*args, **kwargs)

                if response_schema is not None:
                    return serialize(result, response_schema)

                return result

        append_wamp_meta(uri, wrapped, response_schema)
        return wrapped

    return validate
