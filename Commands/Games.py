from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Type

from Golconda.Button import Button, ButtonFunc


hikari = None
Slash = None

# removed


@dataclass
class Player:
    mention: str
    id: int
    name: str
    cards: list
    wins: int


class Gamestate(Enum):
    JOINING = 0
    SETTING = 1
    BETTING = 2
    END = 3


class Game(ABC):
    games = {}
    _progress_button: ButtonFunc
    _game_button: ButtonFunc

    @classmethod
    def progress_button(cls, func):
        cls._progress_button = func
        return func

    @classmethod
    def game_button(cls, func):
        cls._game_button = func
        return func

    def player_search(self, by: str | int):
        for p in self.players:
            if by in [p.id, p.name, p.mention]:
                return p

        raise KeyError(by)

    def addplayer(self, p: hikari.User):
        self.players.append(Player(p.mention, p.id, p.username, [], 0))
        self.table[self.players[-1].id] = []

    def __init__(self, gameid: int):
        self.gameid = gameid
        self.players: list[Player] = []
        self.table: dict[int, list[int]] = {}

    @classmethod
    @abstractmethod
    def create(cls, gameid: int = None) -> "Game":
        ...

    @abstractmethod
    def statebuttons(self):
        ...

    @abstractmethod
    def renderstate(self):
        ...


class BlackJack(Game):
    def __init__(self, gameid: int):
        super().__init__(gameid)
        self.activeplayerid: int = 0
        self.gameid = gameid
        self.players: list[Player] = []

    @classmethod
    def create(cls, gameid: int = None) -> "BlackJack":
        if gameid is None:
            gameid = (max(cls.games) + 1) if cls.games else 0
            cls.games[gameid] = cls(
                gameid,
            )
        return cls.games[gameid]

    def statebuttons(self):
        pass

    def renderstate(self):
        pass


class Potion(Game):
    def __init__(
        self,
        gameid,
    ):
        super().__init__(gameid)
        self.currentbetter = None
        self.currentbet = 0
        self.activeplayerid: int = 0
        self.state: Gamestate = Gamestate.JOINING
        self.passedplayers = []

    @classmethod
    def create(cls, gameid: int = None) -> "Potion":
        if gameid is None:
            gameid = (max(cls.games) + 1) if cls.games else 0
            cls.games[gameid] = cls(
                gameid,
            )
        return cls.games[gameid]

    def tabledepth(self):
        return max(len(x) for x in self.table.values())

    def tableeven(self):
        return all(len(x) == self.tabledepth() for x in self.table.values())

    def setcard(self, card):
        p = self.activeplayerid
        if self.tableeven() or len(self.table[p]) < self.tabledepth():
            self.table[p].append(card)
        self.advanceactiveplayer()

    def statebuttons(self):
        row = hikari.impl.MessageActionRowBuilder()

        if self.state == Gamestate.JOINING:
            self._progress_button.add_to(row, "Join", "buyin")
            if len(self.players) > 1:
                self._progress_button.add_to(row, "Start Game", "start")
        elif self.state == Gamestate.SETTING:
            self._game_button.add_to(row, "Poison", "setpoison")
            self._game_button.add_to(row, "Safe", "setsafe")
            if self.tabledepth() > 0 and min(len(x) for x in self.table.values()):
                self._game_button.add_to(row, "Start Betting", "bet")
        elif self.state == Gamestate.BETTING:
            row = self._game_button.as_select_menu(
                "Bet Amount",
                [("Pass", "bet0")]  # passing = betting 0
                + [
                    (f"{x + 1}", f"bet{x + 1}")
                    for x in range(self.currentbet, self.tablesum())
                ],
            )
        elif self.state == Gamestate.END:
            self._game_button.add_to(row, "Done", "done")

        rows = [row]
        return rows

    def renderstate(self):
        emb = hikari.Embed(
            title="Potion",
            color=0x05F012,
        )
        emb.set_footer(f"gameid:{self.gameid}")
        if self.state == Gamestate.JOINING:
            emb.description = (
                "This is a game of Potions of Power.\n"
                "The Goal is to pile up potion ingredients together, and to brew it and drink it to win!\n"
                "However ... you can also poison the potion to weaken whoever drinks it instead.\n"
                "\n"
                "The brewing process will involve betting on how many ingredients can be used. Whoever wins the bet,"
                "will grab ingredients from the top of their own pile, then of the tops of other players piles and"
                "throw them in the pot and drink.\n"
                "New players can still join the ritual of power. Whoever drinks a pure potion twice, wins."
            )
        elif self.state == Gamestate.SETTING:
            emb.description = (
                "Time to place ingredients!\n"
                "You start the game with 3 Safe Ingredients and 1 Poison Cards and lose 1 random card, everytime "
                "you drink poison. (You will know which, when you try to place that ingredient and nothing happens)\n"
                f"Currently the active player is {self.activeplayer.mention}.\n"
            )
        elif self.state == Gamestate.BETTING:
            if self.currentbetter:
                curbet = self.player_search(self.currentbetter)
                curbet_message = f" by {curbet.mention}"
            else:
                curbet_message = ""
            still_in = ", ".join(
                [x.mention for x in self.players if x.id not in self.passedplayers]
            )
            emb.description = (
                f"Current bet is {self.currentbet}{curbet_message}.\n"
                f"players still betting are: {still_in}\n"
                f"Currently the active player is {self.activeplayer.mention}.\n"
            )
        elif self.state == Gamestate.END:
            pass

        for p in self.players:
            hasset = (not self.tableeven()) and len(
                self.table[p.id]
            ) == self.tabledepth()
            emb.add_field(
                p.name,
                f"Ingredients: {sum(p.cards)}\nWins: {p.wins}\nhas set an ingredient: {'yes' if hasset else 'no'}",
                inline=True,
            )

        return emb

    def tablesum(self):
        return sum(len(x) for x in self.table.values())

    @property
    def activeplayer(self):
        return self.player_search(self.activeplayerid)

    def advanceactiveplayer(self):
        ids = [x.id for x in self.players]
        pos = ids.index(self.activeplayerid)
        ids = ids[pos:] + ids[:pos]  # rotate

        candidates = [pid for pid in ids if ids not in self.passedplayers]
        if candidates[0] == self.activeplayerid:
            candidates = candidates[1:]

        self.activeplayerid = candidates[0]

        if all(x == self.activeplayerid for x in candidates):
            # if the active player is the only candidate or there are no candidates
            self.state += 1
            return

    def setbet(self, bet: int):
        if bet == 0:
            self.passedplayers.append(self.activeplayerid)
            self.advanceactiveplayer()
            return
        if bet > self.currentbet:
            self.currentbet = bet
            self.currentbetter = self.activeplayerid
            self.advanceactiveplayer()


def register(slash: Type[Slash]):
    @slash.cmd("games", "set up game")
    async def games_menu(cmd: Slash):
        cmd.get("none")
        ...

    @slash.sub("blackjack", "set up a game of blackjack", of="games_menu")
    async def blackjack_setup(cmd: Slash):
        g = BlackJack.create()
        await cmd.respond_instant(
            "", embed=g.renderstate(), components=g.statebuttons()
        )

    @slash.sub("potion", "set up a game of potion", of="games_menu")
    async def potion_setup(cmd: Slash):
        g = Potion.create()
        await cmd.respond_instant(
            "", embed=g.renderstate(), components=g.statebuttons()
        )

    @Potion.progress_button
    @Button
    async def potion_progress(press: hikari.ComponentInteraction, param):
        msg = press.message
        emb = msg.embeds[0]
        game: Potion = Potion.create(int(emb.footer.text[7:]))
        if param == "buyin":

            if game.state == Gamestate.JOINING:
                if press.user.mention not in game.players:
                    game.addplayer(press.user)
        if param == "start" and press.user == msg.interaction.user:
            if game.state != Gamestate.JOINING:
                return
            game.activeplayerid = press.user.id
            game.state = Gamestate.SETTING
        await msg.edit(embed=game.renderstate(), components=game.statebuttons())

    @Potion.game_button
    @Button
    async def potion_game(press: hikari.ComponentInteraction, param):
        msg = press.message
        emb = msg.embeds[0]
        game: Potion = Potion.create(int(emb.footer.text[7:]))
        if param == "setsafe":
            if game.activeplayerid == press.user.id:
                game.setcard(0)
        elif param == "setpoison":
            if game.activeplayerid == press.user.id:
                game.setcard(1)
        elif param == "bet":
            game.state = Gamestate.BETTING
            game.currentbet = 0
            game.passedplayers = []
        elif param.startswith("bet"):
            if press.user.id != game.activeplayerid:
                return await press.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE, "not your turn"
                )
            bet = int(param[3:])
            game.setbet(bet)
        await msg.edit(embed=game.renderstate(), components=game.statebuttons())
