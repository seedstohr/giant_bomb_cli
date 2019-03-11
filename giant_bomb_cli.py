#! /usr/bin/python
"  Command line utility for downloading and streaming videos from Giant Bomb!  "
import urllib2
import json
import argparse
from subprocess import call
import os

COLOURS = {"Desc" : "\033[94m",
           "Title" : "\033[93m",
           "Error" : "\033[31m",
           "Debug" : "\033[32m",
           "End" : "\033[0m"}

VIDEO_QUALITIES = {"low",
                   "high",
                   "hd",}

STATUS_CODES = {1 : "OK",
                100 : "Invalid API Key",
                101 : "Object Not Found",
                102 : "Error in URL Format",
                103 : "jsonp' format requires a 'json_callback' argument",
                104 : "Filter Error",
                105 : "Subscriber only video is for subscribers only"}

CONFIG_LOCATION = os.path.expanduser("~/.giant_bomb_cli")

def gb_log(colour, string):
    " Log a string with a specified colour "
    string = string.encode('utf-8')
    print colour + string + COLOURS["End"]

def file_exists_on_server(url):
    " Make the server request "
    try:
        urllib2.urlopen(url)
    except urllib2.URLError:
        return False

    return True

def convert_seconds_to_string(seconds):
    " Convert a time in seconds to a nicely formatted string "
    mins = str(seconds/60)
    secs = str(seconds%60)

    # clean up instance of single digit second values
    # eg [2:8] -> [2:08]
    if len(secs) == 1:
        secs = "0" + secs

    return mins + ":" + secs

def get_status_code_as_string(status_code):
    """ Convert an api status_code to a string
        See here for more details:
        https://www.giantbomb.com/api/documentation#toc-0-0 """

    int_status_code = int(status_code)

    if STATUS_CODES.has_key(int_status_code):
        return STATUS_CODES[int_status_code]
    else:
        return "Unknown"

def create_filter_string_from_args(args):
    " Creates the filter url parameters from the users arguments "
    filter_string = ""
    if args.shouldFilter:
        filter_string += "&filter="
        if args.filterName != None:
            # Handle spaces correctly
            args.filterName = args.filterName.replace(" ", "%20")
            filter_string += "name:" + args.filterName + ","
        if args.contentID != None:
            filter_string += "id:" + args.contentID + ","
        if args.videoShow != None:
            filter_string += "video_show:" + args.videoShow + ","

    return filter_string

def create_request_url(args, api_key):
    " Creates the initial request url "
    request_url = "http://www.giantbomb.com/api"
    request_url += "/videos/"
    request_url += "?api_key=" + api_key
    request_url += "&format=json"
    request_url += "&limit=" + str(args.limit)
    request_url += "&offset=" + str(args.offest)
    request_url += "&sort=id:" + args.sortOrder
    return request_url



def retrieve_json_from_url(url, json_obj):
    """ Grabs the json file from the server, validates the error code
        If this function returns true then the json obj passed in has been
        filled with valid data """

    #Make the server request
    response = None
    try:
        response = urllib2.urlopen(url).read()
    except urllib2.HTTPError, exception:
        gb_log(COLOURS["Error"], "HTTPError = " + str(exception.code))
    except urllib2.URLError, exception:
        gb_log(COLOURS["Error"], "URLError = " + str(exception.reason))

    if response != None:
        json_file = json.loads(response)

        if "status_code" in json_file:
            error = get_status_code_as_string(json_file["status_code"])
            if error == "OK":
                json_obj.update(json_file)
                return True
        else:
            gb_log(COLOURS["Error"], "Error occured: " + error)

    return False

def dump_video_shows(api_key):
    " Print out the list of video shows "
    gb_log(COLOURS["Title"], "Dumping video show IDs")
    shows_url = "http://www.giantbomb.com/api/video_shows/?api_key={0}&format=json".format(api_key)
    json_obj = json.loads("{}")

    if retrieve_json_from_url(shows_url, json_obj) is False:
        gb_log(COLOURS["Error"], "Failed to retrieve video shows from GB API")
        return 1

    for video_show in json_obj["results"]:
	video_show["title"] = video_show["title"].replace(u"\u2018", "'").replace(u"\u2019", "'").replace(u"\xe9", "e")
	video_show["deck"] = video_show["deck"].replace(u"\u2018", "'").replace(u"\u2019", "'").replace(u"\xe9", "e")
        gb_log(COLOURS["Desc"],
               "\t {0}: {1} - ({2})".format(video_show["id"],
                                            video_show["title"], video_show["deck"]))

def validate_args(opts):
    " Validate the users arguments "

    # Validate filters
    if opts.shouldFilter is False:
        if opts.filterName != None or opts.contentID != None or opts.videoShow != None:
            gb_log(COLOURS["Error"], "Please use --filter command to process filter arguments")
            return False

    if opts.quality != None:
        if opts.quality not in VIDEO_QUALITIES:
            gb_log(COLOURS["Error"], "Invalid quality value, options are 'low', 'high', 'hd'")
            return False

    if opts.sortOrder != "asc" and opts.sortOrder != "desc":
        gb_log(COLOURS["Error"], "Invalid sort value, options are 'asc' or 'desc'")
        return False

    if opts.downloadArchive and not opts.downloadArchive.endswith(".json"):
        gb_log(COLOURS["Debug"], "Appending json extension to download archive")
        opts.downloadArchive += ".json"

    return True

def stream_video(url):
    " Steam the video at url "
    if url is None:
        gb_log(COLOURS["Error"], "Invalid URL, perhaps try another quality level?")
        return

    try:
        call(["mplayer", url + "?api_key=" + get_api_key()])
    except OSError:
        gb_log(COLOURS["Error"],
               "Something has gone wrong whilst trying to stream, is mplayer installed?")

def download_video(url, filename):
    " Download the video at url to filename"
    if url is None:
        gb_log(COLOURS["Error"], "Invalid URL, perhaps try another quality level?")
        return

    gb_log(COLOURS["Title"], "Downloading " + url + " to " + filename)
    try:
        call(["wget", "--no-check-certificate", "--user-agent", "downloading via giant_bomb_cli",
              url + "?api_key=" + get_api_key(), "-c", "-O", filename])
    except OSError:
        gb_log(COLOURS["Error"],
               "Something has gone wrong whilst trying to download, is wget installed?")

def output_response(response, args, download_archive):
    " Prints details of videos found "

    for video in response["results"]:
        name = video["name"]
        name = name.replace(u"\u2018", "'").replace(u"\u2019", "'").replace(u"\xe9", "e")
        desc = video["deck"]
        desc = desc.replace(u"\u2018", "'").replace(u"\u2019", "'").replace(u"\xe9", "e")
        time_in_secs = video["length_seconds"]
        video_id = video["id"]
        url = video[args.quality + "_url"]
        video_show_string = "None"
        video_show = video.get("video_show")
        if video_show:
            video_show_string = video_show.get("title")

        gb_log(COLOURS["Title"],
               u"{0} ({1}) [{2}] ID:{3}".format(name, video_show_string,
                                                convert_seconds_to_string(time_in_secs),
                                                video_id))
#        gb_log(COLOURS["Desc"], "\t" + desc)

        if args.shouldStream:
            stream_video(url)
        elif args.shouldDownload:
          # Construct filename
            filename = name.replace("/", "-")
            filename = filename.replace(":", "")
            if url is not None:
            	filename += "." + url.split(".")[-1]
            filename = str(video_id) + " - " + filename
            filename = filename.replace(u"\u2018", "'").replace(u"\u2019", "'").replace(u"\xe9", "e")

            if args.outputFolder != None:
                if not os.path.exists(args.outputFolder):
                    os.makedirs(args.outputFolder)
                filename = args.outputFolder + "/" + filename

            if args.downloadArchive and video_id in download_archive["Downloaded"]:
                gb_log(COLOURS["Debug"], "Skipping download as id is already in download archive")
                continue

            download_video(url, filename)

            if args.downloadArchive:
                download_archive["Downloaded"].append(video_id)

    if len(response["results"]) == 0:
        gb_log(COLOURS["Desc"], "No video results")

def get_api_key():
    " Get the users api key, either from the cache or via user input"

    if os.path.exists(CONFIG_LOCATION) is False:
        os.makedirs(CONFIG_LOCATION)

    config_file_path = CONFIG_LOCATION + "/config"

    config_json = json.loads("{}")
    if os.path.isfile(config_file_path):
        config_json = json.load(open(config_file_path, "r"))
    else:
        user_api = raw_input('Please enter your API key: ')
        config_json["API_KEY"] = user_api.strip()
        json.dump(config_json, open(config_file_path, "w"))

    return config_json["API_KEY"]

def main():
    " Main entry point "
    parser = argparse.ArgumentParser(version='Giant Bomb Command Line Interface v1.0.0')

    parser.add_argument('-l', '--limit', dest="limit", action="store", type=int,
                        default=25, metavar="<x>",
                        help="limits the amount of items requested, defaults to %(default)s")

    parser.add_argument('--offset', dest="offest", action="store", type=int,
                        default=0, metavar="<x>",
                        help="specify the offest into the results, defaults to %(default)s")

    parser.add_argument('--quality', dest="quality", action="store",
                        default="high",
                        help="the quality of the video, used when streaming or downloading" +
                        " (low, high, hd) defaults to %(default)s")

    parser.add_argument('--download', dest="shouldDownload", action="store_true",
                        help="will attempt to download all videos matching filters", default=False)

    parser.add_argument('--stream', dest="shouldStream", action="store_true",
                        help="will attempt to stream videos matching filters via mplayer",
                        default=False)

    parser.add_argument('--output', dest="outputFolder", action="store",
                        help="the folder to output downloaded content to")

    parser.add_argument('--dump_video_shows', dest="shouldDumpIDs", action="store_true",
                        help="will dump all known ids for video shows,", default=False)

    parser.add_argument('--filter', dest="shouldFilter", action="store_true",
                        help="will attempt to filter by the below arguments", default=False)

    parser.add_argument('--sort', dest="sortOrder", action="store", default="desc",
                        help="orders the videos by their id (asc/desc) defaults to desc")

    parser.add_argument('--download-archive', dest="downloadArchive", action="store",
                        help="Download videos whose ids aren't listed within the file, the script will also update the archive file each run")

    # Filter options
    filter_opts = parser.add_argument_group("Filter options",
                                            "Use these in conjunction with " +
                                            "--filter to customise results")

    filter_opts.add_argument('--name', dest="filterName", action="store",
                             help="search for videos containing the specified phrase in the name")

    filter_opts.add_argument('--id', dest="contentID", action="store", help="id of the video")

    filter_opts.add_argument('--video_show', dest="videoShow", action="store",
                             help="id of the video show (see --dump_video_shows)")

    # Debug options
    degbug_options = parser.add_argument_group("Debug Options")
    degbug_options.add_argument('--debug', dest="debugMode", action="store_true",
                                help="logs server requests and json responses", default=False)

    args = parser.parse_args()

    if validate_args(args) is False:
        return 1

    # Check for API key
    api_key = get_api_key()

    if args.shouldDumpIDs:
        dump_video_shows(api_key)
        return 0

    # Create the url and make the request
    request_url = create_request_url(args, api_key) + create_filter_string_from_args(args)
    json_obj = json.loads("{}")

    if args.debugMode:
        gb_log(COLOURS["Debug"], "Requesting url: " + request_url)

    if retrieve_json_from_url(request_url, json_obj) is False:
        gb_log(COLOURS["Error"], "Failed to get response from server")
        return 1

    if args.debugMode:
        gb_log(COLOURS["Debug"],
               "Received {0} of {1} possible results".format(json_obj["number_of_page_results"],
                                                             json_obj["number_of_total_results"]))
        gb_log(COLOURS["Debug"], json.dumps(json_obj, sort_keys=True, indent=4))

    download_archive = {"Downloaded": []}
    if args.downloadArchive and os.path.isfile(args.downloadArchive):
        with open(args.downloadArchive, 'r') as archive_file:
            download_archive = json.load(archive_file)

    output_response(json_obj, args, download_archive)

    if args.downloadArchive:
        with open(args.downloadArchive, 'w') as archive_file:
            json.dump(download_archive, archive_file, sort_keys=True, indent=4)

main()
