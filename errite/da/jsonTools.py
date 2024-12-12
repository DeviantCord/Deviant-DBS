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
import json
import logging


def findDuplicateJsonElementGallery(file, element, artist,foldername):
    """
            Method ran to check if a Deviation UUID is already in the ArtData json file.

            :param file: UNUSED The name of the json file that would be used to compare the provided UUID with existing UUID's
            :type file: string
            :param element: The UUID we are comparing with the JSON file.
            :type element: string
            :param artist: The name of the artist who's deviations we are working with. This is needed for json references
            :type artist: string
            :param foldername: The name of the gallery folder we are working with. Used for json references
            :type foldername: string
            :return: bool
    """
    logger = logging.getLogger('errite.da.jsonTools')
    with open("artdata.json", "r") as jsonFile:
        artdata = json.load(jsonFile)
        jsonFile.close();
        for storeduuid in artdata["art-data"][artist.lower()]["folders"][foldername]["processed-uuids"]:
            if storeduuid == element:
                # print("Compared element: " + element + "vs " + storeduuid)
                # print("Triggered Found match")
                return True;
        return False;

def findDuplicateElementArray(array, element):
    """
            Method ran to check if a Deviation UUID is already in the array.

            :param array: The array that holds the current processed uuids for the particular artist
            :type file: string
            :param element: The UUID we are comparing with the JSON file.
            :type element: string
            :param artist: UNUSED TO BE REMOVED The name of the artist who's deviations we are working with. This is needed for json references
            :type artist: string
            :param foldername: May be reused: The name of the gallery folder we are working with. Used for json references
            :type foldername: string
            :return: bool
    """
    logger = logging.getLogger('errite.da.jsonTools')
    for stored_uuid in array:
        if stored_uuid == element:
            logger.info("Found " + element + " im array")
            return True
    return False










def dumpURLListDebug(list):
    for element in list:
        print(element)
