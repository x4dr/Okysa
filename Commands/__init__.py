def get_register_functions():
    from Commands.OracleCog import register

    yield register
    from Commands.Base import register

    yield register
    from Commands.MinecraftCog import register

    yield register
    from Commands.WikiCog import register

    yield register
    from Commands.RemindCog import register

    yield register
