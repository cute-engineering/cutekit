from typing import Any, TypeVar, cast, Optional, Union
import json
import hashlib

T = TypeVar('T')


def uniq(l: list[str]) -> list[str]:
    result: list[str] = []
    for i in l:
        if i in result:
            result.remove(i)
        result.append(i)
    return result


def hash(obj: Any, keys: list[str] = [], cls: Optional[type[json.JSONEncoder]] = None) -> str:
    toHash = {}
    if len(keys) == 0:
        toHash = obj
    else:
        for key in keys:
            if key in obj:
                toHash[key] = obj[key]
    data = json.dumps(toHash, sort_keys=True, cls=cls)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def camelCase(s: str) -> str:
    s = ''.join(x for x in s.title() if x != '_' and x != '-')
    s = s[0].lower() + s[1:]
    return s


def key(obj: Any, keys: list[str] = []) -> str:
    k: list[str] = []

    if len(keys) == 0:
        keys = list(obj.keys())
        keys.sort()

    for key in keys:
        if key in obj:
            if isinstance(obj[key], bool):
                if obj[key]:
                    k.append(key)
            else:
                k.append(f"{camelCase(key)}({obj[key]})")

    return "-".join(k)


def asList(i: Optional[Union[T, list[T]]]) -> list[T]:
    if i is None:
        return []
    if isinstance(i, list):
        return cast(list[T], i)
    return [i]
