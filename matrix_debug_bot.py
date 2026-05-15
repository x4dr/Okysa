import os
import logging
import nio
import nio.responses
import simplematrixbotlib as botlib
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
for name in ["nio", "simplematrixbotlib", "DEBUG_BOT"]:
    logging.getLogger(name).setLevel(logging.DEBUG)
logger = logging.getLogger("DEBUG_BOT")

original_from_dict = nio.responses.SyncResponse.from_dict


def patched_from_dict(cls, parsed_dict, *args, **kwargs):
    try:
        if "rooms" in parsed_dict:
            for section in ["join", "leave"]:
                for room_id, room_dict in parsed_dict["rooms"].get(section, {}).items():
                    for key in ["state", "timeline", "ephemeral", "account_data"]:
                        if key not in room_dict:
                            room_dict[key] = {"events": []}
                        if key == "timeline":
                            if "limited" not in room_dict[key]:
                                room_dict[key]["limited"] = False
        return original_from_dict(parsed_dict, *args, **kwargs)
    except Exception as e:
        print(f"DEBUG_BOT: Error in sync parsing: {e}")
        return nio.responses.SyncResponse(
            next_batch=parsed_dict.get("next_batch", ""),
            rooms=nio.responses.Rooms({}, {}, {}),
            device_one_time_keys_count=nio.responses.DeviceOneTimeKeyCount(0, 0),
            device_lists=nio.responses.DeviceList([], []),
            to_device=nio.responses.ToDeviceResponse([]),
            presence_events=[],
            account_data=[],
        )


nio.responses.SyncResponse.from_dict = classmethod(patched_from_dict)

load_dotenv()


def main():
    creds = botlib.Creds(
        os.getenv("MATRIX_SERVER"), os.getenv("MATRIX_USER"), os.getenv("MATRIX_PASS")
    )
    bot = botlib.Bot(creds)

    @bot.listener.on_message_event
    async def echo(room, event):
        match = botlib.MessageMatch(room, event, bot)
        if match.is_not_from_this_bot():
            print("DEBUG_BOT: Sending echo...")
            await bot.api.send_text_message(room.room_id, f"Echo: {event.body}")

    @bot.listener.on_custom_event(nio.Event)
    async def on_any_event(room, event):
        print(f"DEBUG_BOT: [ANY_EVENT] type={type(event).__name__} room={room.room_id}")

    @bot.listener.on_startup
    async def startup(room):
        print(f"DEBUG_BOT: Online as {bot.creds.username}")
        joined = await bot.api.async_client.joined_rooms()
        print(f"DEBUG_BOT: Joined rooms: {joined.rooms}")
        for room_id in joined.rooms:
            print(f"DEBUG_BOT: Sending test to {room_id}")
            await bot.api.send_text_message(
                room_id, "Minimal Echo Bot with Debug Logging is now Online!"
            )

    print("DEBUG_BOT: Starting (Python 3.14) with DEBUG logging...")
    bot.run()


if __name__ == "__main__":
    main()
