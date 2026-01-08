FROM alpine

RUN apk update && apk add dropbear tcpdump coreutils libcap-setcap
RUN adduser -D -H -s /bin/ash -h / -G root test_user && \
    ash -c "echo test_user:test_password | chpasswd" && \
    setcap cap_net_raw,cap_net_admin=eip $(which tcpdump)
EXPOSE 10022/tcp
HEALTHCHECK --interval=10s --timeout=1s CMD netstat -tlpn | grep 10022 || exit 1
ENTRYPOINT /bin/ash -c "/usr/sbin/dropbear -B -R -j -k -m -p 0.0.0.0:10022; ping -4 localhost > /tmp/ping.log"