# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import inspect
from collections.abc import Callable
from typing import Any, Generic, ParamSpec, TypeVar

FuncArgs = ParamSpec("FuncArgs")
FuncReturn = TypeVar("FuncReturn")


class Wrapper(Generic[FuncArgs, FuncReturn]):
    def __init__(self, cache: "Cache", func: Callable[FuncArgs, FuncReturn]) -> None:
        self.cache = cache
        self.func = func
        self.disabled = False
        self.__module__ = func.__module__
        self.__name__ = func.__name__
        self.hits = 0
        self.misses = 0

    # When someone attempts to call a cached function, they'll
    # actually end up here. We first check if we have a cached
    # result and if not then we do the actual function call and
    # cache it if applicable
    def __call__(self, *args: FuncArgs.args, **kwargs: FuncArgs.kwargs) -> FuncReturn:
        if self.disabled:
            return self.func(*args, **kwargs)

        # Build the cache key from the function arguments that we
        # care about, which might be none of them
        key = self.cache.build_key(self.func, *args, **kwargs)
        # Don't cache
        if key is None:
            self.misses += 1
            return self.func(*args, **kwargs)

        if key not in self.cache.cache:
            self.misses += 1
            self.cache.cache[key] = self.func(*args, **kwargs)
        else:
            self.hits += 1
            if self.cache.cache_deepcopy:
                self.cache.cache[key] = copy.deepcopy(self.cache.cache[key])

        return self.cache.cache[key]

    def cache_clear(self) -> None:
        self.cache.clear()
        self.misses = 0
        self.hits = 0

    def cache_disable(self) -> None:
        self.disabled = True


class Cache:
    """
    Cache decorator for caching function results based on parameters.

    :param args: a list of function arguments to use as the cache key.
    :param kwargs: these are arguments where we should only cache if the
    function is called with the given value. For example, in pmb.build._package
    we never want to use the cached result when called with force=True.
    """

    def __init__(self, *args: str, cache_deepcopy: bool = False, **kwargs: object) -> None:
        for a in args:
            if not isinstance(a, str):
                raise ValueError(f"Cache key must be a string, not {type(a)}")

        if len(args) != len(set(args)):
            raise ValueError("Duplicate cache key properties")

        self.cache: dict[str, Any] = {}
        self.params = args
        self.kwargs = kwargs
        self.cache_deepcopy = cache_deepcopy

    # Build the cache key, or return None to not cache in the case where
    # we only cache when an argument has a specific value
    def build_key(
        self, func: Callable[FuncArgs, FuncReturn], *args: FuncArgs.args, **kwargs: FuncArgs.kwargs
    ) -> str | None:
        key = "~"
        # Easy case: cache irrelevant of arguments
        if not self.params and not self.kwargs:
            return key

        signature = inspect.signature(func)

        passed_args: dict[str, object] = {}
        for i, (k, val) in enumerate(signature.parameters.items()):
            if k in self.params or k in self.kwargs:
                if i < len(args):
                    passed_args[k] = args[i]
                elif k in kwargs:
                    passed_args[k] = kwargs[k]
                elif val.default != inspect.Parameter.empty:
                    passed_args[k] = val.default
                else:
                    raise ValueError(
                        f"Invalid cache key argument {k}"
                        f" in function {func.__module__}.{func.__name__}"
                    )

        for k, v in self.kwargs.items():
            if k not in signature.parameters:
                raise ValueError(
                    f"Cache key attribute {k} is not a valid parameter to {func.__name__}()"
                )
            passed_val = passed_args[k]
            if passed_val != v:
                # Don't cache
                return None
            else:
                key += f"{k}=({v})~"

        if self.params:
            for k, v in passed_args.items():
                if k in self.params:
                    key += f"{v}~"

        return key

    def __call__(self, func: Callable[FuncArgs, FuncReturn]) -> Wrapper[FuncArgs, FuncReturn]:
        argnames = func.__code__.co_varnames
        for a in self.params:
            if a not in argnames:
                raise ValueError(
                    f"Cache key attribute {a} is not a valid parameter to {func.__name__}()"
                )

        # FIXME: Once PEP-695 generics are in we shouldn't need this.
        return Wrapper(self, func)

    def clear(self) -> None:
        self.cache.clear()
