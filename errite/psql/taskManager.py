"""

    Deviant-DBS
    Copyright (C) 2020-2024  Errite Softworks LLC/ ErriteEpticRikez

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""
import os
import json
import logging
import urllib.error

import psycopg2
import psycopg2.extras
import datetime

from errite.psql.sqlManager import grab_sql
from errite.da.datools import localDetermineNewDeviation
from errite.da.catchup import idlistHasId, ifAllNewDeviations, ifAllNewDeviationsListOnly
import errite.da.daParser as dp
from twilio.rest import Client
from sentry_sdk import capture_exception
from errite.models.DeviationNotification import DeviationNotification
from errite.models.JournalNotification import JournalNotification
from errite.models.StatusNotification import StatusNotification
from errite.tools.mis import findFileName
from aio_pika.pool import Pool
from errite.io.failedTask import getFailedTaskJsonFiles

def get_image_url_pe(entry):
    try:
        check_var = entry["excerpt"]
        return "IGNORETHISDEVIATION"
    except KeyError:
        pass
    try:
        return entry["content"]["src"]
    except KeyError:
        pass
        
    try:
        return entry["flash"]["src"] + " DEVIANTCORDENDINGUSENONPREVIEW"
    except KeyError:
        pass
    
    try:
        return entry["videos"][0]["src"] + "DEVIANTCORDENDINGUSENONPREVIEW"
    except KeyError:
        pass
    
    try:
        return entry["thumbs"]["src"]
    except KeyError:
        pass
    
    return "IGNORETHISDEVIATION"

def get_image_url(entry):
    try:
        return entry["content"]["src"]
    except KeyError:
        print("Trying other formats")
        
    try:
        return entry["flash"]["src"] + " DEVIANTCORDENDINGUSENONPREVIEW"
    except KeyError:
        pass
    
    try:
        return entry["videos"][0]["src"] + "DEVIANTCORDENDINGUSENONPREVIEW"
    except KeyError:
        pass
    
    try:
        return entry["thumbs"]["src"]
    except KeyError:
        pass
    
    return "IGNORETHISDEVIATION"

async def handle_nf_deviation_notifications(discord_commits, normal_commits, hybrid_commits, hybrid_only_commits, givenPool, db_conn):
    change_sql = """ UPDATE deviantcord.deviation_listeners
                    SET dc_uuid = data.dcuuid, last_update = data.last_update, 
                last_ids = data.last_ids::text[] FROM (VALUES %s) AS data(dcuuid, last_update, last_ids, artist, folderid, serverid, channelid)
                    WHERE deviantcord.deviation_listeners.artist = data.artist AND deviantcord.deviation_listeners.folderid = data.folderid
                    AND deviantcord.deviation_listeners.serverid = data.serverid AND deviantcord.deviation_listeners.channelid = data.channelid"""
    change_hybrid_sql = """ UPDATE deviantcord.deviation_listeners
                         SET dc_uuid = data.dcuuid, last_update = data.last_update, 
                        last_ids = data.last_ids::text[], last_hybrids = data.last_hybrids::text[] 
                        FROM (VALUES %s) AS data(dcuuid, last_update, last_ids, last_hybrids, artist, folderid, serverid,
                        channelid)
                         WHERE deviantcord.deviation_listeners.artist = data.artist AND deviantcord.deviation_listeners.folderid = data.folderid
                         AND deviantcord.deviation_listeners.serverid = data.serverid AND deviantcord.deviation_listeners.channelid = data.channelid"""
    change_hybrid_only_sql = """ UPDATE deviantcord.deviation_listeners
                             SET dc_uuid = data.dcuuid, last_update = data.last_update, last_hybrids = data.last_hybrids::text[] 
                            FROM (VALUES %s) AS data(dcuuid, last_update, last_hybrids, artist, folderid, serverid, channelid)
                             WHERE deviantcord.deviation_listeners.artist = data.artist AND deviantcord.deviation_listeners.folderid = data.folderid
                             AND deviantcord.deviation_listeners.serverid = data.serverid AND deviantcord.deviation_listeners.channelid = data.channelid"""
    deviantlogger = logging.getLogger("deviantcog")
    deviantlogger.info("Normal Commits: " + str(len(normal_commits)))
    deviantlogger.info("Discord Commits: " + str(len(discord_commits)))
    deviantlogger.info("Hybrid Commits " + str(len(hybrid_commits)))
    deviantlogger.info("Hybrid Only Commits " + str(len(hybrid_only_commits)))
    
    failed_notifications = []
    temp_cursor = db_conn.cursor()
    discord_batch = []
    
    try:
        if temp_cursor.statusmessage:
            temp_cursor.close()
            db_conn.commit()
            temp_cursor = db_conn.cursor()
        # Process normal commits when they reach batch size
        if len(normal_commits) >= 5:
            psycopg2.extras.execute_values(temp_cursor, change_sql, normal_commits)
            db_conn.commit()
            normal_commits = []

        # Process hybrid commits when they reach batch size
        if len(hybrid_commits) >= 5:
            psycopg2.extras.execute_values(temp_cursor, change_hybrid_sql, hybrid_commits)
            db_conn.commit()
            hybrid_commits = []

        # Process hybrid only commits when they reach batch size
        if len(hybrid_only_commits) >= 5:
            psycopg2.extras.execute_values(temp_cursor, change_hybrid_only_sql, hybrid_only_commits)
            db_conn.commit()
            hybrid_only_commits = []

        # Process any remaining commits
        if normal_commits:
            psycopg2.extras.execute_values(temp_cursor, change_sql, normal_commits)
        if hybrid_commits:
            psycopg2.extras.execute_values(temp_cursor, change_hybrid_sql, hybrid_commits)
        if hybrid_only_commits:
            psycopg2.extras.execute_values(temp_cursor, change_hybrid_only_sql, hybrid_only_commits)

        # Process discord notifications in batches
        for notification in discord_commits:
            discord_batch.append(notification)
            if len(discord_batch) >= 5:
                for batch_notification in discord_batch:
                    try:
                        await batch_notification.sendNotification(givenPool)
                    except (ConnectionError, Exception) as ex:
                        failed_notifications.append(batch_notification)
                        if isinstance(ex, Exception):
                            capture_exception(ex)
                discord_batch = []

        # Process any remaining discord notifications
        for notification in discord_batch:
            try:
                await notification.sendNotification(givenPool)
            except (ConnectionError, Exception) as ex:
                failed_notifications.append(notification)
                if isinstance(ex, Exception):
                    capture_exception(ex)

        if failed_notifications:
            with open(findFileName("notification-failover"), "w+") as failedNotificationFile:
                failedNotificationFile.write(json.dumps(failed_notifications))

        # Final commit for any remaining transactions
        db_conn.commit()

    except Exception as e:
        db_conn.rollback()
        deviantlogger.exception(e)
        capture_exception(e)
        raise
    finally:
        if not temp_cursor.closed:
            temp_cursor.close()

    deviantlogger.info("All transactions committed successfully")

def create_nf_deviation_notifications(new_deviation_count, new_hybrid_count, artist, foldername, mature, isGroup, folderid, serverid, channel_id, obt_dcuuid, obt_last_urls, obt_img_urls, obt_pp, inverse, discord_commits, obt_hybrid_urls, obt_hybrid_img_urls, obt_hybrid_ids):
    # Create notifications for new deviations. This method does not create notifications as a result of a catchup event. 
    deviantlogger = logging.getLogger("deviantcog")

    if not new_deviation_count == 0:
        if inverse:
            temp_index = 0
            while not temp_index == new_deviation_count:
                dump_tstr = str(datetime.datetime.now())
                entry:DeviationNotification = DeviationNotification(
                    "deviation", channel_id, artist, foldername, obt_last_urls[temp_index],
                obt_img_urls[temp_index], obt_pp,inverse, dump_tstr, mature, isGroup)
                discord_commits.append(entry)
                temp_index = temp_index + 1
        
        if not inverse:
            temp_index = (len(obt_last_urls) - new_deviation_count) - 1
            while not temp_index == (len(obt_last_urls) - 1):
                dump_tstr = str(datetime.datetime.now())
                entry:DeviationNotification = DeviationNotification(
                    "deviation", channel_id, artist, foldername, obt_last_urls[temp_index],
                    obt_img_urls[temp_index], obt_pp,inverse, dump_tstr, mature, isGroup)
                discord_commits.append(entry)
                temp_index = temp_index + 1
    if not new_hybrid_count == 0:
        if inverse:
            temp_index = 0
            while not temp_index == new_hybrid_count:
                dump_tstr = str(datetime.datetime.now())
                entry:DeviationNotification = DeviationNotification("deviation", channel_id, artist, foldername, obt_hybrid_urls[temp_index],
                     obt_hybrid_img_urls[temp_index], obt_pp, inverse, dump_tstr, mature, isGroup)
                discord_commits.append(entry)
                temp_index = temp_index + 1
        
        if not inverse:
            temp_index = (len(obt_hybrid_ids) - new_hybrid_count) - 1
            while not temp_index == (len(obt_hybrid_ids) - 1):
                dump_tstr = str(datetime.datetime.now())
                entry:DeviationNotification = DeviationNotification("deviation", channel_id, artist, foldername, obt_hybrid_urls[temp_index],
                     obt_hybrid_img_urls[temp_index], obt_pp, inverse, dump_tstr, mature, isGroup)
                discord_commits.append(entry)
                temp_index = temp_index + 1

def handle_nf_catchup(new_deviation_count, new_hybrid_count, artist, foldername,folderid, serverid, channel_id, obt_dcuuid, obt_last_ids, last_ids, obt_hybrid_ids, last_hybrids, inverse, deviant_secret, deviant_id, mature, isGroup, obt_pp, commits):
    deviantlogger = logging.getLogger("deviantcog")
    obt_latest_id = last_ids[0]
    if inverse:
        deviantlogger.info("Catching up on deviations")
        didCatchup = True
        foundDeviation = False
        offset = 0
        obt_token = dp.getToken(deviant_secret, deviant_id)
        commits['data_resources']["ids"] = []
        commits['data_resources']["urls"] = []
        commits['data_resources']["img-urls"] = []
        while not foundDeviation:
            folder_response = dp.getGalleryFolderArrayResponse(artist, mature, folderid, obt_token, offset)
            try:
                if not folder_response["has_more"] and len(folder_response["results"]) == 0:
                    commits['data_resources']   ["ids"] = []
                    didCatchup = False
                    abort = True
                    break
            except Exception as ex:
                didCatchup = False
                break
            gotId = idlistHasId(last_ids[0], folder_response)
            foundDeviation = gotId
            if not foundDeviation:
                catchup_index = 0
                for entry in folder_response["results"]:
                    if entry["deviationid"] == last_ids[0]:
                        break
                    else:
                        url = get_image_url(entry)
                        commits['data_resources']["img-urls"].append(url)
            offset = offset + 10
        reachedEnd = False
    elif not inverse:
        deviantlogger.info("Catching up on deviations")
        didCatchup = True
        foundDeviation = False
        offset = 0
        obt_token = dp.getToken(deviant_secret, deviant_id)
        commits['data_resources']["ids"] = []
        commits['data_resources']["urls"] = []
        commits['data_resources']["img-urls"] = []
        while not reachedEnd:
            index = index - 1
            if obt_latest_id == folder_response["results"][index]["deviationid"]:
                break
            else:
                url = get_image_url(entry)
                commits['data_resources']   ["img-urls"].append(url)
                commits['data_resources']["ids"].append(folder_response["results"][index]["deviationid"])
                commits['data_resources']["urls"].append(folder_response["results"][index]["url"])
        max_hits = len(commits['data_resources']["ids"])
        hits = len(commits['data_resources']["ids"])
        catchup_finished = False
        while not hits == 0:
            hits = hits - 1
            dump_tstr = str(datetime.datetime.now())
            entry:DeviationNotification = DeviationNotification(
                "normal", channel_id, artist, foldername, commits['data_resources']["urls"][hits],
            commits['data_resources']["img-urls"][hits], obt_pp,inverse, dump_tstr, mature, isGroup)
            commits['discord_commits'].append(entry)
            


def handle_nf_deviation_updates(new_deviation_count, new_hybrid_count, artist, foldername,folderid, serverid, channel_id, obt_dcuuid, obt_last_ids, last_ids, obt_hybrid_ids, last_hybrids, inverse, deviant_secret, deviant_id, mature, isGroup, obt_pp):
    deviantlogger = logging.getLogger("deviantcog")
    
    if new_deviation_count == 0 and new_hybrid_count == 0:
        deviantlogger.info("No updates required")
        return [], [], []

    commits = {
        'hybrid': [],
        'normal': [],
        'hybrid_only': [],
        'discord_commits': [],
        'data_resources': {}
    }
    obt_latest_id = last_ids[0]
    didCatchup = False
    timestr = datetime.datetime.now()
    if new_deviation_count > 0 and new_deviation_count > 10:
        commits['normal'].append((
            obt_dcuuid, timestr, obt_last_ids, artist, folderid, serverid, channel_id
        ))
        deviantlogger.info(f"New deviations found: {new_deviation_count}")
    
    if new_deviation_count == 10:
        handle_nf_catchup(new_deviation_count, new_hybrid_count, artist, foldername,folderid, serverid, channel_id, obt_dcuuid, obt_last_ids, last_ids, obt_hybrid_ids, last_hybrids, inverse, deviant_secret, deviant_id, mature, isGroup, obt_pp, commits)
    # Checks to see if the entire list of deviations is new
    elif ifAllNewDeviationsListOnly(obt_last_ids, last_ids):
        if not obt_latest_id == None:
            handle_nf_catchup(new_deviation_count, new_hybrid_count, artist, foldername,folderid, serverid, channel_id, obt_dcuuid, obt_last_ids, last_ids, obt_hybrid_ids, last_hybrids, inverse, deviant_secret, deviant_id, mature, isGroup, obt_pp, commits)         

    if new_hybrid_count > 0:
        commits['hybrid_only'].append((
            obt_dcuuid, timestr, obt_hybrid_ids, artist, folderid, serverid, channel_id
        ))
        deviantlogger.info(f"New hybrid deviations found: {new_hybrid_count}")

    if new_deviation_count > 0 and new_hybrid_count > 0:
        commits['hybrid'].append((
            obt_dcuuid, timestr, obt_last_ids, obt_hybrid_ids, artist, folderid, serverid, channel_id
        ))
        deviantlogger.info("Both new deviations and hybrid deviations found")

    return commits['hybrid'], commits['normal'], commits['hybrid_only'], commits['discord_commits'], commits['data_resources']


async def syncListeners(conn,deviant_secret, deviant_id, shard_id, givenPool: Pool):
    """
        Method ran grab SQL queries from sqlManager.

        :param conn: The database connection.
        :type conn: conn
        :param task_cursor: The cursor that will do task related SQL queries
        :type task_cursor: cursor
        :param source_cursor: The cursor that will do task related SQL queries
        :type source_cursor: cursor

    """
    change_all_sql = """ UPDATE deviantcord.deviation_listeners
                         SET dc_uuid = data.dcuuid, last_update = data.last_update, 
                        last_ids = data.last_ids::text[] FROM (VALUES %s) AS data(dcuuid, last_update, last_ids, artist,serverid, channelid, mature)
                         WHERE deviantcord.deviation_listeners.artist = data.artist AND
                         deviantcord.deviation_listeners.serverid = data.serverid AND deviantcord.deviation_listeners.channelid = data.channelid
                         AND deviantcord.deviation_listeners.mature = data.mature 
                         AND deviantcord.deviation_listeners.foldertype = 'all-folder'"""
    insert_notification_sql = """INSERT INTO deviantcord.deviation_notifications(channelid, artist, foldername, deviation_link, img_url, pp_url, id, inverse, notif_creation, mature_only, fromgroupuser)
                 VALUES %s """
    source_get_sql = """ SELECT * from deviantcord.deviation_data where artist = %s AND folderid = %s 
    AND inverse_folder = %s AND hybrid = %s"""
    source_get_all_sql = """SELECT * from deviantcord.deviation_data_all where artist = %s AND mature = %s"""
    task_get_sql = "select * from deviantcord.deviation_listeners where disabled = false AND shard_id = %s"
    deviantlogger = logging.getLogger("deviantcog")
    task_cursor = conn.cursor()
    source_cursor = conn.cursor()
    task_cursor.execute(task_get_sql,(shard_id,))
    obt = task_cursor.fetchall()
    obt_token = dp.getToken(deviant_secret, deviant_id)
    textSent = False
    twilioData = None
    with open("twilio.json","r") as twilioJson:
        twilioData = json.load(twilioJson)
        twilioJson.close()

    for data in obt:
        try:
            if task_cursor.statusmessage:
                task_cursor.close()
                conn.commit()
                task_cursor = conn.cursor()
            timestr = datetime.datetime.now()
            all_folder_commits = []
            hybrid_commits = []
            normal_commits = []
            discord_commits = []
            data_resources = {}
            hybrid_only_commits = []
            serverid: float = data[0]
            artist = data[1]
            folderid = data[2]
            foldertype = data[3]
            dc_uuid = data[4]
            channel_id = data[7]
            foldername = data[12]
            inverse = data[11]
            hybrid = data[10]
            last_update = data[8]
            # TODO HERE IS THE BUG
            last_ids = data[13]
            last_hybrids = data[14]
            mature = data[15]
            deviantlogger.info(
                "Adding source for artist " + artist + " in folder " + foldername + " using flags hybrid: " + str(hybrid)
                + " inverse: " + str(inverse) + " mature " + str(mature))
            print("Checking " + artist + " at folder " + foldername)
            if foldertype == "regular":
                print("Getting information...")
                source_cursor.execute(source_get_sql, (artist, folderid, inverse, hybrid))

                obtained_source = source_cursor.fetchmany(1)
                obt_artist = obtained_source[0][1]
                obt_foldername = obtained_source[0][2]
                obt_folderid = obtained_source[0][3]
                obt_inverted = obtained_source[0][4]
                obt_offset = obtained_source[0][16]
                obt_dcuuid = obtained_source[0][5]
                obt_img_urls = obtained_source[0][8]
                obt_last_urls = obtained_source[0][12]
                obt_last_ids = obtained_source[0][13]
                obt_hybrid_ids = obtained_source[0][14]
                obt_hybrid_urls = obtained_source[0][17]
                obt_hybrid_img_urls = obtained_source[0][18]
                isGroup = obtained_source[0][21]
                if len(last_ids) == 0:
                    obt_latest_id = None
                else:
                    obt_latest_id = last_ids[0]
                obt_pp = obtained_source[0][9]
                deviantlogger.info("Comparing DC UUID " + str(dc_uuid) + " from obt_dcuuid " + str(obt_dcuuid))
                print("DC UUID: " + dc_uuid)
                print("vs ")
                print(obt_dcuuid)
                #Check if IDs match
                if not dc_uuid == obt_dcuuid:
                    new_deviation_count = 0
                    new_hybrid_count = 0
                    print("DC UUIDs do not match")
                    if hybrid:
                        new_deviation_count = localDetermineNewDeviation(obt_last_ids, last_ids, inverse)
                        new_hybrid_count = localDetermineNewDeviation(obt_hybrid_ids, last_hybrids, inverse)
                        
                        hybrid_commits, normal_commits, hybrid_only_commits, discord_commits, data_resources = handle_nf_deviation_updates(new_deviation_count, new_hybrid_count, artist, foldername, folderid, serverid, channel_id, obt_dcuuid, obt_last_ids, last_ids, obt_hybrid_ids, last_hybrids, inverse, deviant_secret, deviant_id, mature, isGroup, obt_pp)
                    else:
                        new_deviation_count = localDetermineNewDeviation(obt_last_ids, last_ids, inverse)
                        normal_commits = handle_nf_deviation_updates(new_deviation_count, new_hybrid_count, artist, foldername, folderid, serverid, channel_id, obt_dcuuid, obt_last_ids, last_ids, obt_hybrid_ids, last_hybrids, inverse, deviant_secret, deviant_id, mature, isGroup, obt_pp)
                    create_nf_deviation_notifications(new_deviation_count, new_hybrid_count, artist, foldername, mature, isGroup, folderid, serverid, channel_id, obt_dcuuid, obt_last_urls, obt_img_urls, obt_pp, inverse, discord_commits, obt_hybrid_urls, obt_hybrid_img_urls, obt_hybrid_ids)
                    await handle_nf_deviation_notifications(discord_commits, normal_commits, hybrid_commits, hybrid_only_commits, givenPool, conn)
            if foldertype == "all-folder":
                source_cursor.execute(source_get_all_sql, (artist, mature))
                obtained_source = source_cursor.fetchmany(1)
                obt_dcuuid = obtained_source[0][2]
                obt_img_urls = obtained_source[0][5]
                obt_last_urls = obtained_source[0][9]
                obt_last_ids = obtained_source[0][10]
                obt_pp = obtained_source[0][6]
                isGroup = obtained_source[0][13]
                if not dc_uuid == obt_dcuuid:
                    new_deviation_count = localDetermineNewDeviation(obt_last_ids, last_ids, inverse)
                    if new_deviation_count > 0:
                        all_folder_commits.append((obt_dcuuid, timestr, obt_last_ids, artist, serverid, channel_id, mature))
                        temp_index = 0
                        passes = 0
                        while not passes == new_deviation_count:
                            dump_tstr = str(datetime.datetime.now())
                            discord_commits.append(
                                (
                                    channel_id, artist, foldername, obt_last_urls[temp_index], obt_img_urls[temp_index],
                                    obt_pp,
                                    True, dump_tstr, mature, isGroup))
                            temp_index = temp_index + 1
                            passes = passes + 1
                    temp_cursor = conn.cursor()
                    deviantlogger.info("AllFolder Commit Length " + str(len(all_folder_commits)))
                    deviantlogger.info("AllFolder Discord Commits " + str(len(discord_commits)))
                    failed_notifications = []
                    if not len(all_folder_commits) == 0:
                        psycopg2.extras.execute_values(temp_cursor, change_all_sql, all_folder_commits)
                    if not len(discord_commits) == 0:
                        for notification in discord_commits:
                            try:
                                obtNotification: DeviationNotification = DeviationNotification("deviation",
                                    notification[0], notification[1], notification[2], notification[3], notification[4],
                                    notification[5], notification[6], notification[7], notification[8], notification[9]
                                )
                                await obtNotification.sendNotification(givenPool)
                            except ConnectionError as conEx:
                                failed_notifications.append(notification)
                            except Exception as commonEx:
                                failed_notifications.append(notification)
                                capture_exception(commonEx)
                    if not len(failed_notifications) == 0:
                        with open(findFileName("notification-failover"), "w+") as failedNotificationFile:
                            failedNotificationFile.write(json.dumps(failedNotificationFile))
                            failedNotificationFile.close()

                    deviantlogger.info("Committing Transactions to DB")
                    conn.commit()
                    deviantlogger.info("Transactions committed successfully")
                    temp_cursor.close()
        except Exception as e:
            capture_exception(e)
            print(e)
            conn.rollback()
    if task_cursor and not task_cursor.closed:
        task_cursor.close()
    if source_cursor and not source_cursor.closed:
        source_cursor.close()


def importFailedNotifications(conn, givenPool: Pool):
    json_files = getFailedTaskJsonFiles()
    for file in json_files:
        with open(file, "r") as jsonFile:
            data = json.load(jsonFile)
            jsonFile.close()
            if data["failure_type"] == "deviation":

                entry: DeviationNotification = DeviationNotification(
                    data["type"], data["channelid"], data["artist"], data["folder"], data["devi_url"], data["devi_img_url"],
                    data["pp_url"], data["inverse"], data["ts"], data["mature_devi"], data["isGroupDevi"]
                )
                try:
                    entry.sendNotification(givenPool)
                    print("Sent deviation notification!")
                    os.remove(file)
                except ConnectionError as conEx:
                    print("Failed to send notification!")
                    print(conEx)
                except Exception as commonEx:
                    print("Failed to send notification!")
                    print(commonEx)
            elif data["failure_type"] == "journal":
                entry: JournalNotification = JournalNotification(
                    data["channelid"], data["artist"], data["pp_url"], data["title"], data["url"], data["tstr"], data["mature_journal"], data["thumb_url"]
                )
                try:
                    entry.sendNotification(givenPool)
                    print("Sent journal notification!")
                    os.remove(file)
                except ConnectionError as conEx:
                    print("Failed to send notification!")
                    print(conEx)
                except Exception as commonEx:
                    print("Failed to send notification!")
                    print(commonEx)
            elif data["failure_type"] == "status":
                entry: StatusNotification = StatusNotification(
                    data["channelid"], data["artist"], data["pp_url"], data["title"], data["url"], data["tstr"], data["mature_status"], data["thumb_url"]
                )
                try:
                    entry.sendNotification(givenPool)
                    print("Sent status notification!") 
                    os.remove(file)
                except ConnectionError as conEx:
                    print("Failed to send notification!")
                    print(conEx)
                except Exception as commonEx:
                    print("Failed to send notification!")
                    print(commonEx)
            

def addalltask(serverid: int, channelid: int, artistname, mature, conn):
    source_sql = grab_sql("grab_all_source_import")
    task_cursor = conn.cursor()
    task_cursor.execute(source_sql, (artistname, mature))
    obt_result = task_cursor.fetchone()
    dcuuid = obt_result[1]
    last_ids = obt_result[10]
    sql = grab_sql("new_task")
    timestr = datetime.datetime.now()
    deviantlogger = logging.getLogger("deviantcog")
    deviantlogger.info("Adding alltask for artist " + artistname
                       + " for guild " + str(serverid) + " in channel" + str(channelid) + " in mature " + str(mature))
    task_cursor.execute(sql,
                        (serverid, artistname, "none", "all-folder", dcuuid, False, [], channelid, timestr, timestr,
                         None, True, "All Folder", last_ids, None, mature))
    deviantlogger.info("Committing transaction to database")
    conn.commit()
    deviantlogger.info("Transactions committed")


def addtask(serverid: int, channelid: int, artistname, foldername, folderid, inverse, hybrid, mature, conn):
    source_sql = grab_sql("grab_source_import")
    task_cursor = conn.cursor()
    task_cursor.execute(source_sql, (folderid, inverse, hybrid, mature))
    obt_result = task_cursor.fetchone()
    dcuuid = obt_result[4]
    last_ids = obt_result[13]
    last_hybrid_ids = obt_result[14]
    sql = grab_sql("new_task")
    timestr = datetime.datetime.now()
    deviantlogger = logging.getLogger("deviantcog")
    deviantlogger.info(
        "Adding task for artist " + artistname + " in folder " + foldername + " using flags hybrid: " + str(hybrid)
        + " inverse: " + str(inverse) + " mature " + str(mature) + " for guild " + str(serverid) + " in channelid " +
        str(channelid))
    task_cursor.execute(sql, (serverid, artistname, folderid, "regular", dcuuid, False, [], channelid, timestr, timestr,
                              hybrid, inverse, foldername, last_ids, last_hybrid_ids, mature))
    deviantlogger.info("Committing transaction to database")
    conn.commit()
    deviantlogger.info("Transactions committed")




