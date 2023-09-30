import os
import sys
import time
from dataclasses import dataclass

import qbittorrentapi
from discord_webhook import DiscordWebhook, DiscordEmbed
from hurry.filesize import alternative, size

# READ THE ENV VARS:
QBIT_HOST = os.environ.get('QBIT_IP')
QBIT_PORT = os.environ.get('QBIT_PORT')
QBIT_USER = os.environ.get('QBIT_LOGIN_USER')
QBIT_PASS = os.environ.get('QBIT_LOGIN_PASS')
QBIT_RATIO_TRESHOLD = float(os.environ.get('QBIT_RATIO_TRESHOLD'))
QBIT_TIME_DELAY = int(os.environ.get('QBIT_TIME_DELAY'))
QBIT_ABSOLUTE_TIME_DELAY = int(os.environ.get('QBIT_ABSOLUTE_TIME_DELAY'))
QBIT_TAGS = os.environ.get('QBIT_TAGS')
QBIT_TRACKERS_WITH_RATIO_TRESHOLD = os.environ.get('QBIT_TRACKERS_WITH_RATIO_TRESHOLD')
QBIT_ADD_TRACKERS_IN_TAGS = os.getenv("QBIT_ADD_TRACKERS_IN_TAGS", 'False').lower() in ('true', '1', 't', 'yes', 'y')
QBIT_SET_DEFAULT_QBIT_RATIO = os.getenv("QBIT_SET_DEFAULT_QBIT_RATIO", 'False').lower() in (
    'true', '1', 't', 'yes', 'y')
QBIT_SET_TRACKERS_QBIT_RATIO = os.getenv("QBIT_SET_TRACKERS_QBIT_RATIO", 'False').lower() in (
    'true', '1', 't', 'yes', 'y')
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL'))
DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK')


@dataclass
class TorrentWrapper:
    torrent: qbittorrentapi.torrents.TorrentDictionary
    timeExceeded: bool


@dataclass
class TrackerRatio:
    tracker: str
    ratio: float


print("Starting Script..")

qbt_client = qbittorrentapi.Client(host=QBIT_HOST, port=QBIT_PORT, username=QBIT_USER, password=QBIT_PASS)

inputTags = []
if QBIT_TAGS != '':
    inputTags = list(map(lambda x: x.strip(), QBIT_TAGS.lower().split(",")))


# create the dataclass TrackerRatio that will be used later to make the comparisons
def createTrackersRatioFromEnv():
    trackersRatioList = []
    # don't populate the list if the user didn't use this env var
    if QBIT_TRACKERS_WITH_RATIO_TRESHOLD == "":
        return trackersRatioList

    for tracker in QBIT_TRACKERS_WITH_RATIO_TRESHOLD.split(";"):
        trackerUrlAndRatio = tracker.split("@")
        if len(trackerUrlAndRatio) != 2:
            print(
                "ERR: ENV var TRACKERS_SEED_RATIO is not set properly - you need to make it in the following format:\n TRACKERNAME1@RATIO;TRACKERNAME2@RATIO\nWhere the TRACKERNAME is the name of the tracker (ex. torrentleech) and the RATIO is a decimal number (ex. 1.3)\nNow exiting app!")
            sys.exit(0)

        ratio = 0.0
        try:
            ratio = float(trackerUrlAndRatio[1])
        except ValueError:
            print(
                "ERR: ENV var TRACKERS_SEED_RATIO is not set properly - you need to set the ratio to be a decimal number like 2.3 for example. Now exiting app!")
            sys.exit(0)

        trackersRatioList.append(TrackerRatio(str(trackerUrlAndRatio[0]), ratio))

    return trackersRatioList


# compare the torrent trackers with the trackers and ratio inpputed in the env var
def shouldDeleteOnTrackerRatio(torrent, trackersSeedRatioList):
    for torTracker in torrent.trackers:
        for trackerSeedRatio in trackersSeedRatioList:
            if trackerSeedRatio.tracker in torTracker["url"]:

                # set the ratio if the ENV QBIT_SET_TRACKERS_QBIT_RATIO is set to true
                if QBIT_SET_TRACKERS_QBIT_RATIO:
                    qbt_client.torrents_set_share_limits(str(trackerSeedRatio.ratio), -1, -1, torrent.hash)

                # set the trackers url in the torrent's tag if the ENV QBIT_ADD_TRACKERS_IN_TAGS is set to true
                if QBIT_ADD_TRACKERS_IN_TAGS:
                    # add the tag (first remove it if it has it - then add it)
                    torrent.removeTags(trackerSeedRatio.tracker)
                    torrent.addTags(trackerSeedRatio.tracker)

                # if the ratio and the tracker are matched - return that this torrent is eligible for deletion
                if torrent.ratio >= trackerSeedRatio.ratio:
                    return True
    return False


def normalize_seconds(seconds: int):
    (days, remainder) = divmod(seconds, 86400)
    (hours, remainder) = divmod(remainder, 3600)
    (minutes, seconds) = divmod(remainder, 60)
    res = ""

    if days != 0:
        res += f"{days} days"
        if hours != 0:
            res += f" and {hours} hours"
    elif hours != 0:
        res += f"{hours} hours"
        if minutes != 0:
            res += f" and {minutes} minutes"
    elif minutes != 0:
        res += f"{minutes} minutes"

    return res


def postStatsToDiscord(torrentsToRemove):
    totalSize = 0
    for cTor in torrentsToRemove:
        totalSize = totalSize + cTor.torrent.completed

    webhook = DiscordWebhook(url=DISCORD_WEBHOOK, content="_____\n`Total size on disk removed:` **" + str(
        size(totalSize, system=alternative)) + "**")
    embed = DiscordEmbed(description='The following torrents were deleted:', color=3589207)

    for cTor in torrentsToRemove:
        # add the tags in the message if they exists for the current torrent
        existingTags = qbt_client.torrents_info(torrent_hashes=cTor.torrent.hash)[0]["tags"]
        if existingTags:
            existingTags = f"   :white_small_square:*Tags:* __{existingTags}__"
        else:
            existingTags = ""

        if cTor.timeExceeded:
            timeExceeded = f"   :small_orange_diamond: *Max time of {normalize_seconds(QBIT_ABSOLUTE_TIME_DELAY)} exceeded*   :small_orange_diamond: *Ratio: {round(cTor.torrent.ratio, 2)}*"
            movieSize = str(size(cTor.torrent.completed, system=alternative))
            embed.add_embed_field(name=f":movie_camera: {cTor.torrent.name}",
                                  value=f":small_blue_diamond: {movieSize}{timeExceeded}{existingTags}",
                                  inline=False)
        else:
            movieSize = str(size(cTor.torrent.completed, system=alternative))
            embed.add_embed_field(name=f":movie_camera: {cTor.torrent.name}",
                                  value=f":small_blue_diamond: {movieSize}{existingTags}",
                                  inline=False)

    embed.set_timestamp()
    webhook.add_embed(embed)

    try:
        webhook.execute()
    except Exception as e:
        print(f"Total size on disk removed: {str(size(totalSize, system=alternative))}")
        print("WARNING: Discord webhook is not valid - or was not specified!")


def processTorrents(trackersSeedRatioList):
    torrentsToRemove = []
    torrentsHashes = []

    # remove only the torrents that have reached ratio of >=1.0 and have been completed for at least 1 hour, or completed torrents older than 1 week
    for torrent in qbt_client.torrents_info():
        timeDiff = int(time.time()) - abs(torrent.completion_on)

        # set the ratio if the ENV QBIT_SET_DEFAULT_QBIT_RATIO is set to true
        if QBIT_SET_DEFAULT_QBIT_RATIO:
            qbt_client.torrents_set_share_limits(str(QBIT_RATIO_TRESHOLD), -1, -1, torrent.hash)

        if shouldDeleteOnTrackerRatio(torrent,
                                      trackersSeedRatioList) and torrent.completion_on > 0 and timeDiff >= QBIT_TIME_DELAY:
            if shouldDeleteOnTag(torrent):
                torrentsToRemove.append(TorrentWrapper(torrent, False))
                torrentsHashes.append(torrent.hash)
        elif torrent.ratio >= QBIT_RATIO_TRESHOLD and torrent.completion_on > 0 and timeDiff >= QBIT_TIME_DELAY:
            if shouldDeleteOnTag(torrent):
                torrentsToRemove.append(TorrentWrapper(torrent, False))
                torrentsHashes.append(torrent.hash)

        elif torrent.completion_on > 0 and timeDiff >= QBIT_ABSOLUTE_TIME_DELAY:
            if shouldDeleteOnTag(torrent):
                torrentsToRemove.append(TorrentWrapper(torrent, True))
                torrentsHashes.append(torrent.hash)

    if torrentsToRemove:
        # delete all marked torrents
        postStatsToDiscord(torrentsToRemove)
        qbt_client.torrents_delete(delete_files=True, torrent_hashes=torrentsHashes)


def shouldDeleteOnTag(torrent):
    torrentTags = list(map(lambda x: x.strip(), torrent.tags.lower().split(",")))

    deleteTorrent = len(inputTags) == 0

    if len(inputTags) > 0:
        if len(list(set(inputTags) & set(torrentTags))) > 0:
            deleteTorrent = True
        else:
            deleteTorrent = False

    return deleteTorrent


def main():
    try:
        print("Trying to login to QbitTorrent...")
        qbt_client.auth_log_in()
        trackersSeedRatioList = createTrackersRatioFromEnv()
        print("Successfuly connected to QbitTorrent. Listening for potential torrents to delete..")
        while True:
            processTorrents(trackersSeedRatioList)
            time.sleep(CHECK_INTERVAL)
    except qbittorrentapi.LoginFailed as e:
        print("Invalid login credentials - please check your login credentials - the script will now exit!")
        sys.exit(0)
    except Exception as e:
        print(
            "Cannot find qbitTorrent! Please check to see if the webUI has been enabled. If running a docker container, check to see if it's alive. The script will check availability in 1 minute. ",
            e)
        time.sleep(60)
        main()


main()
