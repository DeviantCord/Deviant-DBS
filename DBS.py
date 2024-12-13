import asyncio
import json
import time

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from aio_pika.pool import Pool
from pythonjsonlogger import jsonlogger
from logging.handlers import TimedRotatingFileHandler
import datetime
import logging
import redis
from sentry_sdk import configure_scope, set_context, set_extra, capture_exception
import sentry_sdk
import psycopg2
import time
import psycopg2.errors


import errite.da.daParser as dp
from errite.deviantcord.timeTools import prefixTimeOutSatisfied
from errite.psql.artistCacheManager import sync_artists
from errite.psql.taskManager import syncListeners, addtask, addalltask
from errite.psql.sourceManager import updateSources, updateallfolders, addsource, verifySourceExistance, \
    verifySourceExistanceExtra, verifySourceExistanceAll, addallsource
from errite.psql.sqlManager import grab_sql
from errite.psql.journalManager import syncJournals, updateJournals, verifyListenerJournalExists, verifySourceJournalExists, \
    addjournallistener, addjournalsource
from errite.config.configManager import createConfig, createSensitiveConfig, createRabbitConfig
from errite.tools.mis import fileExists
from errite.rabbit.rabbitManager import build_url
from errite.tools.startupTools import checkStartUpFiles
import urllib

print("DeviantCord DBS V2.0.5")
print("Developed by Errite Softworks LLC")
clientid = None
db_connection = None
connection_info = None
database_active = False
rabbitJson = None
rabbitUrl = None
dbInfo = None
database_name = None
database_host = None
database_user = None
database_password = None
database_port = None
clientsecret = None
guildid = None
enablesr = False
jsonlock = False
min_roles = {}
min_roles["guilds"] = []
roleid = 0
failedlogincount = 0
publicmode = None
datevar = datetime.datetime.now().strftime("%Y-%m-%d%H%M%S")
whiletrigger = False
logname = "deviantcog"

deviantlogger = logging.getLogger("deviantcog")
deviantlogger.setLevel(logging.INFO)
dlhandler = TimedRotatingFileHandler(logname, when='h', interval=12, backupCount=2000,
                                          encoding='utf-8')
supported_keys = [
    'asctime',
    'created',
    'filename',
    'funcName',
    'levelname',
    'levelno',
    'lineno',
    'module',
    'message',
    'process',
    'processName',
    'relativeCreated',
    'thread',
    'threadName'
]

log_format = lambda x: ['%({0:s})'.format(i) for i in x]
custom_format = ' '.join(log_format(supported_keys))
formatter = jsonlogger.JsonFormatter(custom_format)
dlhandler.setFormatter(formatter)
deviantlogger.addHandler(dlhandler)

token = None
prefix = "$"
passed = True

async def main():
    passedJson = checkStartUpFiles()
    passed = passedJson


    if passed == True:
        deviantlogger.info("Startup JSON Check passed")
        with open("config.json", "r") as configjsonFile:
            with open("client.json", "r") as clientjsonFile:
                configData = json.load(configjsonFile)
                use_sentry = configData["sentry-enabled"]
                if use_sentry:
                    sentry_url = configData["sentry-url"]
                    sentry_sdk.init(
                        sentry_url,

                        # Set traces_sample_rate to 1.0 to capture 100%
                        # of transactions for performance monitoring.
                        # We recommend adjusting this value in production.
                        traces_sample_rate=1.0,
                        # Set profiles_sample_rate to 1.0 to profile 100%
                        # of sampled transactions.
                        # We recommend adjusting this value in production.
                        profiles_sample_rate=1.0,
                        ignore_errors = [KeyboardInterrupt],
                        release="deviant-dbs@2.0.4"
                    )
                sensitiveData = json.load(clientjsonFile)
                configjsonFile.close()
                clientjsonFile.close()
                if not sensitiveData["da-client-id"] == "id here":
                    if not sensitiveData["da-secret"] == "secret":
                        clientsecret = sensitiveData["da-secret"]
                        clientid = sensitiveData["da-client-id"]
                        passedJson = True
        with open("db.json", "r") as dbJson:
            dbInfo = json.load(dbJson)
        with open("rabbit.json", "r") as rabbitConfig:
            rabbitJson = json.load(rabbitConfig)

    if passedJson == True:
        deviantlogger.info("Setting config variables")
        loop = asyncio.get_event_loop()
        # WEB API
        clientsecret = sensitiveData["da-secret"]
        clientid = sensitiveData["da-client-id"]
        token = dp.getToken(clientsecret, clientid)
        shard_type = configData["shard-type"]
        shard_id = configData["shard-id"]
        print("Using shardtype " + shard_type)
        # Database Specific Options
        rabbitUrl = f"amqp://{rabbitJson['username']}:{rabbitJson['password']}@{rabbitJson['host']}:{rabbitJson['port']}/{rabbitJson['vhost']}"


        deviantlogger.info("Setting Database Variables")
        database_name = dbInfo["database-name"]
        database_host = dbInfo["database-host"]
        database_password = dbInfo["database-password"]
        database_user = dbInfo["database-username"]
        database_port = dbInfo["database-port"]
        stop_duplicaterecovery = False
        connect_str = "postgresql://" + database_user + ":" + database_password + "@" + \
                      database_host + ":" + \
                      str(database_port) + "/" + database_name
        print("Connecting to database")
        db_connection = psycopg2.connect(connect_str)
        with open("redis.json", "r") as redisJson:
            redisData = json.load(redisJson)
            redisStr = redisData["url"]
            redisPassword = redisData["password"]
            print("Connecting to redis ")
            rpool = redis.ConnectionPool.from_url(url=redisStr, password=redisPassword, db=0)
            print("Connected to redis!")
            redisJson.close()
        async def get_rabbit_connection() -> AbstractRobustConnection:
            return await aio_pika.connect_robust(rabbitUrl)

        connection_pool: Pool = Pool(get_rabbit_connection, max_size=10, loop=loop)


        async def get_rabbit_channel() -> aio_pika.Channel:
            async with connection_pool.acquire() as connection:
                return await connection.channel()

        channel_pool: Pool = Pool(get_rabbit_channel, max_size=10, loop=loop)

        noError = True
        passes = 0
        while noError:
            if not shard_type.lower() == "profiles":
                if passes == 2:
                    token = dp.getToken(clientsecret, clientid)
                    passes = 0
            if shard_type.lower() == "sources":
                get_cursor = db_connection.cursor()
                get_query = "select * from deviantcord.deviation_data WHERE NOT disabled = true AND shard_id = %s;"
                get_cursor.execute(get_query,(shard_id,))
                obt_results = get_cursor.fetchall()
                updateSources(db_connection, obt_results, token)
                db_connection.commit()
                get_query = "SELECT * from deviantcord.deviation_data_all WHERE NOT disabled = true AND shard_id = %s;"
                get_cursor.execute(get_query,(shard_id,))
                obt_results = get_cursor.fetchall()
                updateallfolders(db_connection, obt_results, token)
            elif shard_type.lower() == "listeners":
                await syncListeners(db_connection, clientsecret, clientid, shard_id, channel_pool)
            elif shard_type.lower() == "journals":
                updateJournals(db_connection, token)
                syncJournals(db_connection, channel_pool)
            elif shard_type.lower() == "profiles":
                token = dp.getToken(clientsecret, clientid)
                sync_artists(db_connection,token, rpool)
            passes = passes + 1
            print("Now resting...")
            if shard_type.lower() == "profiles":
                time.sleep(43200)
            else:
                time.sleep(900)

if __name__ == "__main__":
    asyncio.run(main())

