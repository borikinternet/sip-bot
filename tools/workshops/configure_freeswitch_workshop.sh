#!/usr/bin/env bash
set -euo pipefail

readonly vars_file="/etc/freeswitch/vars.xml"
readonly modules_file="/etc/freeswitch/autoload_configs/modules.conf.xml"
readonly packaged_password='default_password=1234'
readonly workshop_password='default_password=Workshop-2026!'
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly project_root="$(cd -- "$script_dir/../.." && pwd)"
readonly workshop_config="$project_root/config/workshops/freeswitch"

install -d -m 0755 /etc/systemd/system/freeswitch.service.d
install -m 0644 \
    "$workshop_config/systemd/freeswitch.service.d/10-workshop-nonat.conf" \
    /etc/systemd/system/freeswitch.service.d/10-workshop-nonat.conf
systemctl daemon-reload

disable_stun_preprocess() {
    local variable_name="$1"
    local directive="<X-PRE-PROCESS cmd=\"stun-set\" data=\"${variable_name}=stun:stun.freeswitch.org\"/>"

    if grep -Fq "<!-- ${directive} -->" "$vars_file"; then
        return
    fi
    if grep -Fq "$directive" "$vars_file"; then
        sed -i "s|${directive}|<!-- ${directive} -->|" "$vars_file"
        return
    fi

    echo "Cannot find the active or disabled ${variable_name} STUN directive in $vars_file" >&2
    exit 1
}

set_external_ip_to_local() {
    local variable_name="$1"
    local stun_directive="<X-PRE-PROCESS cmd=\"stun-set\" data=\"${variable_name}=stun:stun.freeswitch.org\"/>"
    local disabled_stun="<!-- ${stun_directive} -->"
    local local_binding="<X-PRE-PROCESS cmd=\"set\" data=\"${variable_name}=\$\${local_ip_v4}\"/>"

    if grep -Fq "$local_binding" "$vars_file"; then
        return
    fi
    if grep -Fq "$disabled_stun" "$vars_file"; then
        sed -i "s|${disabled_stun}|${disabled_stun}\n  ${local_binding}|" "$vars_file"
        return
    fi

    echo "Cannot bind ${variable_name} to local_ip_v4 in $vars_file" >&2
    exit 1
}

disable_stun_preprocess external_rtp_ip
disable_stun_preprocess external_sip_ip
set_external_ip_to_local external_rtp_ip
set_external_ip_to_local external_sip_ip

if grep -Fq "$workshop_password" "$vars_file"; then
    :
elif grep -Fq "$packaged_password" "$vars_file"; then
    sed -i "s/${packaged_password}/${workshop_password}/" "$vars_file"
else
    echo "Cannot find the packaged or workshop default_password in $vars_file" >&2
    exit 1
fi

if grep -Eq '^[[:space:]]*<load module="mod_callcenter"/>[[:space:]]*$' "$modules_file"; then
    :
elif grep -Eq '^[[:space:]]*<!--<load module="mod_callcenter"/>-->[[:space:]]*$' "$modules_file"; then
    sed -i 's|<!--<load module="mod_callcenter"/>-->|<load module="mod_callcenter"/>|' "$modules_file"
else
    echo "Cannot find the packaged mod_callcenter load marker in $modules_file" >&2
    exit 1
fi

install -m 0644 \
    "$workshop_config/autoload_configs/callcenter.conf.xml" \
    /etc/freeswitch/autoload_configs/callcenter.conf.xml
install -m 0644 \
    "$workshop_config/dialplan/default/20_workshop_callcenter.xml" \
    /etc/freeswitch/dialplan/default/20_workshop_callcenter.xml
install -d -o freeswitch -g freeswitch -m 0750 \
    /var/lib/freeswitch/recordings/sip-bot

systemctl restart freeswitch
systemctl is-active --quiet freeswitch
fs_cli -x status
fs_cli -x 'module_exists mod_callcenter' | grep -Fx true
fs_cli -x 'callcenter_config queue list' | grep -F 'support@default'
fs_cli -x 'callcenter_config queue list' | grep -F 'science-bot@default'
fs_cli -x 'callcenter_config agent list' | grep -F '1001@default'
fs_cli -x 'callcenter_config agent list' | grep -F '1002@default'
fs_cli -x 'callcenter_config tier list' | grep -F '1001@default'
fs_cli -x 'callcenter_config tier list' | grep -F '1002@default'
