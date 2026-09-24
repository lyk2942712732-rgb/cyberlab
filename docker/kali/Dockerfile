FROM kalilinux/kali-rolling:latest
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    kali-defaults xfce4 xfce4-terminal dbus-x11 \
    tigervnc-standalone-server tigervnc-common novnc websockify \
    python3 python3-venv python3-gi gir1.2-atspi-2.0 at-spi2-core curl wget ca-certificates iproute2 iputils-ping \
    nmap netcat-openbsd sqlmap gobuster ffuf nikto burpsuite firefox-esr \
    fonts-dejavu fonts-noto-cjk procps ffmpeg libportaudio2 libsndfile1 xdotool wmctrl x11-utils gcc libffi-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash student \
    && mkdir -p /home/student/.config/xfce4 /home/student/.local/share \
    && chown -R student:student /home/student
COPY start.sh /usr/local/bin/start-desktop
COPY capture.py /usr/local/bin/cyberlab-capture.py
COPY openadapt-capture.tar.gz /tmp/openadapt-capture.tar.gz
COPY patch_xrecord.py patch_receipts.py patch_xrecord_close.py patch_xrecord_disable.py /tmp/
COPY check_desktop.py /usr/local/bin/check-desktop.py
COPY check_x11.py /usr/local/bin/check_x11.py
COPY --chown=student:student xfwm4.xml /home/student/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml
RUN chmod 755 /usr/local/bin/start-desktop \
    && mkdir -p /opt/openadapt-source /var/lib/cyberlab/captures \
    && tar -xzf /tmp/openadapt-capture.tar.gz -C /opt/openadapt-source --strip-components=1 \
    && python3 -m venv --system-site-packages /opt/openadapt \
    && /opt/openadapt/bin/pip install --no-cache-dir /opt/openadapt-source \
    && capture_pkg=$(/opt/openadapt/bin/python -c 'import openadapt_capture, pathlib; print(pathlib.Path(openadapt_capture.__file__).parent)') \
    && /opt/openadapt/bin/python /tmp/patch_xrecord.py "$capture_pkg/input_observer/linux.py" \
    && /opt/openadapt/bin/python /tmp/patch_receipts.py "$capture_pkg/recorder.py" \
    && /opt/openadapt/bin/python /tmp/patch_xrecord_close.py "$capture_pkg/input_observer/linux.py" \
    && /opt/openadapt/bin/python /tmp/patch_xrecord_disable.py "$capture_pkg/input_observer/linux.py" \
    && rm -rf /tmp/openadapt-capture.tar.gz /tmp/patch_*.py \
    && mkdir -p /usr/share/themes/CyberLab/xfwm4 \
    && cp /usr/share/themes/Default/xfwm4/*.xpm /usr/share/themes/Default/xfwm4/themerc /usr/share/themes/CyberLab/xfwm4/ \
    && chown -R student:student /var/lib/cyberlab
USER student
WORKDIR /home/student
ENV DISPLAY=:1 HOME=/home/student
ENV PATH="/opt/openadapt/bin:\${PATH}" RECORD_AUDIO=false RECORD_BROWSER_EVENTS=false SCREEN_CAPTURE_FPS=5 PLOT_PERFORMANCE=false CYBERLAB_CAPTURE_ROOT=/var/lib/cyberlab/captures
# VNC has no GPU; skip Firefox's unsupported hardware probe without disabling
# Firefox's content sandbox or the container's security restrictions.
ENV MOZ_AVOID_OPENGL_ALTOGETHER=1
HEALTHCHECK --interval=5s --timeout=10s --start-period=15s --retries=10 \
    CMD python3 /usr/local/bin/check-desktop.py
ENTRYPOINT ["/usr/local/bin/start-desktop"]
