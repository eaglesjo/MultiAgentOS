# VYRELON Architecture

VYRELON is local-first. The local runtime owns filesystem, shell/process and Git execution. GitHub is a first-class remote lifecycle through a provider-neutral gateway.

User -> VYRELON -> Work Unit -> Agent Runtime
                         |-> Local Runtime
                         |-> GitHub Gateway -> GitHub

The core depends on GitHubGateway, not on gh, REST, GraphQL or a vendor SDK. The first adapter uses the locally authenticated gh CLI.

Authentication is external to source control. No token or credential is stored in this repository.

Writes will be policy-controlled by Work Unit. Push, PR and merge are separate capabilities.

AI model and agent providers are independent of GitHub access.
