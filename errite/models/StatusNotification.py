import datetime
import json

import aio_pika
from aio_pika.pool import Pool


class StatusNotification:
    def __init__(self, tstr:datetime, pp_url:str, url:str, body:str, artist:str,
                 itemUrl:str, channel_id:float):
        self.tstr = tstr
        self.pp_url = pp_url
        self.url = url
        self.body = body
        self.artist = artist
        self.itemUrl = itemUrl
        self.channel_id = channel_id


    def serializeData(self) -> dict:
        data:list = {}
        data["notification_type"] = "status"
        data["artist"] = self.artist
        data["channelid"] = self.channelid
        data["pp_url"] = self.pp_url
        data["body"] = self.body
        data["item_url"] = self.itemUrl
        data["url"] = self.url
        data["tstr"] = self.tstr

        return data


    async def sendNotification(self, givenChannelPool: Pool, givenQueue:str):
        async with givenChannelPool.acquire() as channel:


            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(self.serializeData()), delivery_mode=aio_pika.abc.DeliveryMode.PERSISTENT), givenQueue
            )

    async def sendNotification(self, givenChannelPool: Pool):
        async with givenChannelPool.acquire() as channel:


            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(self.serializeData()), delivery_mode=aio_pika.abc.DeliveryMode.PERSISTENT), "status_notifications"
            )