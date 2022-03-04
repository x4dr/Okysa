import hikari
from hikari.api import RESTClient


def slashies(rest: RESTClient):
    c = rest.slash_command_builder("anon", "say something ... anonymously :D")
    option1 = hikari.CommandOption(type=3, name="say", description="what you want to say", is_required=True)
    c.add_option(option1)
    return [c]
