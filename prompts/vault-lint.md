Run the LINT operation on the Obsidian vault. Read `vault-config.md` first for vault name and path. Use the Obsidian CLI with the vault name from vault-config.md:

1. `obsidian orphans vault="VAULT_NAME" total`
2. `obsidian unresolved vault="VAULT_NAME" total`
3. `obsidian deadends vault="VAULT_NAME" total`
4. `obsidian tasks vault="VAULT_NAME" todo total`
5. Count root-level files missing type frontmatter
6. Compare with previous health report at the vault's `_llm/status/health.md` to note improvements or regressions
7. Write updated report to the vault's `_llm/status/health.md`
8. Append to the vault's `_llm/log.md`
9. Open in Obsidian: `obsidian open vault="VAULT_NAME" path="_llm/status/health.md"`
