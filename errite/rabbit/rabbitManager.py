
import aio_pika
from aio_pika.abc import AbstractConnection
from aio_pika.pool import Pool


def build_url(jsonData):
    """Build Auth URL

    Args:
        amqp_user (str): User name
        amqp_pass (str): Password
        virtual_host (str): Virtual Host

    Returns:
        str: AMQP URL
    """
    return ''.join(['amqp://',
                    jsonData["Username"], ':', jsonData["Password"],
                    '@', jsonData["Hostname"], '/'])


async def getRabbitConnection(rabbitJsonData) -> AbstractConnection:
    testUrl = build_url(rabbitJsonData)
    return await aio_pika.connect_robust(build_url(rabbitJsonData))

async def getRabbitChannels(givenChannelPool: Pool) -> aio_pika.Channel:
    async with givenChannelPool.acquire() as connection:
        return await connection.channel()



async def publishMessage(givenChannelPool: Pool, message:str, givenQueue:str):
    async with givenChannelPool.acquire() as channel:

        await channel.default_exchange.publish(
            aio_pika.Message(body=(message).encode(), delivery_mode=aio_pika.abc.DeliveryMode.PERSISTENT), givenQueue
        )


