---
project: sp-cli
sources:
  primary: docs/CLI-short.md
  other:
    - README.md
    - docs/Reference.md
created_at: 2024-12-31 13:20:46.144276+00:00
---

## Summary
Spaceport CLI (sp) is a command line tool for managing workspaces and projects, and for generating and testing executable specifications. It provides commands for:
- Initializing workspaces
- Adding/renaming projects
- Generating executable specifications and test code
- Running tests
- Listing projects and specs

## Details
- A workspace is represented by a spaceport.yaml file
- Projects can be added either with an artifact file or with primary/other source files
- Test results can be output in human-readable, JSON, or JUnit XML formats
- The `sp make` command generates executable specs for projects
- The `sp code` command generates test code from specs
- The `sp test` command runs tests for specified specs or all specs in a project

## Open Questions
- What is the format/schema of spaceport.yaml?
- What is the default path pattern for artifact files?
- What is the format of executable specifications?
- What is the format of test code?
- What information is included in the test results output formats?
- Are there any naming constraints for projects and specs?

## Executables
### Workspace Initialization
>> Initialize a new workspace
> - GIVEN:
>   - an empty directory named 'initialize-a-workspace'
>   - verifiable condition for a valid spaceport.yaml file: the `name` field's value is 'initialize-a-workspace'
> - USE a terminal to enter the directory
> - Run `sp init`
> - USE a structured document editor
> - Verify that spaceport.yaml exists and is valid
````py .test
# GIVEN:
# - an empty directory named 'initialize-a-workspace'
# - verifiable condition for a valid spaceport.yaml file: the `name` field's value is 'initialize-a-workspace'

# USE a terminal to enter the directory
T.use("container")
T.set_working_dir("fs//", "initialize-a-workspace")

# Run `sp init`
T.input_text("term//input", "sp init")
T.input_enter("term//input")
T.wait_till_complete("term//")

# USE a structured document editor
T.use("container")

# Verify that spaceport.yaml exists and is valid
T.open_document("sdoc//", "spaceport.yaml")
content, _ = T.read_node("sdoc//name")
assert content == "initialize-a-workspace"
````

### Project Management
>> Add a project with an artifact file
> - GIVEN:
>   - a workspace directory with spaceport.yaml: 'fixtures/sp-cli/add-a-project-with-an-artifact-file'
>   - a project name string: 'project'
>   - an artifact file path: 'project.md'
>   - verifiable condition for project registration in workspace: the first item of the `projects` array has a `name` field with value 'project'
> - USE a terminal
> - Run `sp add {project_name} -a {artifact_path}`
> - USE a structured document editor
> - Verify the project is registered in spaceport.yaml
> - Verify the artifact file exists at the specified path
````py .test
# GIVEN:
# - a workspace directory with spaceport.yaml: 'fixtures/sp-cli/add-a-project-with-an-artifact-file'
# - a project name string: 'project'
# - an artifact file path: 'project.md'
# - verifiable condition for project registration in workspace: the first item of the `projects` array has a `name` field with value 'project'
workspace_dir = 'fixtures/sp-cli/add-a-project-with-an-artifact-file'
project_name = 'project'
artifact_path = 'project.md'

# USE a terminal
T.use("container", copy_from_host=[workspace_dir])
# Run `sp add {project_name} -a {artifact_path}`
T.set_working_dir("term//", workspace_dir)
T.input_text("term//input", f"sp add {project_name} -a {artifact_path}")
T.input_enter("term//input")
T.wait_till_complete("term//")

# USE a structured document editor
T.use("container")
# Verify the project is registered in spaceport.yaml
T.open_document("sdoc//", "spaceport.yaml")
project_data = T.read_node("sdoc//projects/0")
assert project_data[0]["name"] == "project"

# Verify the artifact file exists at the specified path
T.use("container")
assert T.has_some(f"fs//{artifact_path}")
````

>> Add a project with primary and other sources
> - GIVEN:
>   - a workspace directory with spaceport.yaml: 'fixtures/sp-cli/add-a-project-with-primary-and-other-sources'
>   - a project name string: 'project'
>   - a primary source file path: 'primary.md'
>   - multiple other source file paths: 'other.md', 'other2.md'
>   - verifiable condition for project registration in workspace: for the first item of the `projects` array, the `name` field has value 'project', the `sources` field is an object with `primary` field of value 'primary.md', and `other` field of value ['other.md', 'other2.md']
> - USE a terminal
> - Run `sp add {project_name} -p {primary_path} -o {other_path1} -o {other_path2}`
> - USE a structured document editor
> - Verify the project is registered in spaceport.yaml
> - Verify source paths are correctly recorded
````py .test
# GIVEN:
# - a workspace directory with spaceport.yaml: 'fixtures/sp-cli/add-a-project-with-primary-and-other-sources'
# - a project name string: 'project'
# - a primary source file path: 'primary.md'
# - multiple other source file paths: 'other.md', 'other2.md'
# - verifiable condition for project registration in workspace: for the first item of the `projects` array, the `name` field has value 'project', the `primary` field has value 'primary.md', and the `other` field has value ['other.md', 'other2.md']
workspace_dir = 'fixtures/sp-cli/add-a-project-with-primary-and-other-sources'
project_name = 'project'
primary_path = 'primary.md'
other_paths = ['other.md', 'other2.md']

# USE a terminal
T.use("container", copy_from_host=[workspace_dir])
# Run `sp add {project_name} -p {primary_path} -o {other_path1} -o {other_path2}`
T.set_working_dir("fs//", workspace_dir)
cmd = f"sp add {project_name} -p {primary_path} -o {other_paths[0]} -o {other_paths[1]}"
T.input_text("term//input", cmd)
T.input_enter("term//input")
T.wait_till_complete("term//")

# USE a structured document editor
T.use("container")
# Verify the project is registered in spaceport.yaml
T.open_document("sdoc//", "spaceport.yaml")

# Verify the project is registered in spaceport.yaml and source paths are correctly recorded
first_project = T.read_node("sdoc//projects/0")
project_data, _ = first_project
assert project_data["name"] == project_name, "Project name mismatch"
sources_data = project_data["sources"]
assert sources_data["primary"] == primary_path, "Primary source path mismatch"
assert sources_data["other"] == other_paths, "Other source paths mismatch"
````

>> Rename a project
> - GIVEN:
>   - a workspace with an existing project: 'fixtures/sp-cli/rename-a-project'
>   - old project name: 'old-project'
>   - new project name: 'new-project'
>   - verifiable condition for project name update in workspace manifest: for the first item of the `projects` array, the `name` field has value 'new-project'
>   - artifact file: 'sp-projects/new-project.md'
>   - verifiable condition for artifact file: the text contains 'project: new-project'
> - USE a terminal
> - Run `sp rename {old_name} {new_name}`
> - USE a structured document editor
> - Verify project name is updated in spaceport.yaml
> - Verify artifact file is updated if it exists
````py .test
# GIVEN:
# - a workspace with an existing project: 'fixtures/sp-cli/rename-a-project'
# - old project name: 'old-project'
# - new project name: 'new-project'
# - verifiable condition for project name update in workspace manifest: for the first item of the `projects` array, the `name` field has value 'new-project'
# - artifact file: 'sp-projects/new-project.md'
# - verifiable condition for artifact file: the text contains 'project: new-project'
workspace_path = 'fixtures/sp-cli/rename-a-project'
old_name = 'old-project'
new_name = 'new-project'
artifact_path = 'sp-projects/new-project.md'

# USE a terminal
T.use("container", copy_from_host=[workspace_path])
# Run `sp rename {old_name} {new_name}`
T.set_working_dir("fs//", workspace_path)
T.input_text("term//input", f"sp rename {old_name} {new_name}")
T.input_enter("term//input")
T.wait_till_complete("term//")

# USE a structured document editor
T.use("container")
# Verify project name is updated in spaceport.yaml
T.open_document("sdoc//", "spaceport.yaml")
first_project = T.read_node("sdoc//projects/0")
assert first_project[0]["name"] == new_name

# Verify artifact file is updated if it exists
assert T.has_some("fs//sp-projects/new-project.md")
content = T.read_text("fs//sp-projects/new-project.md", "utf-8")
assert "project: new-project" in content
````

### Specification Generation
>> Generate specs for specific projects
> - GIVEN:
>   - a workspace with multiple projects
>   - list of project names
>   - verifiable condition for generated specs
> - USE a terminal
> - Run `sp make {project1} {project2}`
> - Verify specs are generated for specified projects

>> Generate specs for all projects
> - GIVEN:
>   - a workspace with multiple projects
>   - verifiable condition for generated specs
> - USE a terminal
> - Run `sp make --all`
> - Verify specs are generated for all projects

### Test Code Generation
>> Generate test code for specific specs in a project
> - GIVEN:
>   - a workspace with a project
>   - project name
>   - list of spec names
>   - verifiable condition for generated test code
> - USE a terminal
> - Run `sp code {project} -s {spec1} -s {spec2}`
> - Verify test code is generated for specified specs

>> Generate test code for all specs in multiple projects
> - GIVEN:
>   - a workspace with multiple projects
>   - list of project names
>   - verifiable condition for generated test code
> - USE a terminal
> - Run `sp code {project1} {project2}`
> - Verify test code is generated for all specs in specified projects

### Testing
>> Run tests for specific specs with JSON output
> - GIVEN:
>   - a workspace with a project
>   - list of spec names
>   - output JSON file path
>   - verifiable condition for test execution
>   - verifiable condition for JSON output format
> - USE a terminal
> - Run `sp test {project} -s {spec1} -s {spec2} --json {output_path}`
> - USE a structured document editor
> - Verify tests are executed for specified specs
> - Verify JSON output is generated at specified path with correct format

>> Run tests for all specs with JUnit XML output
> - GIVEN:
>   - a workspace with a project
>   - output XML file path
>   - verifiable condition for test execution
>   - verifiable condition for JUnit XML output format
> - USE a terminal
> - Run `sp test {project} --junit-xml {output_path}`
> - USE a structured document editor
> - Verify tests are executed for all specs
> - Verify JUnit XML output is generated at specified path with correct format

### Project Listing
>> List all projects
> - GIVEN:
>   - a workspace with multiple projects
>   - verifiable condition for project listing format
> - USE a terminal
> - Run `sp list`
> - Verify output shows all projects and their specs

>> List specific projects
> - GIVEN:
>   - a workspace with multiple projects
>   - list of project names
>   - verifiable condition for project listing format
> - USE a terminal
> - Run `sp list {project1} {project2}`
> - Verify output shows specified projects and their specs
