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
from urllib3 import Retry, PoolManager

from errite.tools.mis import convertBoolString
import urllib.request, json
import urllib.error
import urllib3.util
import urllib3
import logging
from errite.da.jsonTools import findDuplicateJsonElementGallery, findDuplicateElementArray

current_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def getToken(clientsecret, clientid):
    """
    Method ran to grab a new token from DA and return it, Login tokens on DeviantArt last for 60 minutes.

    :param clientsecret: The clientsecret associated with your app registered on DeviantArts Dev Area.
    :type clientsecret: string
    :param clientid: The clientid associated with your app registered on DeviantArts Dev Area.
    :type clientid: string
    :return: string
    """
    logger = logging.getLogger('errite.da.daparser')
    logger.info("GetToken: Started")
    
    tokenRequestURL = "https://www.deviantart.com/oauth2/token?grant_type=client_credentials&client_id=" + clientid + \
                     "&client_secret=" + clientsecret
    
    # Set up retry strategy
    user_agent = {'user-agent': current_user_agent}
    retries = Retry(connect=5, read=2, redirect=5, backoff_factor=3)
    http = PoolManager(retries=retries, headers=user_agent)
    
    try:
        # Use urllib3 instead of urllib.request for better timeout handling
        response = http.request('GET', tokenRequestURL, timeout=30.0)
        data = json.loads(response.data.decode('UTF-8'))
        return data["access_token"]
        
    except (urllib3.exceptions.TimeoutError, urllib3.exceptions.ConnectionError) as e:
        logger.error(f"Connection error when fetching token: {str(e)}")
        raise

def checkTokenValid(token):
    """
    Method ran to check if a token is valid, Login tokens on DeviantArt last for 60 minutes.

    :param token: The token to validate
    :type token: string
    :return: int (0 means valid, any other number corresponds with the DeviantArt HTTP Error Code)
    """
    logger = logging.getLogger('errite.da.daparser')
    logger.info("CheckTokenValid: Started")
    
    tokenCheckURL = "https://www.deviantart.com/api/v1/oauth2/gallery/folders?access_token=" + token + \
                    "&username=zander-the-artist&calculate_size=false&ext_preload=false&limit=10&mature_content=true&offset=0"
    
    # Set up retry strategy
    user_agent = {'user-agent': current_user_agent}
    retries = Retry(connect=5, read=2, redirect=5, backoff_factor=3)
    http = PoolManager(retries=retries, headers=user_agent)
    
    try:
        response = http.request('GET', tokenCheckURL, timeout=30.0)
        if response.status == 200:
            logger.info("CheckTokenValid: Token is valid")
            return 0
        elif response.status == 401:
            logger.info("Token is not valid...")
            return 401
        elif response.status == 503:
            logger.error("DA Servers are down for maintenance")
            return 503
        elif response.status == 500:
            logger.error("DA experienced an issue")
            return 500
        elif response.status == 429:
            logger.error("DA API is currently overloaded...")
            return 429
        else:
            logger.error(f"Unexpected status code: {response.status}")
            return response.status
            
    except (urllib3.exceptions.TimeoutError, urllib3.exceptions.ConnectionError) as e:
        logger.error(f"Connection error when checking token validity: {str(e)}")
        raise

def daHasDeviations(artist, accesstoken):
    """
            Method ran to check if a an artist has Deviations on DA by checking their Gallery All View.

            :param artist: The name of the artist who's deviations we are working with. This is needed for json references
            :type artist: string
            :param accesstoken: The name of the gallery folder we are working with. Used for json references
            :type accesstoken: string
            :return: bool
    """

    data = getAllFolderArrayResponse(artist.lower(), bool, accesstoken, 0)
    try:
        if len(data["results"]) == 0:
            print("No deviations")
            return False
    except KeyError:
        print("Invalid Data sent. ")
        return False
    return True


def getFolderArrayResponse(artist, bool, folder, accesstoken, offset):
    """
    Method ran to get the list of folders from an artist from deviantart's API.

    :param artist: The artist's name that owns the folder.
    :type artist: string
    :param bool: Whether mature folders will show or not.
    :type bool: bool
    :param folder: The Exact folder name to grab the UUID of
    :type folder: string
    :param accesstoken: The DA Access token to use for this query
    :type accesstoken: string
    :param offset: The offset value at which to request the gallery folder contents from
    :type offset: int
    :return: array
    """
    logger = logging.getLogger('errite.da.daparser')
    logger.info("GetFolderArrayResponse: Started")
    
    folderRequestURL = "https://www.deviantart.com/api/v1/oauth2/gallery/folders?access_token=" + accesstoken + \
                      "&username=" + artist + "&calculate_size=false&ext_preload=false&limit=10&mature_content=" + \
                      convertBoolString(bool) + "&offset=" + str(offset)
    
    # Set up retry strategy
    user_agent = {'user-agent': current_user_agent}
    retries = Retry(connect=5, read=2, redirect=5, backoff_factor=3)
    http = PoolManager(retries=retries, headers=user_agent)
    
    try:
        # Use urllib3 instead of urllib.request for better timeout handling
        response = http.request('GET', folderRequestURL, timeout=30.0)
        data = json.loads(response.data.decode('UTF-8'))
        return data
        
    except (urllib3.exceptions.TimeoutError, urllib3.exceptions.ConnectionError) as e:
        logger.error(f"Connection error when fetching folder data: {str(e)}")
        raise


def getAllFolderArrayResponse(artist, bool, accesstoken, offset):
    """
    Method ran to get the Gallery Folder data all view from deviantart's API.
    
    :param artist: The artist's name that owns the folder.
    :type artist: string
    :param bool: Whether mature folders will show or not.
    :type bool: bool
    :param accesstoken: The DA Access token to use for this query
    :type accesstoken: string
    :param offset: The offset value at which to request the gallery folder contents from
    :type offset: int
    :return: array
    """
    folderRequestURL = "https://www.deviantart.com/api/v1/oauth2/gallery/all" + "?username=" + artist + "&access_token=" + accesstoken + "&limit=10&mature_content=" + convertBoolString(
        bool) + "&offset=" + str(offset)
    
    # Set up retry strategy
    user_agent = {'user-agent': current_user_agent}
    retries = Retry(connect=5, read=2, redirect=5, backoff_factor=3)
    http = PoolManager(retries=retries, headers=user_agent)
    
    try:
        # Use urllib3 instead of urllib.request for better timeout handling
        response = http.request('GET', folderRequestURL, timeout=30.0)
        data = json.loads(response.data.decode('UTF-8'))
        return data
        
    except (urllib3.exceptions.TimeoutError, urllib3.exceptions.ConnectionError) as e:
        logger = logging.getLogger('errite.da.daparser')
        logger.error(f"Connection error when fetching gallery data: {str(e)}")
        raise

def getUserStatusesResponse(artist:str, accessToken:str, offset:str):
    user_agent = {'user-agent': current_user_agent}
    retries = Retry(connect=5, read=5, redirect=5, backoff_factor=4)
    folderRequestURL = "https://www.deviantart.com/api/v1/oauth2/user/statuses/ " + "?username=" + artist +\
                       "&access_token=" + accessToken + "&limit=10" + "&offset=" + str(offset)
    http = PoolManager(retries=retries, headers=user_agent)
    urllib3.disable_warnings()
    heroes = http.request('GET', folderRequestURL)
    data = json.loads(heroes.data.decode('UTF-8'))
    return data


def getGalleryFolderArrayResponse(artist, bool, folder, accesstoken, offset):
    """
        Method ran to get the Gallery Folder data from deviantart's API.

        :param artist: The artist's name that owns the folder.
        :type artist: string
        :param bool: Whether mature folders will show or not.
        :type bool: bool
        :param folder: UUID of the folder that data is being grabbed from
        :type folder: string
        :param accesstoken: The DA Access token to use for this query
        :type accesstoken: string
        :param offset: The offset value at which to request the gallery folder contents from. The starting value
        :type offset: int
        :return: array
        """
    finished = False;
    user_agent = {'user-agent': current_user_agent}
    retries = Retry(connect=5, read=5, redirect=5, backoff_factor=4)
    folderRequestURL = "https://www.deviantart.com/api/v1/oauth2/gallery/" + folder + "?username=" + artist + "&access_token=" + accesstoken + "&limit=10&mature_content=" + convertBoolString(
        bool) + "&offset=" + str(offset)
    #print(folderRequestURL)
    # print(offset)
    http = PoolManager(retries=retries, headers=user_agent)
    urllib3.disable_warnings()
    heroes = http.request('GET', folderRequestURL)
    data = json.loads(heroes.data.decode('UTF-8'))
    return data


def tagSearchResponse(tag, accesstoken, mature):
    """
            Method ran to get the tagsearch for similiar tags from deviantart's API.
            :param tag: The tag that should be searched for.
            :type tag: string
            :param accesstoken: The DA Access token to use for this query
            :type accesstoken: string
            :param mature: Whether the mature tags should be returned
            :type mature: int
            :return: array
            :param offset: The number of items to offset the results by
    """
    requestURL = "https://www.deviantart.com/api/v1/oauth2/browse/tags/search?tag_name=" + tag \
                 + "&access_token=" + accesstoken + "&mature_content=" + str(mature)
    with urllib.request.urlopen(requestURL) as url:
        data = json.loads(url.read().decode())
        return data;

def userInfoResponse(username, accesstoken, mature):
    """
            Method ran to get the tagsearch for similiar tags from deviantart's API.
            :param tag: The tag that should be searched for.
            :type tag: string
            :param accesstoken: The DA Access token to use for this query
            :type accesstoken: string
            :param mature: Whether the mature tags should be returned
            :type mature: int
            :return: array
            :param offset: The number of items to offset the results by
    """
    info = {}
    retries = Retry(connect=5, read=5, redirect=5, backoff_factor=4)
    requestURL = "https://www.deviantart.com/api/v1/oauth2/user/profile/" + username + "?ext_collections=false&ext_galleries=false" \
                 + "&access_token=" + accesstoken + "&mature_content=" + str(mature)
    http = PoolManager(retries=retries)
    results = http.request('GET', requestURL)
    data = json.loads(results.data.decode('UTF-8'))
    info["data"] = data
    info["response"] = results
    return info


def searchResponse(tag, accesstoken, mature, offset):
    """
            Method ran to get data for deviations with the provided tag from deviantart's API.
            :param tag: The tag that should be searched for.
            :type tag: string
            :param accesstoken: The DA Access token to use for this query
            :type accesstoken: string
            :param mature: Whether the mature tags should be returned
            :type mature: bool
            :param offset: The number of items to offset the results by
            :type offset: int
            :return: array

    """
    requestURL = "https://www.deviantart.com/api/v1/oauth2/browse/tags/search?tag=" + tag \
                 + "&access_token=" + accesstoken + "&mature_content=" + str(mature) + "&offset=" + str(offset)
    with urllib.request.urlopen(requestURL) as url:
        data = json.loads(url.read().decode())
        return data;


def getJournalResponse(artist, accesstoken, featuredonly, mature):
    """
    Method ran to get journal data from the specified artist using deviantart's API.
    :param artist: The tag that should be searched for.
    :type artist: string
    :param featuredonly: Fetch only journals that are feature
    :type featuredonly: bool
    :param accesstoken: The DA Access token to use for this query
    :type accesstoken: string
    :param mature: Whether the mature tags should be returned
    :type mature: int
    :return: array
    """
    logger = logging.getLogger('errite.da.daparser')
    logger.info("GetJournalResponse: Started")
    
    requestURL = "https://www.deviantart.com/api/v1/oauth2/user/profile/posts?access_token=" + accesstoken + "&username=" \
                 + artist + "&featured=" + str(featuredonly) + "&mature_content=" + str(mature)
    
    # Set up retry strategy
    user_agent = {'user-agent': current_user_agent}
    retries = Retry(connect=5, read=2, redirect=5, backoff_factor=3)
    http = PoolManager(retries=retries, headers=user_agent)
    
    try:
        # Use urllib3 instead of urllib.request for better timeout handling
        response = http.request('GET', requestURL, timeout=30.0)
        data = json.loads(response.data.decode('UTF-8'))
        return data
        
    except (urllib3.exceptions.TimeoutError, urllib3.exceptions.ConnectionError) as e:
        logger.error(f"Connection error when fetching journal data: {str(e)}")
        raise

def getStatusResponse(artist, accesstoken, mature):
    """
                Method ran to get status data from the specified artist using deviantart's API.
                :param artist: The tag that should be searched for.
                :type artist: string
                :param accesstoken: The DA Access token to use for this query
                :type accesstoken: string
                :param mature: Whether the mature tags should be returned
                :type mature: int
                :return: array
        """
    requestURL = "https://www.deviantart.com/api/v1/oauth2/user/statuses/?username=" + artist + "&access_token=" + \
                 accesstoken + "&mature_content=" \
                 + str(mature)
    with urllib.request.urlopen(requestURL) as url:
        data = json.loads(url.read().decode())
        return data;


def findFolderUUID(artist, bool, folder, accesstoken):
    """
    Method ran to get the List of Folders from an artist and determine if the folder requested exists.
    If it exists then it returns the UUID
    Returns None if it does not exist.

    :param artist: The artist's name to request the folder's UUID id's from
    :type artist: string
    :param bool: Whether mature folders will show or not.
    :type bool: bool
    :param folder: The Exact folder name to grab the UUID of
    :type folder: string
    :param accesstoken: The DA Access token to use for this query
    :type accesstoken: string
    :return: array
    """
    finished = False
    providedoffset = 0
    while (finished == False):
        try:
            data = getFolderArrayResponse(artist, bool, folder, accesstoken, providedoffset)
            if data["error"] is not None:
                return "ERROR";
        except urllib.error.HTTPError:
            return"ERROR";
        except KeyError:
            tmp = data["has_more"]
            print("Error was not triggered...")

        tmp = data["has_more"]
        # print(data);

        # print(tmp)
        if tmp == True:
            for uuid in data['results']:
                # print (uuid["folderid"])
                if uuid["name"].lower() == folder.lower():
                        return uuid["folderid"];
                providedoffset = data["next_offset"]

        if tmp == False:
            for uuid in data['results']:
                if uuid["name"].lower() == folder.lower():
                        return uuid["folderid"]
            finished = True
    return "None";


