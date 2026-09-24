#!/bin/sh
set -eu
pilot_dir=${1:?Usage: start-pilot.sh /absolute/pilot/directory}
case "$pilot_dir" in /*) ;; *) echo 'Use an absolute path' >&2; exit 1;; esac
test -f "$pilot_dir/probe.py"
test -f "$pilot_dir/export.py"
mkdir -p "$pilot_dir/evidence"
docker run -d --name cyberlab-openadapt-pilot \
  --label cyberlab.experiment=openadapt-pilot \
  --network none --cpus 2 --memory 1536m --memory-swap 1536m \
  --pids-limit 512 --shm-size 256m --cap-drop ALL --cap-add NET_RAW \
  --security-opt no-new-privileges:true \
  --mount "type=bind,src=$pilot_dir/evidence,dst=/evidence" \
  --mount "type=bind,src=$pilot_dir/probe.py,dst=/opt/pilot/probe.py,readonly" \
  --mount "type=bind,src=$pilot_dir/export.py,dst=/opt/pilot/export.py,readonly" \
  cyberlab/kali:openadapt-pilot
docker exec cyberlab-openadapt-pilot python3 /usr/local/bin/check-desktop.py --wait
