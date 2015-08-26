FROM python:2

MAINTAINER Philip Jay <phil@jay.id.au>

ENV TZ Australia/Melbourne

RUN pip install -U pip lockfile pyserial python-daemon

RUN mkdir /opt/raven
ADD *.py /opt/raven/

VOLUME /data

CMD [ "python", "/opt/raven/raven_reader.py", "-d", "/serial", "-vvv", "-f", "/data/raven.sqlite" ]
