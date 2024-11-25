import json
from typing import Optional
import datetime

import aio_pika
from aio_pika.pool import Pool


class JournalNotification:
    def __init__(self, channelid:float, artist:str, pp_url:str, title:str, url:str, tstr:datetime, mature_journal:bool,
                 thumb_url:str):
        self.channelid:float = channelid
        self.artist:str = artist
        self.pp_url = pp_url
        self.title:str = title
        self.url:str = url
        self.tstr:datetime = tstr
        self.mature_journal:bool = mature_journal

    def serializeData(self) -> dict:
        data:list = {}
        data["notification_type"] = "journal"
        data["artist"] = self.artist
        data["channelid"] = self.channelid
        data["pp_url"] = self.pp_url
        data["title"] = self.title
        data["url"] = self.url
        data["tstr"] = self.tstr
        data["mature_journal"] = self.mature_journal

        return data

    async def sendNotification(self, givenChannelPool: Pool, givenQueue:str):
        async with givenChannelPool.acquire() as channel:


            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(self.serializeData()), delivery_mode=aio_pika.abc.DeliveryMode.PERSISTENT), givenQueue
            )

    async def sendNotification(self, givenChannelPool: Pool):
        async with givenChannelPool.acquire() as channel:


            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(self.serializeData()), delivery_mode=aio_pika.abc.DeliveryMode.PERSISTENT), "journal_notifications"
            )
