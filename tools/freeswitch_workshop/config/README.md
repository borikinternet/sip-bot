# Local FreeSWITCH workshop fixture

The compose fixture is pinned to `safarov/freeswitch` image digest
`sha256:b31c743f4c911a19687c61e3214968f2a24f93f9d3d667cc26284192e158ffc6`
(FreeSWITCH `1.10.12`). It uses Docker Desktop bridge networking with explicit
local SIP/RTP port publishing; the bot and Baresip use the loopback registrar
URI from the committed MVP constants.

The two directory users are `tester` (the bot) and `peer` (the workshop
caller). Both use the intentionally public credential
`PUBLIC-DEMO-SIP-PASSWORD`; it is not a production secret.
