import asyncio
from telethon.sync import TelegramClient

# Ensure there is an event loop for Telethon sync helpers
asyncio.set_event_loop(asyncio.new_event_loop())

api_id =23590539
api_hash = 'aceaebdb6d7c479461028195320a9906'
phone = '+84344712604'
client = TelegramClient(phone, api_id, api_hash)
