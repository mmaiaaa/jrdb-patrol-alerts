Local JRDB data

Place downloaded JRDB bytes in an ignored subdirectory here, or use an external SSD/data root. All content under `data/` other than this README is excluded by the repository ignore rules. Never use an unrestricted `git add -f` to bypass those rules for dataset content.

Obtain data through [JRDB](https://jrdb.erc.monash.edu/) using your own approved account. Record exact release, streams, sequence IDs, calibration/timestamps, and checksums in `manifests/sequences.csv`. Do not store passwords or signed download URLs in Git.

Start with one development sequence and the sensor/label content needed by the chosen pilot. Package names and storage requirements have not been verified in the authenticated portal. Do not assume every modality is independently downloadable.

Keep raw data immutable once acquired. Store derived data separately, with the input manifest and generating code recorded. No raw JRDB data or labels are included in this starter.
