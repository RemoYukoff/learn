# Incident severity levels

## SEV1

Complete outage of a production service or data loss affecting any customer. The on-call engineer must acknowledge within 5 minutes. An incident commander is assigned immediately and status page updates are posted every 30 minutes.

## SEV2

Major degradation: a core feature is unavailable or latency is more than 5 times the baseline for more than 10 minutes. Acknowledge within 15 minutes, status page updates every hour.

## SEV3

Minor issue with a workaround, or a non-core feature unavailable. Acknowledge within 4 business hours. No status page update is required.

## Postmortems

Every SEV1 and SEV2 needs a blameless postmortem published within 5 business days, with action items that have owners and due dates.
