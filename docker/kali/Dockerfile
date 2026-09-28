FROM kalilinux/kali-rolling:latest
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    kali-defaults xfce4 xfce4-terminal dbus-x11 \
    tigervnc-standalone-server tigervnc-common novnc websockify \
    python3 python3-gi python3-xlib gir1.2-atspi-2.0 at-spi2-core libatk-wrapper-java libatk-wrapper-java-jni curl wget ca-certificates iproute2 iputils-ping \
    nmap netcat-openbsd sqlmap gobuster ffuf nikto burpsuite firefox-esr \
    fonts-dejavu fonts-noto-cjk procps xdotool wmctrl x11-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash student \
    && mkdir -p /home/student/.config/xfce4 /home/student/.local/share \
    && chown -R student:student /home/student
COPY start.sh /usr/local/bin/start-desktop
COPY activity/ /usr/local/lib/cyberlab-activity/
COPY check_desktop.py /usr/local/bin/check-desktop.py
COPY check_x11.py /usr/local/bin/check_x11.py
COPY --chown=student:student xfwm4.xml /home/student/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml
RUN chmod 755 /usr/local/bin/start-desktop \
    && mkdir -p /var/lib/cyberlab/activity \
    && chmod 755 /usr/local/lib/cyberlab-activity/emit.py \
    && install -m 755 /usr/local/lib/cyberlab-activity/burpsuite.sh /usr/local/bin/burpsuite \
    && python3 /usr/local/lib/cyberlab-activity/install.py \
    && mkdir -p /usr/share/themes/CyberLab/xfwm4 \
    && cp /usr/share/themes/Default/xfwm4/*.xpm /usr/share/themes/Default/xfwm4/themerc /usr/share/themes/CyberLab/xfwm4/ \
    && chown -R student:student /var/lib/cyberlab
USER student
WORKDIR /home/student
ENV DISPLAY=:1 HOME=/home/student
ENV CYBERLAB_ACTIVITY_ROOT=/var/lib/cyberlab/activity NO_AT_BRIDGE=0 MOZ_ACCESSIBILITY_ATSPI_ENABLED=1
# VNC has no GPU; skip Firefox's unsupported hardware probe without disabling
# Firefox's content sandbox or the container's security restrictions.
ENV MOZ_AVOID_OPENGL_ALTOGETHER=1
HEALTHCHECK --interval=20s --timeout=15s --start-period=30s --retries=30 \
    CMD python3 /usr/local/bin/check-desktop.py
ENTRYPOINT ["/usr/local/bin/start-desktop"]
