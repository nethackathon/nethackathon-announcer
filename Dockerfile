from alpine:3

label org.opencontainers.image.authors="danielkinsman@riseup.net"
label org.opencontainers.licenses="MIT"
label org.opencontainers.image.source="https://gitlab.com/DanielKinsman/nethack-announcer"
label org.opencontainers.image.url="https://gitlab.com/DanielKinsman/nethack-announcer"
label org.opencontainers.version="0.0.1"

run apk add --no-cache py3-virtualenv

copy main.py /opt/main.py
copy requirements.txt /opt/requirements.txt

run virtualenv /opt/nh
run /opt/nh/bin/pip install --no-cache -r /opt/requirements.txt

cmd ["/opt/nh/bin/python", "/opt/main.py"]
