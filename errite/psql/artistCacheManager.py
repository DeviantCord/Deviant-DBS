from errite.da.datools import getUserInfo
import errite.da.daParser as dp
import time
import psycopg2
import psycopg2.extras
import redis
import datetime


def sync_artists(db_conn, da_token:str, rpool):
    update_sql = """UPDATE deviantcord.artist_info
                        SET artist_picture_url = data.artist_picture_url, last_updated = data.last_updated
                        FROM (VALUES %s) AS data(artist_picture_url, last_updated, cond_artist)
                        WHERE deviantcord.artist_info.artist = data.cond_artist """
    sql = """SELECT * FROM deviantcord.artist_info"""
    db_updates = []
    redis_updates = {}
    updated_redis = []
    db_cursor = db_conn.cursor()
    db_cursor.execute(sql)
    obt_artists = db_cursor.fetchall()
    for entry in obt_artists:
        timestr = datetime.datetime.now()
        obt_artistname:str = entry[0]
        obt_artistpic:str = entry[1]
        bug_occured = False
        valid_reply = False
        apply_updates = False
        artist_userinfo = dp.userInfoResponse(obt_artistname, da_token, False)
        if artist_userinfo["response"].status == 400:
            bug_occured = True
        elif artist_userinfo["response"].status == 500:
            bug_occured = True
        elif artist_userinfo["response"].status == 200:
            valid_reply = True
        else:
            raise ValueError
        if not bug_occured and valid_reply:
            ext_userinfo = getUserInfo(artist_userinfo["data"])
            if not obt_artistname.upper() == ext_userinfo["username"].upper() or not obt_artistpic == ext_userinfo["user_pic"]:
                apply_updates = True
            if apply_updates:
                db_updates.append((ext_userinfo["user_pic"], timestr, obt_artistname))
                redis_updates[ext_userinfo["username"]] = ext_userinfo["user_pic"]
                updated_redis.append(ext_userinfo["username"])

    if not len(db_updates) == 0:
        temp_cursor = db_conn.cursor()
        psycopg2.extras.execute_values(temp_cursor, update_sql, db_updates)
        db_conn.commit()
        temp_cursor.close()
    for redis_entry in updated_redis:
        redis_connection = redis.Redis(connection_pool=rpool)
        key = redis_entry.upper() + "-icon"
        key_result = redis_connection.get(key)
        if not key_result is None:
            redis_connection.set(key, redis_updates[redis_entry])
            redis_connection.expire(key, 3600)
        redis_connection.close()
    db_cursor.close()








