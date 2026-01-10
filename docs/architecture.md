# CodeAtlas Architecture

## C4 Model

> **Note:** The C4 diagrams below use Mermaid's C4 syntax. If your MkDocs setup doesn't support C4 diagrams, you may need to install the `mermaid-c4` plugin or use the alternative diagrams provided in the sections below.

### Level 1: System Context

```mermaid
C4Context
    title System Context Diagram for CodeAtlas
    
    Person(developer, "Developer", "Uses CodeAtlas to generate documentation for repositories")
    System(codeatlas, "CodeAtlas", "Automated documentation generation system for Git repositories")
    System_Ext(github, "GitHub", "Git repository hosting and API")
    System_Ext(ollama, "Ollama", "LLM inference server for documentation generation")
    
    Rel(developer, codeatlas, "Runs CLI or triggers via", "GitHub Actions")
    Rel(codeatlas, github, "Forks/clones repos, creates PRs", "HTTPS/API")
    Rel(codeatlas, ollama, "Generates documentation", "HTTP API")
    
    UpdateRelStyle(developer, codeatlas, $offsetX="-10", $offsetY="-20")
    UpdateRelStyle(codeatlas, github, $offsetX="10", $offsetY="10")
    UpdateRelStyle(codeatlas, ollama, $offsetX="-10", $offsetY="10")
```

### Level 2: Container Diagram

```mermaid
C4Container
    title Container Diagram for CodeAtlas
    
    Person(developer, "Developer")
    System_Ext(github, "GitHub")
    System_Ext(ollama, "Ollama")
    
    Container_Boundary(c1, "CodeAtlas Application") {
        Container(cli, "CLI Application", "Python CLI", "Entry point, orchestrates workflow")
        Container(repo_mgr, "Repository Manager", "Python", "Handles forking, cloning, file collection")
        Container(dep_analyzer, "Dependency Analyzer", "Python", "Extracts file dependencies")
        Container(doc_gen, "Documentation Generator", "Python", "Generates docs using LLM")
        Container(site_builder, "MkDocs Site Builder", "Python", "Creates/updates MkDocs configuration")
        Container(publisher, "Git Publisher", "Python", "Commits and pushes changes")
        Container(review_mgr, "Review Manager", "Python", "Creates review branches and PRs")
    }
    
    Rel(developer, cli, "Executes", "Command line")
    Rel(cli, repo_mgr, "Uses")
    Rel(cli, dep_analyzer, "Uses")
    Rel(cli, doc_gen, "Uses")
    Rel(cli, site_builder, "Uses")
    Rel(cli, publisher, "Uses")
    Rel(cli, review_mgr, "Uses")
    
    Rel(repo_mgr, github, "Fork/clone repos", "HTTPS/API")
    Rel(review_mgr, github, "Create PRs", "REST API")
    Rel(publisher, github, "Push commits", "Git/HTTPS")
    Rel(doc_gen, ollama, "Generate documentation", "HTTP API")
    Rel(doc_gen, dep_analyzer, "Gets dependency context")
```

### Level 3: Component Diagram - Documentation Generator

```mermaid
C4Component
    title Component Diagram - Documentation Generator Container
    
    Container_Boundary(doc_gen, "Documentation Generator") {
        Component(config_loader, "Config Loader", "Python", "Loads model configuration from YAML")
        Component(client_factory, "Ollama Client Factory", "Python", "Creates HTTP clients for Ollama instances")
        Component(file_filter, "File Filter", "Python", "Filters files that need documentation")
        Component(prompt_builder, "Prompt Builder", "Python", "Builds LLM prompts with context")
        Component(llm_client, "LLM Client", "Python", "Calls Ollama API for documentation")
        Component(diagram_gen, "Diagram Generator", "Python", "Generates Mermaid diagrams")
        Component(markdown_renderer, "Markdown Renderer", "Python", "Renders final documentation")
        Component(dep_context, "Dependency Context Provider", "Python", "Provides dependency information")
    }
    
    System_Ext(ollama, "Ollama")
    ContainerDb(config_file, "models.yaml", "YAML", "Model configuration")
    Container(repo_info, "RepoInfo", "Data", "Repository metadata")
    Container(dep_analyzer, "Dependency Analyzer")
    
    Rel(config_loader, config_file, "Reads")
    Rel(client_factory, config_loader, "Uses config")
    Rel(file_filter, repo_info, "Filters files from")
    Rel(prompt_builder, repo_info, "Uses file info")
    Rel(prompt_builder, dep_context, "Gets context")
    Rel(dep_context, dep_analyzer, "Queries")
    Rel(llm_client, client_factory, "Uses client")
    Rel(llm_client, ollama, "Calls API", "HTTP")
    Rel(diagram_gen, ollama, "Calls API", "HTTP")
    Rel(markdown_renderer, llm_client, "Uses output")
    Rel(markdown_renderer, diagram_gen, "Includes diagrams")
```

### Level 3: Component Diagram - Repository Manager

```mermaid
C4Component
    title Component Diagram - Repository Manager Container
    
    Container_Boundary(repo_mgr, "Repository Manager") {
        Component(fork_handler, "Fork Handler", "Python", "Creates/manages GitHub forks")
        Component(clone_manager, "Clone Manager", "Python", "Clones or opens repositories")
        Component(file_collector, "File Collector", "Python", "Collects and catalogs repository files")
        Component(language_detector, "Language Detector", "Python", "Detects programming language")
        Component(changed_files, "Changed Files Detector", "Python", "Detects changed files in PRs/pushes")
    }
    
    System_Ext(github, "GitHub API")
    ContainerDb(local_repo, "Local Repository", "Git", "Cloned repository on disk")
    Container(repo_info, "RepoInfo", "Data", "Repository metadata")
    
    Rel(fork_handler, github, "Creates forks", "REST API")
    Rel(clone_manager, github, "Clones repos", "HTTPS")
    Rel(clone_manager, local_repo, "Manages")
    Rel(file_collector, local_repo, "Scans files")
    Rel(language_detector, file_collector, "Detects language")
    Rel(changed_files, local_repo, "Analyzes git history")
    Rel(repo_info, file_collector, "Stores file list")
    Rel(repo_info, clone_manager, "Stores path")
```

### Deployment Diagram

```mermaid
C4Deployment
    title Deployment Diagram for CodeAtlas
    
    Deployment_Node(dev_machine, "Developer Machine", "Local development environment") {
        Container(codeatlas_cli, "CodeAtlas CLI", "Python", "Command-line application")
    }
    
    Deployment_Node(gh_actions, "GitHub Actions Runner", "CI/CD environment") {
        Container(codeatlas_ga, "CodeAtlas", "Python", "GitHub Actions workflow")
    }
    
    Deployment_Node(ollama_server, "Ollama Server", "Local or remote") {
        ContainerDb(ollama, "Ollama", "Docker/Service", "LLM inference server")
    }
    
    Deployment_Node(github_cloud, "GitHub Cloud", "SaaS") {
        SystemDb(github_api, "GitHub API", "REST API", "Repository management")
        SystemDb(github_repos, "Git Repositories", "Git", "Source code repositories")
    }
    
    Deployment_Node(local_storage, "Local Storage", "File system") {
        ContainerDb(workspaces, "Workspaces", "Directory", "Cloned repositories")
        ContainerDb(docs, "Generated Docs", "Markdown", "Documentation files")
    }
    
    Rel(codeatlas_cli, ollama, "Generates docs", "HTTP")
    Rel(codeatlas_cli, github_api, "Fork/clone", "HTTPS")
    Rel(codeatlas_cli, workspaces, "Stores repos")
    Rel(codeatlas_cli, docs, "Writes docs")
    
    Rel(codeatlas_ga, ollama, "Generates docs", "HTTP")
    Rel(codeatlas_ga, github_api, "Fork/clone", "HTTPS")
    Rel(codeatlas_ga, github_repos, "Works with", "Git")
    Rel(codeatlas_ga, docs, "Writes docs")
    
    Rel(github_api, github_repos, "Manages")
```

### Alternative C4 Diagrams (Standard Mermaid)

If C4-specific syntax isn't supported, here are alternative diagrams using standard Mermaid:

#### System Context (Alternative)

```mermaid
graph TB
    subgraph "External Systems"
        Developer[👤 Developer]
        GitHub[🐙 GitHub<br/>Repository Hosting]
        Ollama[🤖 Ollama<br/>LLM Server]
    end
    
    subgraph "CodeAtlas System"
        CodeAtlas[CodeAtlas<br/>Documentation Generator]
    end
    
    Developer -->|"Runs CLI or triggers"| CodeAtlas
    CodeAtlas -->|"Fork/clone repos<br/>Create PRs"| GitHub
    CodeAtlas -->|"Generate documentation"| Ollama
    
    style CodeAtlas fill:#4a90e2,stroke:#2e5c8a,color:#fff
    style Developer fill:#e8f4f8
    style GitHub fill:#e8f4f8
    style Ollama fill:#e8f4f8
```

#### Container Diagram (Alternative)

```mermaid
graph TB
    subgraph "CodeAtlas Application"
        CLI[CLI Application<br/>Entry Point]
        RepoMgr[Repository Manager<br/>Fork/Clone]
        DepAnalyzer[Dependency Analyzer<br/>Extract Dependencies]
        DocGen[Documentation Generator<br/>LLM Integration]
        SiteBuilder[MkDocs Site Builder<br/>Configuration]
        Publisher[Git Publisher<br/>Commit/Push]
        ReviewMgr[Review Manager<br/>PR Creation]
    end
    
    subgraph "External Systems"
        GitHub[GitHub API]
        Ollama[Ollama LLM]
    end
    
    CLI --> RepoMgr
    CLI --> DepAnalyzer
    CLI --> DocGen
    CLI --> SiteBuilder
    CLI --> Publisher
    CLI --> ReviewMgr
    
    RepoMgr --> GitHub
    ReviewMgr --> GitHub
    Publisher --> GitHub
    DocGen --> Ollama
    DocGen --> DepAnalyzer
    
    style CLI fill:#4a90e2,stroke:#2e5c8a,color:#fff
    style RepoMgr fill:#7b9acc
    style DepAnalyzer fill:#7b9acc
    style DocGen fill:#7b9acc
    style SiteBuilder fill:#7b9acc
    style Publisher fill:#7b9acc
    style ReviewMgr fill:#7b9acc
    style GitHub fill:#e8f4f8
    style Ollama fill:#e8f4f8
```

## Class Diagram

```mermaid
classDiagram
    class CLI {
        +cli(argv)
        +cli_mode(args, config_path)
        +github_actions_mode(args, config_path)
        +parse_github_event() dict
    }

    class RepoManager {
        -repo_url: str
        -fork_owner: str
        -workdir: Path
        -token: str
        -session: httpx.Client
        +prepare_repo(branch) RepoInfo
        -_ensure_fork() str
        -_clone_or_open() Path
        -_collect_files() Iterable[FileRecord]
        +has_existing_docs() bool
        +get_changed_files() list[str]
    }

    class FileRecord {
        +rel_path: str
        +language: str
        +size_bytes: int
    }

    class RepoInfo {
        +source_url: str
        +fork_owner: str
        +repo_name: str
        +path: Path
        +branch: str
        +fork_url: str
        +files: list[FileRecord]
        +token: str
        +dependency_analyzer: DependencyAnalyzer
    }

    class DependencyAnalyzer {
        -repo_info: RepoInfo
        -dependencies: dict
        -dependents: dict
        +analyze()
        +get_file_dependencies() list[str]
        +get_file_dependents() list[str]
        -_extract_dependencies() list[str]
        -_resolve_python_module() str
        -_resolve_js_module() str
        -_resolve_rust_module() str
        -_resolve_go_package() str
    }

    class DocumentationGenerator {
        -config_path: Path
        -config: dict
        -clients: dict
        -diagram_client: Client
        -max_chars: int
        +generate(repo_info) list[Path]
        -_load_config() dict
        -_client_for() Client
        -_build_prompt() str
        -_get_dependency_context() dict
        -_generate_diagram() str
        -_render_markdown() str
    }

    class ModelConfig {
        +name: str
        +instance: str
        +default: bool
    }

    class MkDocsSite {
        -repo_info: RepoInfo
        -docs_root: Path
        -mkdocs_file: Path
        +ensure_site_structure(generated_docs)
        -_discover_docs() list[Path]
        -_build_code_nav() list[dict]
        -_load_config() dict
    }

    class Publisher {
        -repo_info: RepoInfo
        -repo: pygit2.Repository
        -author_name: str
        -author_email: str
        +commit_and_optionally_push()
        +build_mkdocs_site() bool
        -_stage_changes() bool
        -_commit() str
        -_push()
    }

    class ReviewManager {
        -repo_info: RepoInfo
        -repo: pygit2.Repository
        -token: str
        -session: httpx.Client
        +create_review_branch() str
        +create_review_pr() str
        +push_review_branch() bool
    }

    CLI --> RepoManager : creates
    CLI --> DependencyAnalyzer : creates
    CLI --> DocumentationGenerator : creates
    CLI --> MkDocsSite : creates
    CLI --> Publisher : creates
    CLI --> ReviewManager : creates

    RepoManager --> RepoInfo : creates
    RepoManager --> FileRecord : creates

    DependencyAnalyzer --> RepoInfo : uses
    DependencyAnalyzer --> FileRecord : uses

    DocumentationGenerator --> RepoInfo : uses
    DocumentationGenerator --> FileRecord : uses
    DocumentationGenerator --> ModelConfig : uses
    DocumentationGenerator --> DependencyAnalyzer : uses

    MkDocsSite --> RepoInfo : uses
    Publisher --> RepoInfo : uses
    ReviewManager --> RepoInfo : uses

    RepoInfo --> FileRecord : contains
    RepoInfo --> DependencyAnalyzer : references
```

## Component Flow Diagram

```mermaid
flowchart TD
    Start([CLI Entry Point]) --> Mode{Execution Mode?}
    Mode -->|CLI| CLIMode[CLI Mode]
    Mode -->|GitHub Actions| GAMode[GitHub Actions Mode]
    
    CLIMode --> RepoMgr[RepoManager.prepare_repo]
    GAMode --> RepoMgr
    
    RepoMgr --> Fork[Fork Repository]
    Fork --> Clone[Clone Repository]
    Clone --> Collect[Collect Files]
    Collect --> RepoInfo[Create RepoInfo]
    
    RepoInfo --> DepAnalyzer[DependencyAnalyzer.analyze]
    DepAnalyzer --> ExtractDeps[Extract Dependencies]
    ExtractDeps --> BuildGraph[Build Dependency Graph]
    BuildGraph --> AttachAnalyzer[Attach to RepoInfo]
    
    AttachAnalyzer --> DocGen[DocumentationGenerator.generate]
    DocGen --> FilterFiles[Filter Undocumented Files]
    FilterFiles --> ForEachFile{For Each File}
    
    ForEachFile --> ReadContent[Read File Content]
    ReadContent --> GetDeps[Get Dependency Context]
    GetDeps --> BuildPrompt[Build LLM Prompt]
    BuildPrompt --> CallLLM[Call Ollama LLM]
    CallLLM --> GenDiagram[Generate Mermaid Diagram]
    GenDiagram --> RenderMD[Render Markdown]
    RenderMD --> WriteDoc[Write Documentation File]
    
    WriteDoc --> MoreFiles{More Files?}
    MoreFiles -->|Yes| ForEachFile
    MoreFiles -->|No| MkDocs[MkDocsSite.ensure_site_structure]
    
    MkDocs --> CreateConfig[Create/Update mkdocs.yml]
    CreateConfig --> BuildNav[Build Navigation]
    
    BuildNav --> ReviewMode{Review PR Mode?}
    ReviewMode -->|Yes| ReviewMgr[ReviewManager.create_review_branch]
    ReviewMode -->|No| Publisher[Publisher.commit_and_optionally_push]
    
    ReviewMgr --> CreateBranch[Create Review Branch]
    CreateBranch --> Commit[Commit Changes]
    Commit --> PushBranch[Push Branch]
    PushBranch --> CreatePR[Create Pull Request]
    
    Publisher --> Stage[Stage Changes]
    Stage --> Commit2[Commit Changes]
    Commit2 --> Push{Push?}
    Push -->|Yes| PushRemote[Push to Remote]
    Push -->|No| BuildSite[Build MkDocs Site]
    PushRemote --> BuildSite
    
    BuildSite --> End([Complete])
    CreatePR --> End
```

## Module Dependencies

```mermaid
graph TB
    subgraph "Main Entry"
        main[main.py]
    end
    
    subgraph "Ingest Module"
        ingest[ingest/git_repo.py]
        RepoManager[RepoManager]
        RepoInfo[RepoInfo]
        FileRecord[FileRecord]
    end
    
    subgraph "Dependencies Module"
        deps[deps/analyzer.py]
        DependencyAnalyzer[DependencyAnalyzer]
    end
    
    subgraph "LLM Module"
        llm[llm/generate_docs.py]
        DocumentationGenerator[DocumentationGenerator]
        ModelConfig[ModelConfig]
    end
    
    subgraph "Documentation Module"
        docs[docs/site.py]
        MkDocsSite[MkDocsSite]
    end
    
    subgraph "Publish Module"
        publish[publish/git_ops.py]
        Publisher[Publisher]
    end
    
    subgraph "Review Module"
        review[review/review_manager.py]
        ReviewManager[ReviewManager]
    end
    
    main --> ingest
    main --> deps
    main --> llm
    main --> docs
    main --> publish
    main --> review
    
    ingest --> RepoManager
    ingest --> RepoInfo
    ingest --> FileRecord
    
    deps --> DependencyAnalyzer
    deps -.-> ingest
    
    llm --> DocumentationGenerator
    llm --> ModelConfig
    llm -.-> ingest
    llm -.-> deps
    
    docs --> MkDocsSite
    docs -.-> ingest
    
    publish --> Publisher
    publish -.-> ingest
    
    review --> ReviewManager
    review -.-> ingest
```

