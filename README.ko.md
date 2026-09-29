# MultiAgentOS

**로컬 우선(Local-first), GitHub 네이티브 AI 개발을 위한 기반 플랫폼입니다.**

MultiAgentOS는 **VYRELON**을 위한 기반 런타임이자 멀티 에이전트 개발 오케스트레이터입니다. 대화형 AI가 실제 프로젝트와 작업할 수 있도록 하면서, 원격 GitHub 저장소와 개발자의 로컬 프로젝트 사이의 경계를 명확하게 유지합니다.

> **두 연결은 서로 다른 역할을 합니다.**
> - **GitHub URL → ChatGPT GitHub 앱 → 원격 GitHub 저장소**
> - **VYRELON → MCP / Secure MCP Tunnel → 로컬 프로젝트**
>
> GitHub 연결은 작업 대상이 되는 원격 저장소를 지정하고 접근하게 합니다. VYRELON은 로컬 파일시스템, 패치, 프로세스 및 실행 권한의 경계를 제공합니다.

**Documentation:** [English](README.md) · [한국어](README.ko.md)

## 핵심 개념

- **Local-first** — 파일시스템, shell/process, Git을 로컬 개발의 핵심으로 다룹니다.
- **GitHub-native** — repository, branch, commit, issue, pull request, review, CI 흐름을 지원합니다.
- **Chat-Agent agnostic** — ChatGPT를 기본 대화형 에이전트로 사용하면서 Gemini, Claude 및 다른 provider를 연결할 수 있습니다.
- **Policy-controlled writes** — 파일, Git, GitHub 변경은 VYRELON 정책과 명시적인 권한 경계를 따릅니다.
- **Executable lifecycle** — Understand → Plan → Delegate → Execute → Verify → Review → Handoff 흐름을 지원합니다.

## GitHub와 VYRELON의 관계

가장 중요한 개념은 **GitHub 연결과 로컬 연결은 같은 것이 아니라는 것**입니다.

```text
                  MultiAgentOS
                       |
            +----------+----------+
            |                     |
            v                     v
       GitHub 경로            Local 경로
            |                     |
 GitHub URL / repository      VYRELON runtime
            |                     |
 ChatGPT GitHub app       MCP / Secure MCP Tunnel
            |                     |
            v                     v
     원격 GitHub 저장소          로컬 프로젝트
```

**GitHub URL은 로컬 프로젝트 연결이 아닙니다.**

GitHub URL 또는 repository name은 ChatGPT GitHub 연결에서 **어떤 원격 저장소를 대상으로 작업할지** 알려주는 식별자입니다.

반대로 **VYRELON은 로컬 실행 경계**입니다. 명시적으로 허용된 경우 다음과 같은 로컬 capability를 제공합니다.

- filesystem READ / WRITE
- `patch.apply`
- shell/process 실행
- 로컬 테스트 실행
- MCP tool surface

## ChatGPT + GitHub 사용 방법

1. ChatGPT에서 **Settings → Apps**를 엽니다. 일부 화면에서는 이전 Plugins 명칭이 사용될 수 있습니다.
2. **GitHub** 앱을 연결하고 GitHub 인증을 완료합니다.
3. ChatGPT가 검색할 수 있는 repository 접근 권한을 부여합니다.
4. 새 ChatGPT 대화를 시작합니다.
5. 대화에서 **GitHub URL 또는 repository name을 한 번 지정**합니다.
6. 그 repository를 대상으로 수행할 작업을 요청합니다.

예:

> `https://github.com/eaglesjo/MultiAgentOS`를 확인하고 현재 VYRELON 연결 모델과 첫 릴리즈 README 개선점을 분석해줘.

새 대화에서 repository URL/name을 지정하는 것은 **원격 GitHub 저장소를 현재 대화의 작업 대상으로 식별하는 것**입니다.

그 자체로 로컬 파일시스템 접근 권한이 생기는 것은 아닙니다.

## VYRELON + 로컬 프로젝트

독립 실행:

```bash
python -m pip install multiagentos

cd your-project
multiagentos init . --component all
multiagentos status .
```

로컬 MCP 서버:

```bash
multiagentos mcp serve --path /absolute/path/to/project
```

기본 MCP surface는 read-only입니다.

쓰기 및 process capability가 필요한 경우:

```bash
multiagentos mcp serve \
  --path /absolute/path/to/project \
  --allow-write \
  --allow-process
```

## ChatGPT/Codex + 로컬 VYRELON

Secure MCP Tunnel을 사용하면 ChatGPT/Codex에서 로컬 VYRELON MCP 서버에 접근하는 연결 경로를 구성할 수 있습니다.

```text
ChatGPT / Codex
       |
       v
Secure MCP Tunnel
       |
       v
 tunnel-client
       |
       v
VYRELON MCP Server
       |
       v
Local Project
```

**Tunnel은 새로운 MCP 서버가 아닙니다.** 동일한 VYRELON MCP 서버를 원격 클라이언트가 사용할 수 있도록 연결하는 transport/connection infrastructure입니다.

## Cost-free baseline

MultiAgentOS의 핵심 로컬 개발 경로는 유료 AI provider API key를 필수로 요구하지 않습니다.

VYRELON은 AI provider와 독립적으로 다음을 수행할 수 있습니다.

- filesystem READ / WRITE
- patch application
- process / test execution
- local MCP runtime

자세한 검증 결과는 [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)을 참고하세요.

## CLI

주요 명령:

```bash
multiagentos detect .
multiagentos init . --component all
multiagentos status .
multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
multiagentos chat --path . --objective "inspect the current project"
multiagentos mcp serve --path .
multiagentos github probe OWNER/REPOSITORY
```

## Validation

```bash
python -m unittest discover -s tests -v
```

GitHub Actions에서도 동일한 테스트 경로를 검증합니다.

## Documentation

- [English README](README.md)
- [Getting Started](docs/GETTING_STARTED.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md)
- [VYRELON MCP Architecture](docs/ARCHITECTURE_DECISIONS.md)
- [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)

## Localization

README 번역은 단순 문장 번역이 아니라 **기술 용어와 연결 모델의 의미를 보존하는 것**을 목표로 합니다.

특히 다음 용어는 의미를 변경하지 않습니다.

- VYRELON
- MultiAgentOS
- GitHub
- MCP
- Secure MCP Tunnel
- `patch.apply`
- filesystem
- process
- execution policy
- permission boundary
- Chat Agent
- Model / Agent / Runtime

영문 README를 canonical 문서로 유지하고, 각 locale 문서는 동일한 구조와 기술적 의미를 유지하는 것을 원칙으로 합니다.
