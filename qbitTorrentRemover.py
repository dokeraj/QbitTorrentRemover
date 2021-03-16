import qbittorrentapi
from discord_webhook import DiscordWebhook, DiscordEmbed
import os
from hurry.filesize import alternative, size
import time
import sys

# READ THE ENV VARS:
QBIT_HOST = os.environ.get('QBIT_IP')
QBIT_PORT = os.environ.get('QBIT_PORT')
QBIT_USER = os.environ.get('QBIT_LOGIN_USER')
QBIT_PASS = os.environ.get('QBIT_LOGIN_PASS')
QBIT_RATIO_TRESHOLD = float(os.environ.get('QBIT_RATIO_TRESHOLD'))
QBIT_TIME_DELAY = int(os.environ.get('QBIT_TIME_DELAY'))
QBIT_ABSOLUTE_TIME_DELAY = int(os.environ.get('QBIT_ABSOLUTE_TIME_DELAY'))
QBIT_TAGS = os.environ.get('QBIT_TAGS')
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL'))
DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK')

print("Starting Script..")

qbt_client = qbittorrentapi.Client(host=QBIT_HOST, port=QBIT_PORT, username=QBIT_USER, password=QBIT_PASS)

inputTags = []
if QBIT_TAGS != '':
	inputTags = list(map(lambda x: x.strip(), QBIT_TAGS.lower().split(",")))


def postStatsToDiscord(torrentsToRemove):
	totalSize = 0
	for cTor in torrentsToRemove:
		totalSize = totalSize + cTor.completed

	webhook = DiscordWebhook(url=DISCORD_WEBHOOK, content="_____\n`Total size on disk removed:` **" + str(size(totalSize, system=alternative)) + "**" )
	embed = DiscordEmbed(description='The following torrents were deleted:', color=3589207)

	for cTor in torrentsToRemove:
		movieSize = str(size(cTor.completed, system=alternative))
		embed.add_embed_field(name=f":movie_camera: {cTor.name}", value=f":small_blue_diamond: {movieSize}", inline=False)

	embed.set_timestamp()
	webhook.add_embed(embed)

	try:
		webhook.execute()
	except Exception as e:
		print(f"Total size on disk removed: {str(size(totalSize, system=alternative))}")
		print("WARNING: Discord webhook is not valid - or was not specified!")


def processTorrents():
	torrentsToRemove = []
	torrentsHashes = []

	# remove only the torrents that have reached ratio of >=1.0 and have been completed for at least 1 hour, or completed torrents older than 1 week
	for torrent in qbt_client.torrents_info():
		timeDiff = int(time.time()) - torrent.completion_on
		if (torrent.ratio >= QBIT_RATIO_TRESHOLD and torrent.completion_on != 0 and timeDiff >= QBIT_TIME_DELAY) or (torrent.completion_on != 0 and timeDiff >= QBIT_ABSOLUTE_TIME_DELAY):
			if shouldDeleteOnTag(torrent):
				torrentsToRemove.append(torrent)
				torrentsHashes.append(torrent.hash)

	if torrentsToRemove:
		# delete all marked torrents
		qbt_client.torrents_delete(delete_files=True, torrent_hashes=torrentsHashes)
		postStatsToDiscord(torrentsToRemove)


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
	# instantiate a Client using the appropriate WebUI configuration
	try:
		print("Trying to login to QbitTorrent...")
		qbt_client.auth_log_in()
		print("Successfuly connected to QbitTorrent. Listening for potential torrents to delete..")
		while True:
			processTorrents()
			time.sleep(CHECK_INTERVAL)
	except qbittorrentapi.LoginFailed as e:
		print("Invalid login credentials - please check your login credentials - the script will now exit!")
		sys.exit(0)
	except Exception as e:
		print("Cannot find qbitTorrent! Please check to see if the webUI has been enabled. If running a docker container, check to see if it's alive. The script will check availability in 1 minute. ", e)
		time.sleep(60)
		main()


main()
