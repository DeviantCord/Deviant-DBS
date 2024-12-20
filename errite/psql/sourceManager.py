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
import logging
from sentry_sdk import configure_scope, set_context, set_extra, capture_exception
import psycopg2
import psycopg2.extras
import json
import uuid
import datetime
import errite.da.daParser as dp
from errite.da.datools import determineNewDeviations
from errite.tools.mis import gatherGalleryFolderResources, createIDURLList
from errite.psql.sqlManager import grab_sql
from twilio.rest import Client


def updateSources(con, data, clientToken):
    check_sql = """ UPDATE deviantcord.deviation_data
                 SET last_check = data.last_check FROM (VALUES %s) AS data(last_check, artist, folderid)
                 WHERE deviantcord.deviation_data.artist = data.artist AND deviantcord.deviation_data.folderid = data.folderid"""
    change_sql = """ UPDATE deviantcord.deviation_data
                 SET dc_uuid = data.dcuuid, last_update = data.last_update, last_check = data.last_check, 
                 latest_img_urls = data.latest_img_url::text[], latest_pp_url = data.latest_pp_url::text,
                 latest_deviation_url = data.latest_deviation_url, last_urls = data.last_urls::text[],
                  last_ids = data.last_ids::text[], given_offset = data.given_offset FROM (VALUES %s) AS data(dcuuid, last_update, last_check, latest_img_url, latest_pp_url, latest_deviation_url,
                            last_urls, last_ids, given_offset, artist, folderid, inverse_folder, hybrid, mature)
                 WHERE deviantcord.deviation_data.artist = data.artist AND deviantcord.deviation_data.folderid = data.folderid AND
                 deviantcord.deviation_data.inverse_folder = data.inverse_folder AND deviantcord.deviation_data.hybrid = data.hybrid 
                 AND deviantcord.deviation_data.mature = data.mature"""
    hybrid_change_sql = """ UPDATE deviantcord.deviation_data
                 SET dc_uuid = data.dcuuid, last_update = data.last_update, last_check = data.last_check, 
                 latest_img_urls = data.latest_img_url::text[], latest_pp_url = data.latest_pp_url::text,
                 latest_deviation_url = data.latest_deviation_url, last_urls = data.last_urls::text[],
                  last_ids = data.last_ids::text[], given_offset = data.given_offset, last_hybrid_ids = data.last_hybrid_ids::text[],
                  hybrid_urls = data.hybrid_urls::text[], hybrid_img_urls = data.hybrid_img_urls::text[]
                   FROM (VALUES %s) AS data(dcuuid, last_update, last_check, latest_img_url, latest_pp_url, latest_deviation_url,
                             last_urls, last_ids, given_offset,last_hybrid_ids, hybrid_urls, hybrid_img_urls, artist, folderid,
                             hybrid, inverse_folder, mature)
                 WHERE deviantcord.deviation_data.artist = data.artist AND deviantcord.deviation_data.folderid = data.folderid
                 AND deviantcord.deviation_data.hybrid = data.hybrid AND deviantcord.deviation_data.inverse_folder = data.inverse_folder
                 AND deviantcord.deviation_data.mature = data.mature"""
    hybrid_only_sql = """ UPDATE deviantcord.deviation_data
                     SET last_check = data.last_check, last_hybrid_ids = data.last_hybrid_ids::text[], 
                     hybrid_urls = data.hybrid_urls::text[], hybrid_img_urls = data.hybrid_img_urls::text[] FROM (VALUES %s) 
                     AS data(last_check, last_hybrid_ids, hybrid_urls, hybrid_img_urls, artist, folderid, hybrid, inverse_folder, mature)
                     WHERE deviantcord.deviation_data.artist = data.artist 
                     AND deviantcord.deviation_data.folderid = data.folderid AND deviantcord.deviation_data.hybrid = data.hybrid
                     AND deviantcord.deviation_data.inverse_folder = data.inverse_folder AND deviantcord.deviation_data.mature = data.mature"""
    
    deviantlogger = logging.getLogger("deviantcog")
    test = []
    checks = []
    hybridCommits = []
    hybridOnly = []
    batch_size = 5  # Reduced from 100 to match updateallsources
    cursor = con.cursor()
    committingData = False
    
    for row in data:
        try:
            check_only = False
            normal_update = True
            has_hybrid = False
            foldername = row[2]
            artistname = row[1]

            print("Trying artist " + artistname + " in folder " + foldername)
            folderid = row[3]
            inverse = row[4]
            dc_uuid = row[5]
            last_updated = row[6]
            last_check = row[7]
            latest_img_url = row[8]
            latest_pp_url = row[9]
            latest_deviation_url = row[10]
            mature = row[11]
            last_urls = row[12]
            last_ids = row[13]
            last_hybrids = row[14]
            hybrid = row[15]
            offset = row[16]
            timestr = datetime.datetime.now()
            didCatchup = False

            print("Normal Checking artist: " + artistname + " in folder " + foldername + " inverse: " +
                               str(inverse) +
                               " hybrid: " + str(hybrid) + " mature " + str(mature) + " offset " + str(offset))
            if inverse:
                da_response = dp.getGalleryFolderArrayResponse(artistname, mature, folderid, clientToken, 0)
                if len(da_response["results"]) == 0:
                    latest_pp_url = "none"
                else:
                    latest_pp_url = da_response["results"][0]["author"]["usericon"]
                if hybrid:
                    hybridResponse = dp.getGalleryFolderArrayResponse(artistname, mature, folderid, clientToken, offset)
                    if len(hybridResponse["results"]) == 0:
                        has_hybrid = True
                        gathered_hybrids = createIDURLList(hybridResponse)
                        normal_update = False
                    elif len(last_hybrids) == 0 and not len(hybridResponse["results"]) == 0:
                        has_hybrid = True
                        gathered_hybrids = createIDURLList(hybridResponse)
                        normal_update = False
                    elif not hybridResponse["results"][0]["deviationid"] == last_hybrids[0]:
                        has_hybrid = True
                        gathered_hybrids = createIDURLList(hybridResponse)
                        normal_update = False

            elif not inverse:
                da_response = dp.getGalleryFolderArrayResponse(artistname, mature, folderid, clientToken, offset)
                if da_response["has_more"]:
                    didCatchup = True
                    end_offolder = False
                    offset = da_response["next_offset"]
                    while not end_offolder:
                        da_response = dp.getGalleryFolderArrayResponse(artistname, mature, folderid, clientToken,
                                                                       offset)
                        if da_response["has_more"]:
                            offset = offset + 10
                        else:
                            end_offolder = True

                result_len = len(da_response["results"])
                if result_len == 0:
                    latest_pp_url = "none"
                else:
                    latest_pp_url = da_response["results"][result_len - 1]["author"]["usericon"]
                if hybrid:
                    hybridResponse = dp.getGalleryFolderArrayResponse(artistname, mature, folderid, clientToken, 0)
                    if len(last_hybrids) == 0 and not len(hybridResponse["results"]) == 0:
                        has_hybrid = True
                        gathered_hybrids = createIDURLList(hybridResponse)
                        normal_update = False
                    elif not hybridResponse["results"][0]["deviationid"] == last_hybrids[0]:
                        has_hybrid = True
                        gathered_hybrids = createIDURLList(hybridResponse)
                        normal_update = False
            if len(da_response["results"]) == 0:
                gathered_resources = gatherGalleryFolderResources(da_response)
                if len(last_ids) == 0:
                    continue
                try:
                    offset_increase = determineNewDeviations(da_response["results"], last_ids)
                    offset = offset + offset_increase
                except Exception as ex:
                    print(ex)
                dcuuid = str(uuid.uuid1())
                last_ids = gathered_resources["deviation-ids"]
                last_urls = gathered_resources["deviation-urls"]
                if len(gathered_resources["deviation-urls"]) == 0:
                    latest_deviation_url = "none"
                else:
                    latest_deviation_url = gathered_resources["deviation-urls"][0]
                last_updated = timestr
                last_check = timestr
                latest_img_url: str = gathered_resources["img-urls"]
                print("Triggered")
            elif len(last_ids) == 0 and not len(da_response["results"]) == 0:
                gathered_resources = gatherGalleryFolderResources(da_response)
                if not didCatchup:
                    offset_increase = determineNewDeviations(da_response["results"], last_ids)
                    offset = offset + offset_increase
                dcuuid = str(uuid.uuid1())
                last_ids = gathered_resources["deviation-ids"]
                last_urls = gathered_resources["deviation-urls"]
                if len(gathered_resources["deviation-urls"]) == 0:
                    latest_deviation_url = []
                else:
                    latest_deviation_url = gathered_resources["deviation-urls"][0]
                last_updated = timestr
                last_check = timestr
                latest_img_url: str = gathered_resources["img-urls"]
                print("Triggered")
            elif not da_response["results"][0]["deviationid"] == last_ids[0]:
                gathered_resources = gatherGalleryFolderResources(da_response)
                if not didCatchup:
                    offset_increase = determineNewDeviations(da_response["results"], last_ids)
                    offset = offset + offset_increase
                dcuuid = str(uuid.uuid1())
                last_ids = gathered_resources["deviation-ids"]
                last_urls = gathered_resources["deviation-urls"]
                if len(gathered_resources["deviation-urls"]) == 0:
                    latest_deviation_url = []
                else:
                    latest_deviation_url = gathered_resources["deviation-urls"][0]
                last_updated = timestr
                last_check = timestr
                latest_img_url:str = gathered_resources["img-urls"]
                print("Triggered")
            else:
                last_check = timestr
                check_only = True
                normal_update = False
            if latest_pp_url is None:
                latest_pp_url = "none"
            if normal_update:
                dcuuid = str(uuid.uuid1())
                test.append((dcuuid, last_updated, last_check, latest_img_url, latest_pp_url, latest_deviation_url,
                              last_urls, last_ids, offset, artistname, folderid, inverse, hybrid, mature))
                print(test[0])
            if check_only:
                checks.append((timestr, artistname, folderid))
            if has_hybrid:
                dcuuid = str(uuid.uuid1())
                hybridCommits.append((dcuuid, last_updated, last_check, latest_img_url, latest_pp_url, latest_deviation_url,
                         last_urls, last_ids, offset, gathered_hybrids["ids"], gathered_hybrids["urls"],
                                      gathered_hybrids["img-urls"], artistname, folderid, hybrid, inverse, mature))

            # Batch process more frequently
            if len(test) >= batch_size:
                committingData = True
                deviantlogger.info(f"Updating with pre-emptive batch of {len(test)} updates")
                psycopg2.extras.execute_values(cursor, change_sql, test)
                con.commit()
                committingData = False
                test = []
                
            if len(checks) >= batch_size:
                committingData = True
                deviantlogger.info(f"Updating with pre-emptive batch of {len(checks)} checks")
                psycopg2.extras.execute_values(cursor, check_sql, checks)
                con.commit()
                committingData = False
                checks = []
                
            if len(hybridCommits) >= batch_size:
                committingData = True
                deviantlogger.info(f"Updating with pre-emptive batch of {len(hybridCommits)} hybrid commits")
                psycopg2.extras.execute_values(cursor, hybrid_change_sql, hybridCommits)
                con.commit()
                committingData = False
                hybridCommits = []

        except Exception as e:
            if committingData:
                con.rollback()
            elif str(test[0][9]) == str(artistname):  # Remove failed artist from batch if it caused the error
                del test[0]
            deviantlogger.exception(e)
            capture_exception(e)
            print(f"Error processing {artistname}: {str(e)}")
            continue  # Continue to next artist instead of failing completely
    
    try:
        # Process any remaining updates
        if len(checks) > 0:
            deviantlogger.info(f"Updating with remaining batch of {len(checks)} checks")
            psycopg2.extras.execute_values(cursor, check_sql, checks)
            con.commit()
            
        if len(test) > 0:
            deviantlogger.info(f"Updating with remaining batch of {len(test)} updates")
            psycopg2.extras.execute_values(cursor, change_sql, test)
            con.commit()
            
        if len(hybridCommits) > 0:
            deviantlogger.info(f"Updating with remaining batch of {len(hybridCommits)} hybrid commits")
            psycopg2.extras.execute_values(cursor, hybrid_change_sql, hybridCommits)
            con.commit()
            
        if len(hybridOnly) > 0:
            deviantlogger.info(f"Updating with remaining batch of {len(hybridOnly)} hybrid only updates")
            psycopg2.extras.execute_values(cursor, hybrid_only_sql, hybridOnly)
            con.commit()

    except Exception as e:
        con.rollback()
        deviantlogger.exception(e)
        capture_exception(e)
        print(f"Error in final batch processing: {str(e)}")
        
    finally:
        if not cursor.closed:
            cursor.close()

def updateallfolders(con, data, clientToken):
    check_sql = """ UPDATE deviantcord.deviation_data_all
                 SET last_check = data.last_check FROM (VALUES %s) AS data(last_check, artist, mature)
                 WHERE deviantcord.deviation_data_all.artist = data.artist AND deviantcord.deviation_data_all.mature = data.mature"""
    change_sql = """ UPDATE deviantcord.deviation_data_all
                 SET dc_uuid = data.dcuuid, last_update = data.last_update, last_check = data.last_check, 
                 latest_img_urls = data.latest_img_url::text[], latest_pp_url = data.latest_pp_url,
                 latest_deviation_url = data.latest_deviation_url, last_urls = data.last_urls::text[],
                  last_ids = data.last_ids::text[] FROM (VALUES %s) AS data(dcuuid, last_update, last_check, latest_img_url, latest_pp_url, latest_deviation_url,
                            last_urls, last_ids, artist, mature)
                 WHERE deviantcord.deviation_data_all.artist = data.artist AND deviantcord.deviation_data_all.mature = data.mature"""
    deviantlogger = logging.getLogger("deviantcog")
    updates = []
    checks = []
    textSent = False
    cursor = con.cursor()
    debug_index = 0
    committingData = False
    for row in data:
        try:    
            hybridResponse = None
            check_only = False
            normal_update = True
            has_hybrid = False
            new_uuid = str(uuid.uuid1())
            artistname = row[1]
            dc_uuid = row[2]
            last_updated = row[3]
            last_check = row[4]
            latest_img_url = row[5]
            latest_pp_url = row[6]
            latest_deviation_url = row[7]
            mature = row[8]
            last_urls = row[9]
            last_ids = row[10]
            new_check_timestamp = datetime.datetime.now()
            new_update_timestamp = datetime.datetime.now()
            deviantlogger.info("Checking artist: " + artistname + " mature " + str(mature))
            #Its always 0 since new deviations for all folders are only posted on the top
            if artistname.lower() == "ibp-8":
                print("DEBUG CONDITION MET")
            da_response = dp.getAllFolderArrayResponse(artistname, mature, clientToken, 0)
            gathered_allfolders = gatherGalleryFolderResources(da_response)
            if len(da_response["results"]) == 0:
                latest_pp_url = "none"
            elif len(last_ids) == 0 and len(da_response["results"]) > 0:
                if latest_pp_url is None:
                    latest_pp_url = 'none'
                else:
                    latest_pp_url = da_response["results"][0]["author"]["usericon"]
                updates.append((new_uuid, new_update_timestamp, new_check_timestamp, gathered_allfolders["img-urls"], latest_pp_url, latest_deviation_url,
                            gathered_allfolders["deviation-urls"], gathered_allfolders["deviation-ids"], artistname, mature))
            elif len(gathered_allfolders["deviation-ids"]) == 0 or not da_response["results"][0]["deviationid"] == last_ids[0]:
                if latest_pp_url is None:
                    latest_pp_url = 'none'
                else:
                    latest_pp_url = da_response["results"][0]["author"]["usericon"]
                updates.append((new_uuid, new_update_timestamp, new_check_timestamp, gathered_allfolders["img-urls"], latest_pp_url, latest_deviation_url,
                            gathered_allfolders["deviation-urls"], gathered_allfolders["deviation-ids"], artistname, mature))
            else:
                checks.append((new_check_timestamp, artistname, mature))
            debug_index = debug_index + 1

            # Batch process updates more frequently to avoid long-running transactions
            if len(updates) >= 5:  # Process in batches of 100
                committingData = True
                print("Updating with pre-emptive batch of " + str(len(updates)) + " updates")
                psycopg2.extras.execute_values(cursor, change_sql, updates)
                con.commit()
                committingData = False
                updates = []
            if len(checks) >= 5:
                committingData = True
                print("Updating with pre-emptive batch of " + str(len(checks)) + " checks")
                psycopg2.extras.execute_values(cursor, check_sql, checks)
                con.commit()
                committingData = False
                checks = []
        except Exception as e:
            if committingData:
                con.rollback()
            elif str(updates[0][8]) == str(artistname):
                del updates[0]
            print("Notified sentry of error")
            print(e)
            deviantlogger.exception(e)
            capture_exception(e)
    
    try:
        # Process any remaining updates
        if len(checks) > 0:
            print("Updating with remaining batch of " + str(len(checks)) + " checks")
            psycopg2.extras.execute_values(cursor, check_sql, checks)
            con.commit()
        if len(updates) > 0:
            print("Updating with remaining batch of " + str(len(updates)) + " updates")
            psycopg2.extras.execute_values(cursor, change_sql, updates)
            con.commit()
        cursor.close()

    except Exception as e:
        # Make sure to rollback on error
        con.rollback()
        deviantlogger.exception(e)
        capture_exception(e)
        print("Uh oh, an exception has occured!")
        print(e)
    finally:
        # Ensure cursor is closed
        if not cursor.closed:
            cursor.close()

def verifySourceExistance(artist, folder, inverse, hybrid, mature, conn):
    sql = grab_sql("verify_source_exists")
    verify_cursor = conn.cursor()
    verify_cursor.execute(sql, (artist, folder, inverse, hybrid, mature))
    obt_results = verify_cursor.fetchone()
    verify_cursor.close()
    if obt_results is None:
        return False
    else:
        return True

def verifySourceExistanceExtra(artist, folder, inverse, hybrid, mature, conn):
    information = {}
    sql = grab_sql("verify_source_exists")
    verify_cursor = conn.cursor()
    verify_cursor.execute(sql, (artist, folder, inverse, hybrid, mature))
    obt_results = verify_cursor.fetchone()
    verify_cursor.close()
    if obt_results is None:
        information["results"] = False
        return information
    else:
        information["results "] = True
        information["ids"] = obt_results[1]
        information["hybrid-ids"] = obt_results[2]
        return information

def verifySourceExistanceAll(artist,mature, conn):
    sql = grab_sql("verify_all_source_exists")
    verify_cursor = conn.cursor()
    verify_cursor.execute(sql, (artist, mature))
    obt_results = verify_cursor.fetchone()
    verify_cursor.close()
    if obt_results is None:
        return False
    else:
        return True


def addallsource(daresponse, artist, conn, mature, dcuuid = str(uuid.uuid1())):
    #Since the initial checks to make sure the given artist isn't a group. We already hit the DA API once.
    # No point in hitting it again
    deviantlogger = logging.getLogger("deviantcog")
    deviantlogger.info("Adding all source for artist " + artist + " with mature flag " + str(mature))
    gathered_allfolders = gatherGalleryFolderResources(daresponse)
    sql = grab_sql("new_all_source")
    source_cursor = conn.cursor()
    timestr = str(datetime.datetime.now())
    if len(daresponse["results"]) == 0:
        pp_picture = "none"
    else:
        pp_picture = daresponse["results"][0]["author"]["usericon"]
    if len(daresponse["results"]) == 0 or len(gathered_allfolders["deviation-ids"]) == 0:
        source_cursor.execute(sql, (artist, dcuuid, timestr, timestr, gathered_allfolders["img-urls"],
                                    pp_picture, "none", json.dumps(daresponse), mature, gathered_allfolders["deviation-urls"],
                                    gathered_allfolders["deviation-ids"]))
    else:
        source_cursor.execute(sql, (artist, dcuuid, timestr, timestr, gathered_allfolders["img-urls"],
                                    pp_picture, gathered_allfolders["deviation-urls"][0], json.dumps(daresponse), mature, gathered_allfolders["deviation-urls"],
                                    gathered_allfolders["deviation-ids"]))
    deviantlogger.info("AddallSource successfully executed. Committing to DB")
    conn.commit()
    deviantlogger.info("Committed")
    source_cursor.close()


def addsource(artist, folder, folderid, inverse, hybrid, client_token, conn, mature,dcuuid = str(uuid.uuid1())):
    source_information = {}
    gathered_hybrid = None
    source_information["normal-ids"] = None
    source_information["hybrid-ids"] = None
    new_url = None
    deviantlogger = logging.getLogger("deviantcog")
    deviantlogger.info("Adding source for artist " + artist + " in folder " + folder + " using flags hybrid: " +
                       str(hybrid) + " inverse: " + str(inverse) + " mature " + str(mature))
    if inverse == False:
        offset = 0
        current_data = {}
        hybrid_data = None
        has_more = True
        while has_more:
            current_data = dp.getGalleryFolderArrayResponse(artist, mature, folderid, client_token, offset)
            if not current_data["has_more"]:
                break;
            else:
                offset = current_data["next_offset"]

        if hybrid:
            hybrid_data = dp.getGalleryFolderArrayResponse(artist, mature, folderid, client_token, 0)
            gathered_hybrid = gatherGalleryFolderResources(hybrid_data)

        sql = grab_sql("new_source")
        gathered_resources = gatherGalleryFolderResources(current_data)
        folder_cursor = conn.cursor()
        if len(current_data["results"]) == 0:
            pp_picture = "none"
        else:
            pp_picture = current_data["results"][0]["author"]["usericon"]
        if pp_picture is None:
            pp_picture = "none"
        timestr = datetime.datetime.now()
        if len(gathered_resources["deviation-urls"]) == 0:
            new_url = None
        else:
            new_url = gathered_resources["deviation-urls"][len(gathered_resources["deviation-urls"]) - 1]
        if hybrid:
            folder_cursor.execute(sql,(artist, folder, folderid, inverse, dcuuid, timestr, timestr,
                                       gathered_resources["img-urls"], json.dumps(current_data),
                                       new_url,
                                       pp_picture, mature, gathered_resources["deviation-urls"], gathered_resources["deviation-ids"],
                                       gathered_hybrid["deviation-ids"], hybrid, offset, gathered_hybrid["deviation-urls"],
                                       gathered_hybrid["img-urls"],))
        else:
            folder_cursor.execute(sql, (artist, folder, folderid, inverse, dcuuid, timestr, timestr,
                                        gathered_resources["img-urls"], json.dumps(current_data),
                                        new_url,pp_picture, mature, gathered_resources["deviation-urls"],
                                        gathered_resources["deviation-ids"],None, hybrid, offset, None, None,))
    elif inverse == True:
        print("Entered true")
        current_data = dp.getGalleryFolderArrayResponse(artist, mature, folderid, client_token, 0)
        if hybrid:
            has_more = True
            offset = 0
            while has_more:
                hybrid_data = dp.getGalleryFolderArrayResponse(artist, mature, folderid, client_token, offset)
                if not hybrid_data["has_more"]:
                    break;
                else:
                    offset = hybrid_data["next_offset"]

            gathered_hybrid = gatherGalleryFolderResources(hybrid_data)
        sql = grab_sql("new_source")
        gathered_resources = gatherGalleryFolderResources(current_data)
        folder_cursor = conn.cursor()
        if len(current_data["results"]) == 0:
            pp_picture = "none"
        else:
            pp_picture = current_data["results"][0]["author"]["usericon"]
        dcuuid = str(uuid.uuid1())
        timestr = datetime.datetime.now()
        if len(gathered_resources["deviation-urls"]) == 0:
            new_url = None
        else:
            new_url = gathered_resources["deviation-urls"][len(gathered_resources["deviation-urls"]) - 1]
        if hybrid:
            # HERE
            folder_cursor.execute(sql,(artist, folder, folderid, inverse, dcuuid, timestr, timestr,
                                       gathered_resources["img-urls"], json.dumps(current_data),
                                       new_url,
                                       pp_picture, mature, gathered_resources["deviation-urls"], gathered_resources["deviation-ids"],
                                       gathered_hybrid["deviation-ids"], hybrid, offset, gathered_hybrid["deviation-urls"],
                                       gathered_hybrid["img-urls"],))
        else:
            folder_cursor.execute(sql, (artist, folder, folderid, inverse, dcuuid, timestr, timestr,
                                        gathered_resources["img-urls"], json.dumps(current_data),
                                        new_url,
                                        pp_picture, mature, gathered_resources["deviation-urls"],
                                        gathered_resources["deviation-ids"],None, hybrid, 0,None,None,))
    deviantlogger.info("Committing transactions to DB")
    conn.commit()
    deviantlogger.info("Successfully committed transactions to DB")
    folder_cursor.close()
    source_information["normal-ids"] = gathered_resources["deviation-ids"]
    if hybrid:
        source_information["hybrid-ids"] = gathered_hybrid["deviation-ids"]
    else:
        source_information["hybrid-ids"] = None
    return source_information
