#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker build -t cyberlab/kali:local docker/kali
docker build -t cyberlab/sqli-basic:v1 docker/targets/sqli-basic
docker save -o sqli-basic.tar cyberlab/sqli-basic:v1
printf '%s\n' 'Images built. Upload sqli-basic.tar from the teaching console.'
