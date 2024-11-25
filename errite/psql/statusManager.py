import datetime
import uuid

import psycopg2
import json

from aio_pika.pool import Pool

from errite.da.daParser import getUserStatusesResponse
from errite.da.datools import determineNewStatus, determineNewStatusIds
from errite.io.failedTask import writeFailedTaskJson
from errite.psql.sqlManager import grab_sql
from errite.tools.mis import createStatusInfoList
from errite.models.StatusNotification import StatusNotification


def updateStatuses(conn, clienttoken):
    get_sources = grab_sql("grab_all_status_updates")
    read_cursor = conn.cursor()
    read_cursor.execute(get_sources)
    obt_results = read_cursor.fetchall()
    status_change_sql = grab_sql("status_source_change")
    statusCommits = []
    for row in obt_results:
        artist = row[0]
        last_ids = row[1]
        dcuuid = str(uuid.uuid1())

        statusResponse = getUserStatusesResponse(artist,clienttoken, 0)
        if not len(statusResponse["results"]) == 0:
            if not statusResponse["results"][0]["deviationid"] == last_ids[0]:
                infoList = createStatusInfoList(statusResponse["results"])

                statusCommits.append((dcuuid, infoList["status-id"], infoList["thumbnails-img-urls"],
                                      infoList["status-urls"], infoList["excerpts"], infoList["profilepic"],
                                      infoList["thumbnail-ids"], artist))

    temp_cursor = conn.cursor()
    if not len(statusCommits) == 0:
        psycopg2.extras.execute_values(temp_cursor, status_change_sql, statusCommits)




def syncStatuses(conn, givenPool: Pool):
    changeCommits = []
    notificationCommits = []
    source_cursor = conn.cursor()
    journal_cursor = conn.cursor()
    write_cursor = conn.cursor()
    get_listeners = grab_sql("get_listener_status_updates")
    journal_cursor.execute(get_listeners)
    obt_journals = journal_cursor.fetchall()
    for statusEntry in obt_journals:
        artist = statusEntry[0]
        dc_uuid = statusEntry[1]
        last_ids = statusEntry[2]
        serverId = statusEntry[3]
        channelId = statusEntry[4]
        sql = grab_sql("get_sync_status_updates")
        source_cursor.execute(sql,(artist,))
        obt_source = source_cursor.fetchone()
        osLastStatusIds = obt_source[1]
        osLastItemsUrls = obt_source[2]
        osLastUrls = obt_source[3]
        osLastBodys = obt_source[4]
        osDcUUID = obt_source[5]
        osLastPP = obt_source[6]

        if not dc_uuid == osDcUUID:
            if not osLastStatusIds[0] == last_ids[0]:
                new_deviations = determineNewStatusIds(osLastStatusIds, last_ids)
                sql = grab_sql("add_status_notification")
                index = 0
                change_sql = grab_sql("change_status_listener")
                new_dccuid = str(uuid.uuid1())
                timestr = str(datetime.datetime.now())
                changeCommits.append((new_dccuid, osLastStatusIds, osLastPP, artist, serverId, channelId,))
                while not index == new_deviations:
                    timestr = str(datetime.datetime.now())
                    newNotif:StatusNotification = StatusNotification(timestr, osLastPP, osLastUrls[index], osLastBodys[index],
                                                                     artist,osLastItemsUrls[index], channelId)
                    notificationCommits.append(newNotif)
                    index = index + 1
                failed_notifications = []
                for notification in notificationCommits:
                    try:
                        notification.sendNotification(givenPool)
                    except ConnectionError as conEx:
                        failed_notifications.append(notification)
                    except Exception as commonEx:
                        failed_notifications.append(notification)
                if len(failed_notifications) > 0:
                    failed_status_dict = {}
                    failed_status_dict["failure_type"] = "status"
                    failed_status_dict["failed_entries"] = failed_notifications
                    failed_status_json = json.dump(failed_status_dict)
                    writeFailedTaskJson(failed_status_dict)
                post_notif_sql = grab_sql("add_status_notification")
                try:
                    psycopg2.extras.execute_values(write_cursor, change_sql, changeCommits)
                except Exception as EX2:
                    print("Exception")
                conn.commit()
            else:
                print("Skipped")


    print("Finished syncJournals!")