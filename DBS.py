import json
import time

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
from errite.psql.taskManager import syncListeners, addtask, addalltask
from errite.psql.sourceManager import updateSources, updateallfolders, addsource, verifySourceExistance, \
    verifySourceExistanceExtra, verifySourceExistanceAll, addallsource
from errite.psql.sqlManager import grab_sql
from errite.psql.journalManager import syncJournals, updateJournals, verifyListenerJournalExists, verifySourceJournalExists, \
    addjournallistener, addjournalsource
from errite.config.configManager import createConfig, createSensitiveConfig
from errite.tools.mis import fileExists
from errite.psql.artistCacheManager import sync_artists
import urllib

print("DeviantCord DBS V1.2.1")
print("Developed by Errite Games LLC")
clientid = None
db_connection = None
connection_info = None
database_active = False
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
passedJson = False;
if fileExists("config.json") == False:
    createConfig()
if fileExists("client.json") == False:
    createSensitiveConfig()
    print("You need to set your login information!")
    deviantlogger.error("You need to set your login information!")
    deviantlogger.info("client.json created. You need to set your login information")
    passed = False

if passed == True:
    deviantlogger.info("Startup JSON Check passed")
    if fileExists("config.json") == True:
        if fileExists("client.json") == True:
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
                            release="deviant-dbs@1.2.1"
                        )
                    sensitiveData = json.load(clientjsonFile)
                    configjsonFile.close()
                    clientjsonFile.close()
                    if not sensitiveData["da-client-id"] == "id here":
                        if not sensitiveData["da-secret"] == "secret":
                            clientsecret = sensitiveData["da-secret"]
                            clientid = sensitiveData["da-client-id"]
                            passedJson = True
    if fileExists("db.json"):
        database_active = True
        with open("db.json", "r") as dbJson:
            dbInfo = json.load(dbJson)

if passedJson == True:
    deviantlogger.info("Setting config variables")
    # WEB API
    clientsecret = sensitiveData["da-secret"]
    clientid = sensitiveData["da-client-id"]
    token = dp.getToken(clientsecret, clientid)
    shard_type = configData["shard-type"]
    shard_id = configData["shard-id"]
    print("Using shardtype " + shard_type)
    # Database Specific Options
    deviantlogger.info("Setting Database Variables")
    database_name = dbInfo["database-name"]
    database_host = dbInfo["database-host"]
    database_host2 = dbInfo["database-host2"]
    database_host3 = dbInfo["database-host3"]
    database_password = dbInfo["database-password"]
    database_user = dbInfo["database-username"]
    database_port = dbInfo["database-port"]
    stop_duplicaterecovery = False
    if database_host2 == "none":
        connect_str = "dbname='" + database_name + "' user='" + database_user \
                      + "'host='" + database_host + "' " + \
                      "'port='" + str(database_port) + "password='" + database_password + "'"
    elif database_host3 == "none":
        connect_str = "dbname='" + database_name + "' user='" + database_user \
                      + "'host='" + database_host + "," + database_host2 + "' " + \
                      "'port='" + str(database_port) + "password='" + database_password + "'"
    else:
        connect_str = "dbname='" + database_name + "' user='" + database_user \
                      + "'host='" + database_host + "," + database_host2 + "," + database_host3 + " " + \
                      "'port='" + str(database_port) + "'password='" + database_password + "'"
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
            source_cursor = db_connection.cursor()
            updateSources(source_cursor, db_connection, obt_results, token)
            db_connection.commit()
            get_query = "SELECT * from deviantcord.deviation_data_all WHERE NOT disabled = true AND shard_id = %s;"
            get_cursor.execute(get_query,(shard_id,))
            obt_results = get_cursor.fetchall()
            updateallfolders(source_cursor, db_connection, obt_results, token)
        elif shard_type.lower() == "listeners":
            source_cursor = db_connection.cursor()
            task_cursor = db_connection.cursor()
            syncListeners(db_connection, task_cursor, source_cursor, clientsecret, clientid, shard_id)
        elif shard_type.lower() == "journals":
            updateJournals(db_connection, token)
            syncJournals(db_connection)
        elif shard_type.lower() == "profiles":
            token = dp.getToken(clientsecret, clientid)
            sync_artists(db_connection,token, rpool)

        passes = passes + 1
        print("Now resting...")
        if shard_type.lower() == "profiles":
            time.sleep(43200)
        else:
            time.sleep(900)


