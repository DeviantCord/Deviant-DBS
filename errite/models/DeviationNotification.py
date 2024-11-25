import datetime
import json

import aio_pika
from aio_pika.pool import Pool


class DeviationNotification:
    def __init__(self, type:str, channelid:float, artist:str, folder:str, devi_url:str, devi_img_url:str,
                 pp_url:str, inverse:bool, ts:datetime, mature_devi:bool, isGroupDevi:bool):
        self.type:str = type
        self.channelid:float = channelid
        self.artist:str = artist
        self.folder:str = folder
        self.devi_url:str = devi_url
        self.devi_img_url:str = devi_img_url
        self.pp_url:str = pp_url
        self.inverse:bool = inverse
        self.ts:datetime = ts
        self.mature_devi:bool = mature_devi
        self.isGroupDevi:bool = isGroupDevi

    def serializeData(self) -> dict:
        data = {}
        data["notification_type"] = "deviation"
        data["type"] = self.type
        data["channelid"] = self.channelid
        data["artist"] = self.artist
        data["folder"] = self.folder
        data["devi_url"] = self.devi_url
        data["devi_img_url"] = self.devi_img_url
        data["pp_url"] = self.pp_url
        data["inverse"] = self.inverse
        data["ts"] = self.ts
        data["mature_devi"] = self.mature_devi
        data["isGroupDevi"] = self.isGroupDevi
        return data

    async def sendNotification(self, givenChannelPool: Pool, givenQueue: str = "deviantcord_prod"):
        async with givenChannelPool.acquire() as channel:
            message_body = json.dumps(self.serializeData()).encode('utf-8')
            
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=message_body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=givenQueue
            )


