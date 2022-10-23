from copy import copy
import errno
import os
import hashlib
import signal
import requests
import subprocess
import json
import copy
import re


class Colors:
    BLACK = "\033[0;30m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    BROWN = "\033[0;33m"
    BLUE = "\033[0;34m"
    PURPLE = "\033[0;35m"
    CYAN = "\033[0;36m"
    LIGHT_GRAY = "\033[0;37m"
    DARK_GRAY = "\033[1;30m"
    LIGHT_RED = "\033[1;31m"
    LIGHT_GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    LIGHT_BLUE = "\033[1;34m"
    LIGHT_PURPLE = "\033[1;35m"
    LIGHT_CYAN = "\033[1;36m"
    LIGHT_WHITE = "\033[1;37m"
    BOLD = "\033[1m"
    FAINT = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    NEGATIVE = "\033[7m"
    CROSSED = "\033[9m"
    RESET = "\033[0m"


class CliException(Exception):
    def __init__(self, msg: str):
        self.msg = msg


def stripDups(l: list[str]) -> list[str]:
    # Remove duplicates from a list
    # by keeping only the last occurence
    result: list[str] = []
    for item in l:
        if item in result:
            result.remove(item)
        result.append(item)
    return result


def findFiles(dir: str, exts: list[str] = []) -> list[str]:
    if not os.path.isdir(dir):
        return []

    result: list[str] = []

    for f in os.listdir(dir):
        if len(exts) == 0:
            result.append(f)
        else:
            for ext in exts:
                if f.endswith(ext):
                    result.append(os.path.join(dir, f))
                    break

    return result


def hashFile(filename: str) -> str:
    with open(filename, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def objSha256(obj: dict, keys: list[str] = []) -> str:
    toHash = {}

    if len(keys) == 0:
        toHash = obj
    else:
        for key in keys:
            if key in obj:
                toHash[key] = obj[key]

    data = json.dumps(toHash, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def toCamelCase(s: str) -> str:
    s = ''.join(x for x in s.title() if x != '_' and x != '-')
    s = s[0].lower() + s[1:]
    return s


def objKey(obj: dict, keys: list[str] = []) -> str:
    toKey = []

    if len(keys) == 0:
        keys = list(obj.keys())
        keys.sort()

    for key in keys:
        if key in obj:
            if isinstance(obj[key], bool):
                if obj[key]:
                    toKey.append(key)
            else:
                toKey.append(f"{toCamelCase(key)}({obj[key]})")

    return "-".join(toKey)


def mkdirP(path: str) -> str:
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
    return path


def downloadFile(url: str) -> str:
    dest = ".osdk/cache/" + hashlib.sha256(url.encode('utf-8')).hexdigest()
    tmp = dest + ".tmp"

    if os.path.isfile(dest):
        return dest

    print(f"Downloading {url} to {dest}")

    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        mkdirP(os.path.dirname(dest))
        with open(tmp, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        os.rename(tmp, dest)
        return dest
    except requests.exceptions.RequestException as e:
        raise CliException(f"Failed to download {url}: {e}")


def runCmd(*args: str) -> bool:
    try:
        proc = subprocess.run(args)
    except FileNotFoundError:
        raise CliException(f"Failed to run {args[0]}: command not found")
    except KeyboardInterrupt:
        raise CliException("Interrupted")

    if proc.returncode == -signal.SIGSEGV:
        raise CliException("Segmentation fault")

    if proc.returncode != 0:
        raise CliException(
            f"Failed to run {' '.join(args)}: process exited with code {proc.returncode}")

    return True


def getCmdOutput(*args: str) -> str:
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE)
    except FileNotFoundError:
        raise CliException(f"Failed to run {args[0]}: command not found")

    if proc.returncode == -signal.SIGSEGV:
        raise CliException("Segmentation fault")

    if proc.returncode != 0:
        raise CliException(
            f"Failed to run {' '.join(args)}: process exited with code {proc.returncode}")

    return proc.stdout.decode('utf-8')

def sanitizedUname():
    un = os.uname()
    if un.machine == "aarch64":
        un.machine = "arm64"
    return un

def findLatest(command) -> str:
    """
    Find the latest version of a command

    Exemples
    clang -> clang-15
    clang++ -> clang++-15
    gcc -> gcc10
    """
    print("Searching for latest version of " + command)

    regex = re.compile(r"^" + re.escape(command) + r"(-.[0-9]+)?$")

    versions = []
    for path in os.environ["PATH"].split(os.pathsep):
        if os.path.isdir(path):
            for f in os.listdir(path):
                if regex.match(f):
                    versions.append(f)
    
    if len(versions) == 0:
        raise CliException(f"Failed to find {command}")

    versions.sort()
    chosen = versions[-1]

    print(f"Using {chosen} as {command}")
    return chosen


CACHE = {}

MACROS = {
    "uname": lambda what: getattr(sanitizedUname(), what).lower(),
    "include": lambda *path: loadJson(''.join(path)),
    "join": lambda lhs, rhs: {**lhs, **rhs} if isinstance(lhs, dict) else lhs + rhs,
    "concat": lambda *args: ''.join(args),
    "exec": lambda *args: getCmdOutput(*args).splitlines(),
    "latest": findLatest,
}


def isJexpr(jexpr: list) -> bool:
    return isinstance(jexpr, list) and len(jexpr) > 0 and isinstance(jexpr[0], str) and jexpr[0].startswith("@")


def jsonEval(jexpr: list) -> any:
    macro = jexpr[0][1:]
    if not macro in MACROS:
        raise CliException(f"Unknown macro {macro}")
    return MACROS[macro](*list(map((lambda x: jsonWalk(x)), jexpr[1:])))


def jsonWalk(e: any) -> any:
    if isinstance(e, dict):
        for k in e:
            e[jsonWalk(k)] = jsonWalk(e[k])
    elif isJexpr(e):
        return jsonEval(e)
    elif isinstance(e, list):
        for i in range(len(e)):
            e[i] = jsonWalk(e[i])

    return e


def loadJson(filename: str) -> dict:
    try:
        result = {}
        if filename in CACHE:
            result = CACHE[filename]
        else:
            with open(filename) as f:
                result = jsonWalk(json.load(f))
                result["dir"] = os.path.dirname(filename)
                result["json"] = filename
                CACHE[filename] = result

        result = copy.deepcopy(result)
        return result
    except Exception as e:
        raise CliException(f"Failed to load json {filename}: {e}")


def tryListDir(path: str) -> list[str]:
    try:
        return os.listdir(path)
    except FileNotFoundError:
        return []
