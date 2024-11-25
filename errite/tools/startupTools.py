import logging

from errite.config.configManager import createConfig, createSensitiveConfig, createRabbitConfig
from errite.tools.mis import fileExists


def checkStartUpFiles():
    passed:bool = True
    deviantlogger = logging.getLogger("deviantcog")
    deviantlogger.setLevel(logging.INFO)
    if fileExists("config.json") == False:
        passed = False
        createConfig()
    if fileExists("client.json") == False:
        passed = False
        createSensitiveConfig()
        print("You need to set your login information!")
        deviantlogger.error("You need to set your login information!")
        deviantlogger.info("client.json created. You need to set your login information")
        passed = False
    if fileExists("rabbit.json") == False:
        passed = False
        createRabbitConfig()
    if fileExists("db.json") == False:
        passed = False

    return passed


