#!/bin/sh
set -eu

# This is an explicitly public workshop credential.  It is not a production
# secret and must match the committed SIP_REGISTRATION_PASSWORD constant.
PUBLIC_DEMO_PASSWORD='PUBLIC-DEMO-SIP-PASSWORD'
BASE_CONFIG='/usr/share/freeswitch/conf/vanilla'
RUNTIME_CONFIG='/tmp/sip-bot-freeswitch-config'
RUNTIME_LOG='/tmp/sip-bot-freeswitch-log'
RUNTIME_DB='/tmp/sip-bot-freeswitch-db'

rm -rf "$RUNTIME_CONFIG"
mkdir -p "$RUNTIME_CONFIG"
mkdir -p "$RUNTIME_LOG" "$RUNTIME_DB"
cp -a "$BASE_CONFIG/." "$RUNTIME_CONFIG/"

# The upstream image generates a random password when /etc/freeswitch is
# absent.  We provide a complete deterministic runtime config instead, so no
# generated credential is printed by the image entrypoint.
sed -i "s/default_password=1234/default_password=$PUBLIC_DEMO_PASSWORD/" "$RUNTIME_CONFIG/vars.xml"

# The host publishes SIP/RTP ports to the local machine.  FreeSWITCH binds in
# the container but advertises the published loopback address to WSL clients.
sed -i \
  -e 's#<param name="sip-ip" value="\$\${local_ip_v4}"/>#<param name="sip-ip" value="0.0.0.0"/>#' \
  -e 's#<param name="rtp-ip" value="\$\${local_ip_v4}"/>#<param name="rtp-ip" value="0.0.0.0"/>#' \
  -e 's#<param name="ext-sip-ip" value="\$\${external_sip_ip}"/>#<param name="ext-sip-ip" value="127.0.0.1"/>#' \
  -e 's#<param name="ext-rtp-ip" value="\$\${external_rtp_ip}"/>#<param name="ext-rtp-ip" value="127.0.0.1"/>#' \
  "$RUNTIME_CONFIG/sip_profiles/internal.xml"

# The workshop clients run outside the FreeSWITCH container while reaching it
# through Docker-published loopback ports. Do not classify Docker's bridge
# address as the peer's local network: that would put 172.18.0.2 in the SDP
# sent back to WSL, where it is not routable. With wan_v4.auto the profile
# uses the configured ext-* loopback address for these peers.
sed -i 's#<param name="local-network-acl" value="localnet.auto"/>#<param name="local-network-acl" value="wan_v4.auto"/>#' \
  "$RUNTIME_CONFIG/sip_profiles/internal.xml"

# Docker Desktop's minimal image does not expose an IPv6 listener.  Keep the
# local fs_cli control socket on IPv4 and disable the image's optional
# SignalWire adoption probe, which is outside the workshop scope and would
# otherwise create unrelated external-certificate noise in the logs.
sed -i 's#<param name="listen-ip" value="::"/>#<param name="listen-ip" value="127.0.0.1"/>#' \
  "$RUNTIME_CONFIG/autoload_configs/event_socket.conf.xml"
sed -i '/<load module="mod_signalwire"\/>/d' "$RUNTIME_CONFIG/autoload_configs/modules.conf.xml"

# Keep only the two accounts used by the workshop.  The account password is
# public by design; it is never echoed by this script or queried in logs.
rm -f "$RUNTIME_CONFIG/directory/default/"*.xml
cp /workshop-overlay/directory/default/*.xml "$RUNTIME_CONFIG/directory/default/"

# Replace the broad sample routes with the small explicit workshop route.
rm -f "$RUNTIME_CONFIG/dialplan/default/"*.xml
rm -f "$RUNTIME_CONFIG/dialplan/public/"*.xml
cp /workshop-overlay/dialplan/public/*.xml "$RUNTIME_CONFIG/dialplan/public/"
cp /workshop-overlay/dialplan/00_sip_bot_workshop.xml "$RUNTIME_CONFIG/dialplan/00_sip_bot_workshop.xml"

exec /usr/bin/freeswitch -c -nf -nonat -nonatmap -conf "$RUNTIME_CONFIG" -log "$RUNTIME_LOG" -db "$RUNTIME_DB"
