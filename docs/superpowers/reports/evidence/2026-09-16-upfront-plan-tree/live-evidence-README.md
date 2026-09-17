# Live upfront plan-tree evidence

`live-plan-tree-result.json` is the validator output for `live-plan-tree-manifest.json` against the
original isolated run directories. The JSONL files are the four operation traces. The five Git
bundles retain complete histories for the normal code/internal-vault repository, bounded external
vault, contract-break code and vault repositories, and legacy vault. `live-role-logs.tar.gz` retains
the complete role-bridge log directory, including the interrupted replanner log.

Verify a bundle with `git bundle verify <bundle>` and inspect it by cloning the bundle into an empty
directory. To replay the validator after the original temporary directories are gone, clone each
bundle, extract the log archive, copy the manifest, and replace its absolute repository/log roots
with those restored paths. The package paths are already relative to this source checkout.

`live-evidence-sha256.txt` covers every retained `live-*` artifact except itself. The `live-final-*`
logs record the final offline gate after enabling the upfront default.
