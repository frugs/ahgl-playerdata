import asyncio
from typing import List, TypeVar, Coroutine, Iterable, Callable

Input = TypeVar('Input')
Output = TypeVar('Output')


async def async_map(
        func: Callable[[Input], Coroutine[None, None, Output]],
        iterable: Iterable[Input],
) -> List[Output]:
    fs = await asyncio.wait([
        asyncio.ensure_future(func(x))
        for x
        in iterable])
    return [await future for future in fs[0]]
