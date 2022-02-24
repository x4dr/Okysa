paths = {}


def default(func=None):
    if func is None:
        return paths.default
    paths.default = func
    return func


def command(cmd, prefix=None):
    if prefix is None:
        return paths.get(cmd, default())
    paths[prefix] = cmd
    return cmd
