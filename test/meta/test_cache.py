# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

from pmb.meta import Cache, Wrapper


def test_cache_hits_basic() -> None:
    def multiply_2(x: int) -> int:
        return x * 2

    multiply_2_cached = Cache("x")(multiply_2)

    assert isinstance(multiply_2_cached, Wrapper)

    assert multiply_2(2) == 4

    assert multiply_2_cached(2) == 4
    assert multiply_2_cached.misses == 1

    assert multiply_2_cached(2) == 4
    assert multiply_2_cached.hits == 1

    assert multiply_2_cached(3) == 6
    assert multiply_2_cached.misses == 2

    assert multiply_2_cached(4) == 8
    assert multiply_2_cached.misses == 3

    assert multiply_2_cached(3) == 6
    assert multiply_2_cached.hits == 2


def test_cache_hits_kwargs() -> None:
    def multiply_2(x: int, y: int = 2, z: list[int] = []) -> int:
        return x * y + sum(z)

    multiply_2_cached = Cache("x", "y", "z")(multiply_2)

    assert isinstance(multiply_2_cached, Wrapper)

    assert multiply_2(2) == 4
    assert multiply_2_cached(2) == 4
    assert multiply_2_cached.misses == 1
    assert multiply_2(2, 3) == multiply_2_cached(2, 3)
    assert multiply_2_cached.misses == 2
    assert multiply_2(2, 3) == multiply_2_cached(2, 3)
    assert multiply_2_cached.hits == 1

    assert multiply_2(3, 4, [1, 1]) == 14
    assert multiply_2_cached(3, 4, [1, 1]) == 14
    assert multiply_2_cached(3, 3, [1, 1]) == 11
    assert multiply_2_cached.misses == 4
    assert multiply_2_cached(3, 4, [1, 1]) == 14
    assert multiply_2_cached.hits == 2

    # Should only cache when y=3
    multiply_2_cached_y3 = Cache("x", "z", y=3)(multiply_2)

    assert multiply_2_cached_y3(1, 1, [1, 1]) == 3
    assert multiply_2_cached_y3.misses == 1

    assert multiply_2_cached_y3(1, 1, [1, 1]) == 3
    assert multiply_2_cached_y3.misses == 2

    assert multiply_2_cached_y3(1, 3, [4, 1]) == 8
    assert multiply_2_cached_y3.misses == 3
    assert multiply_2_cached_y3(1, 3, [4, 1]) == 8
    assert multiply_2_cached_y3.hits == 1


def test_build_key() -> None:
    def multiply_2(x: int, y: int = 2, z: list[int] = []) -> int:
        return x * y + sum(z)

    multiply_2_cached = Cache("x", "y", "z")(multiply_2)

    key = multiply_2_cached.cache.build_key(multiply_2, 1, 2, [3, 4])
    print(f"KEY: {key}")

    assert key == "~1~2~[3, 4]~"

    multiply_2_cached_y4 = Cache("x", "z", y=4)(multiply_2)

    # Key should be None since y != 4
    key = multiply_2_cached_y4.cache.build_key(multiply_2, 1, 2, [3, 4])
    print(f"Expecting None KEY: {key}")
    assert key is None

    # Now we expect a real key since y is 4
    key = multiply_2_cached_y4.cache.build_key(multiply_2, 1, 4, [3, 4])
    print(f"KEY: {key}")
    assert key == "~y=(4)~1~[3, 4]~"
