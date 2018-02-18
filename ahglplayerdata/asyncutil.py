import asyncio
from typing import List, TypeVar, Coroutine, Iterable, Callable

I = TypeVar('I')
O = TypeVar('O')


async def async_map_ignore_failed(
        func: Callable[[I], Coroutine[None, None, O]], iterable: Iterable[I]) -> List[O]:
    fs = await asyncio.wait([
        asyncio.ensure_future(func(x))
        for x
        in iterable])
    return [await future for future in fs[0]]