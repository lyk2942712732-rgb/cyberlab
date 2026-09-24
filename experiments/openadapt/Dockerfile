# Pilot only: keep the production Kali image/tag unchanged.
FROM cyberlab/kali:local
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-venv python3-gi gir1.2-atspi-2.0 at-spi2-core \
    ffmpeg libportaudio2 libsndfile1 xdotool wmctrl x11-utils \
    gcc libffi-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Source snapshot is staged by the build procedure; see README.md.
COPY openadapt-capture.tar.gz /tmp/openadapt-capture.tar.gz
RUN echo "d1ce1c84e7d93a23a3a6b2b8939fe3a7badff3feebf94040ec51d045deb60e13  /tmp/openadapt-capture.tar.gz" | sha256sum -c - \
    && mkdir /opt/openadapt-source \
    && tar -xzf /tmp/openadapt-capture.tar.gz -C /opt/openadapt-source --strip-components=1 \
    && python3 -m venv --system-site-packages /opt/openadapt \
    && /opt/openadapt/bin/pip install --no-cache-dir /opt/openadapt-source \
    && /opt/openadapt/bin/pip freeze > /opt/openadapt-requirements.txt \
    && rm /tmp/openadapt-capture.tar.gz
ENV PATH="/opt/openadapt/bin:${PATH}" \
    RECORD_AUDIO=false RECORD_BROWSER_EVENTS=false SCREEN_CAPTURE_FPS=5 \
    PLOT_PERFORMANCE=false
LABEL cyberlab.experiment="openadapt-pilot" \
    openadapt.source.revision="986ebaeae6700c58b0e523b54471ce8d3ef01925"
COPY patch_xrecord.py /opt/pilot-build/patch_xrecord.py
COPY patch_receipts.py /opt/pilot-build/patch_receipts.py
COPY patch_xrecord_close.py /opt/pilot-build/patch_xrecord_close.py
RUN /opt/openadapt/bin/python /opt/pilot-build/patch_xrecord.py \
    /opt/openadapt/lib/python3.14/site-packages/openadapt_capture/input_observer/linux.py
RUN /opt/openadapt/bin/python /opt/pilot-build/patch_receipts.py /opt/openadapt/lib/python3.14/site-packages/openadapt_capture/recorder.py
RUN /opt/openadapt/bin/python /opt/pilot-build/patch_xrecord_close.py /opt/openadapt/lib/python3.14/site-packages/openadapt_capture/input_observer/linux.py
LABEL openadapt.local.patch="xrecord-create-sync-v1,native-receipt-forwarding-v1,xrecord-data-close-v1"
USER student
