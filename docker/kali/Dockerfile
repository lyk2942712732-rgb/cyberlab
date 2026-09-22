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
COPY check_x11.py /usr/local/bin/check_x11.py
COPY --chown=student:student xfwm4.xml /home/student/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml
RUN chmod 755 /usr/local/bin/start-desktop \
    && mkdir -p /usr/share/themes/CyberLab/xfwm4 \
    && cp /usr/share/themes/Default/xfwm4/*.xpm /usr/share/themes/Default/xfwm4/themerc /usr/share/themes/CyberLab/xfwm4/
USER student
WORKDIR /home/student
ENV DISPLAY=:1 HOME=/home/student
# VNC has no GPU; skip Firefox's unsupported hardware probe without disabling
# Firefox's content sandbox or the container's security restrictions.
ENV MOZ_AVOID_OPENGL_ALTOGETHER=1
HEALTHCHECK --interval=5s --timeout=10s --start-period=15s --retries=10 \
    CMD python3 /usr/local/bin/check-desktop.py
ENTRYPOINT ["/usr/local/bin/start-desktop"]
