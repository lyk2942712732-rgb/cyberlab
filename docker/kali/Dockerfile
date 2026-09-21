FROM kalilinux/kali-rolling:latest
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    kali-defaults xfce4 xfce4-terminal dbus-x11 \
    tigervnc-standalone-server tigervnc-common novnc websockify \
    python3 curl wget ca-certificates iproute2 iputils-ping \
    nmap netcat-openbsd sqlmap gobuster ffuf nikto burpsuite firefox-esr \
    fonts-dejavu fonts-noto-cjk procps \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash student \
    && mkdir -p /home/student/.config/xfce4 /home/student/.local/share \
    && chown -R student:student /home/student
COPY start.sh /usr/local/bin/start-desktop
COPY check_desktop.py /usr/local/bin/check-desktop.py
RUN chmod 755 /usr/local/bin/start-desktop
USER student
WORKDIR /home/student
ENV DISPLAY=:1 HOME=/home/student
HEALTHCHECK --interval=5s --timeout=10s --start-period=15s --retries=10 \
    CMD python3 /usr/local/bin/check-desktop.py
ENTRYPOINT ["/usr/local/bin/start-desktop"]
