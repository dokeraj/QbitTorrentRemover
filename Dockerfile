FROM python:alpine3.14

RUN pip3 install qbittorrent-api
RUN pip3 install discord-webhook
RUN pip3 install hurry.filesize

ENV QBIT_LOGIN_USER=admin
ENV QBIT_LOGIN_PASS=adminadmin
ENV QBIT_PORT=3003
ENV QBIT_IP=localhost

ENV QBIT_RATIO_TRESHOLD=1.0
ENV QBIT_TIME_DELAY=3600
ENV QBIT_ABSOLUTE_TIME_DELAY=1209600
ENV QBIT_TAGS=""
ENV QBIT_TRACKERS_WITH_RATIO_TRESHOLD=""
ENV QBIT_ADD_TRACKERS_IN_TAGS=False
ENV QBIT_SET_DEFAULT_QBIT_RATIO=True

ENV DISCORD_WEBHOOK=xxx
ENV CHECK_INTERVAL=300

RUN mkdir /pyScript

ADD qbitTorrentRemover.py /pyScript/

WORKDIR /pyScript/

CMD ["python3", "-u", "/pyScript/qbitTorrentRemover.py"]