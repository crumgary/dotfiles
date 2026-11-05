# Repeatable Linux and WSL provisioning

Status: proposed for review. Tracks https://github.com/crumgary/dotfiles/issues/3.

## Outcome and scope

A clean Linux or WSL user environment can be set up from versioned configuration,
with an explicit list of required tools, configuration, agent skills, and remaining
manual authentication steps. A read-only doctor explains differences between the
declared environment and the machine. The first acceptance target is a separate,
clean Ubuntu WSL instance, followed by an Ubuntu Linux VM. Broader distribution
and architecture support requires its own acceptance run; existing profile names
do not constitute proof of support.

Keep the existing wsl, devbox, lab, and embedded profiles. Embedded remains a
minimal fallback outside the first complete provisioning acceptance test.
macOS, Windows host installation, VM creation, USB passthrough, VPNs, and lab
networking are outside this workflow. Existing lab_notes infrastructure automation
continues to own infrastructure. This workflow begins with an available user
account, network connectivity, and a supported OS. Required privilege and repository
access are checked before installation.

## Approaches considered

1. Extend the existing dotfiles repositories. Retain chezmoi for managed home
   files, add explicit machine declarations and a small deterministic workflow.
   This preserves current ownership and gives humans and agents the same commands.
   Recommended. The main obligation is tightening current installer behavior.
2. Introduce a separate fleet repository. Centralizes machine operations, but
   creates a fourth configuration owner and a second path for coordinating
   changes. Reconsider if cross-machine service operations become a real need.
3. Move workstation configuration into Ansible. Appropriate for system services
   and infrastructure, but would require a deliberate transfer of home-file
   ownership from chezmoi. Retain Ansible for the existing infrastructure scope.

## Ownership

| Location | Owns |
| --- | --- |
| Public dotfiles | Generic profiles, package/tool declarations, managed home templates, workflow commands, doctor, public examples, generic agent adapters and tests |
| Private personal overlay | Personal machine records, private endpoints, aliases, personal instruction fragments and custom skills |
| Private work overlay | Work machine records, work endpoints and policy, work-specific configuration and custom skills |
| Machine-local state | Selected machine ID, resolved configuration, credentials, sessions, caches, runtime databases, installation receipts |
| lab_notes | Explanations, troubleshooting, hardware/network runbooks, and infrastructure automation |

Inventory entries live entirely in their owning overlay. A machine that enables
both overlays has one inventory record with explicit overlay selections; identity
records are not silently merged. Public-only setup accepts an explicitly supplied
local record using a public example as its schema. There is no dependency on a
fourth repository, a Firstmate path, or the location of a convenience symlink.

The inventory is the versioned source for machine choices. Existing local chezmoi
data is imported once with a reviewable comparison, rather than becoming a second
editable authority. Direct local overrides are reported as drift. Profile package
lists remain in their existing public declaration rather than being duplicated
for every machine.

## Machine records

A schema-versioned TOML record contains a stable machine ID, profile, supported
OS/architecture expectation, overlay selections, enabled agent/tool bundles, and
configuration revision references. Connection aliases are optional private
metadata; local operation is the initial execution model. Hostnames and paths
are not the machine's identity. Paths resolve from the target user's home.

An agent bundle names each required CLI, its version policy, configuration adapter,
custom skill source or upstream repository/subdirectory/revision, and destination.
The resolver rejects two owners of the same destination. External skills use
immutable source revisions and verified content hashes. Harness-maintained plugin
caches and lockfiles are owned through supported installation mechanisms, never
hand-edited or copied indiscriminately.

The initial verified platform is Ubuntu x86_64, in WSL and a Linux VM. Adding
another distribution or architecture requires release-artifact selection and a
clean-system test. OS packages use documented distro versions; exact-version
claims are reserved for tools and skills whose sources support them. Receipts
record the actual installed versions and source revisions.

## Workflow contract

The following are proposed operations, not commands implemented by this change:

- **Doctor:** inspect local declared state, managed-file drift, source checkout
  cleanliness, required command presence/versions, overlay availability,
  instruction/skill destinations, and relevant permissions. Default output is
  paths and findings, with optional structured JSON. It prints no config contents,
  credential values, complete environment, or history. Findings distinguish
  matching, drifted, missing, blocked, and unverified checks. A missing prerequisite
  or incomplete check never counts as success.
- **Plan:** resolve one machine record and locally available revisions; show
  intended file, package, tool, and permission changes plus authentication and
  privilege prerequisites. It does not install, fetch, or apply anything. It
  identifies any unpinned dependency instead of claiming an exact rebuild.
- **Apply:** perform the reviewed plan after checking that its configuration,
  source revisions, and relevant target preconditions still match. Changed
  preconditions require a new plan. Required failures stop dependent stages and
  return failure; explicitly optional components are reported separately.
- **Update:** explicitly fetch and select new source revisions, show changes,
  and generate a new plan. Applying an existing plan does not pull overlay repos
  or silently select newer tools. Dirty/diverged repositories are reported and
  left intact. The workflow never automatically stashes or resets edits.

Doctor and plan must work without modifying target files, repositories, caches,
or chezmoi persistent state, without sudo, network requests, password-manager
invocation, arbitrary template execution, or installer execution. The
implementation must audit and restrict the template-rendering path; merely
wrapping chezmoi status is insufficient to establish this contract. A check that
cannot meet it reports unverified with the reason.

Apply separates acquisition, prerequisite verification, tool installation,
configuration deployment, and post-install verification. Acquisition obtains only
the revisions selected in the plan. Existing chezmoi scripts must be adapted so
their exit status reflects required failures and their overlay installation no
longer pulls implicitly. Interrupted runs resume through verified idempotent
stages. This is not an atomic system transaction: preserve prior managed files
for targeted recovery, and report completed and failed stages. Package rollback
is not promised.

## Agent configuration and secrets

Source instruction fragments have explicit generic, personal, work, and
machine-specific scopes. Each enabled agent receives configuration appropriate
to its documented loading behavior. Render a self-contained instruction file
where cross-file loading is unsupported or unverified; use references only where
their behavior is verified. Different agents do not get competing copies to
edit. Generated targets point back to their versioned sources for maintenance.

MCP definitions and plugin settings separate non-secret configuration from
credentials. Authentication uses the tool's supported login flow or an explicit
secret reference. Private repository access is a bootstrap prerequisite and
missing access produces a resumable blocked stage. Do not copy authentication
tokens, SSH private keys, sessions, shell history, plugin caches, or memory
databases from the current machine. Data backup/restore is a separate operation.
Preserve private runtime directories, including ~/.pi/agent at mode 0700.

## Delivery slices and acceptance

1. **Inventory and doctor:** define the schema, example records, migration of
   existing local selections, and a doctor for current managed files, overlays,
   permissions, and declared required tools. Prove read-only behavior with fixture
   homes and an execution environment that denies writes, network, and subprocesses
   outside the audited allowlist. Include intentionally missing and drifted
   fixtures. Report unverified agent behavior honestly. No live apply in this slice.
2. **Provisioning:** implement plan/apply/update separation and correct required
   failure handling. Test on a clean WSL instance without access to the original
   home, tool caches, or credentials, then repeat on a Linux VM. Verify shell,
   Git identity, editor, and enabled tools; a second apply must make no unexpected
   managed-file or installation changes. Verify missing private access, missing
   privilege, interruption, and unavailable required downloads are actionable
   failures rather than successful bootstrap messages.
3. **Scoped agent configuration:** inventory only deliberately selected agents,
   install pinned skills and supported plugins, and verify actual instruction
   loading using harmless distinct markers for each scope. Verify work-disabled
   machines exclude work content and runtime state remains private and unmanaged.
   A successful process exit or matching symlink alone is insufficient evidence
   that an agent loaded the rules.

Issues #1 and #2 remain linked migration and cleanup work. No existing reconciliation
edits are automatically committed, applied, or moved by this design. Design
approval selects the architecture; implementation proceeds one slice at a time.

## Evidence used

- Public bootstrap.sh, README.md, home/.chezmoi.toml.tmpl, package declarations,
  overlay scripts, agent CLI installer, and profile smoke tests in this checkout.
- Existing personal/work overlay READMEs and the pending reconciliation patch.
- lab_notes/host_tools.adoc, host_dev_setup.adoc, and ansible/README.md: separate
  host tooling, hardware/network setup, and infrastructure responsibilities.
- [chezmoi scripts documentation](https://github.com/twpayne/chezmoi/blob/master/assets/chezmoi.io/docs/user-guide/use-scripts-to-perform-actions.md)
  and [daily operations](https://github.com/twpayne/chezmoi/blob/master/assets/chezmoi.io/docs/user-guide/daily-operations.md),
  retrieved through Context7. Script execution and target preview are separate;
  read-only guarantees require checking more than the absence of apply.
