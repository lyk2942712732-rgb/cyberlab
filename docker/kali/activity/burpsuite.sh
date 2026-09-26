#!/bin/sh
# Keep Burp's heap bounded beside Firefox; enable its native accessibility bridge.
exec java -Xms64m -Xmx384m --enable-native-access=ALL-UNNAMED \
  -Xbootclasspath/a:/usr/share/java/java-atk-wrapper.jar \
  -Djavax.accessibility.assistive_technologies=org.GNOME.Accessibility.AtkWrapper \
  -jar /usr/share/burpsuite/burpsuite.jar --suppress-jre-check --disable-check-for-updates-dialog "$@"
