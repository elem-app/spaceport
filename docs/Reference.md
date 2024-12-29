# Reference

The reference provides an overview of the inner workings of Spaceport. It is intended for developers who are interested in how Spaceport works under the hood.

For practical usage, see the [guides](Guides.md).

## A mental model

Fundamentally, Spaceport is an automation tool for specifying and testing the expected behavior of a system. Its working model can be seen as having two stages:

1. **Transformation** - Spaceport can refine natural language content describing the expected behavior of a system, then transform it into test scripts.
2. **Execution** - Spaceport can set up the test environment and execute the test scripts to verify the expected behavior.

The **transformation** stage involves two steps:

```
               1. Rewriting            2. Transpiling
┌────────────────┐       ┌────────────────┐       ┌────────────────┐
│   References   │   →   │     Specs      │   →   │  Test Scripts  │
│     (text)     │   →   │     (text)     │   →   │     (code)     │
└────────────────┘       └────────────────┘       └────────────────┘
```

This architecture allows gradual structuralization of text into code. 

Rewriting is the process of generating specs from reference sources. First, feature specs are synthesized from product requirements, issues, documentation, or code for the business logic. Then, they are transformed into executable specs, which are more granular and are about design/implementation details. [Executable spec](#executable-specs) is to Spaceport as an IR is to a compiler. Without this "IR", direct transpilation from natural language into code is possible but highly inefficient and unstable.

Transpiling is the process of generating test scripts from executable specs. The output code is written in a [Python DSL](#test-code). It allows for easier encapsulation of a diverse range of user interactions with the system under test. Much of a test script are special function calls under the `T` namespace, like `T.click("gui//button")` or `T.read_text("fs//file.txt")`. As their names suggest, they describe your user's actions and expectations when working with your software.

In the **execution** stage, Spaceport will dynamically load [implementation packages](#subject-implementations) of the `T` namespace--this decoupling makes it very easy to swap between different implementations that may run in different test environments (containerized vs. local), target different systems (web vs. desktop), or rely on different libraries (Selenium vs. Playwright). Test scripts and the [environment manifest](#environment-manifest) guide the implementations to properly set up test contexts--like spinning up a browser, connecting to a database, launching a container--and release resources after tests are done.

Another important component of testing is fixture data. Currently, fixture data has to be directly specified in the executable specs, but in the future, Spaceport will be able to 1) import fixture data from external sources, and 2) generate fixture data automatically.

## Executable specs

Executable specs are the central part of a Spaceport project. They are the source of truth for the expected behavior of a system.

Executable specs follow a specific Markdown format and a (natural) language standard.

#### Format

An executable specification consists of one or more Markdown blockquotes that conform to the following rules:

- An optional first line that starts with `>>`; this line declares the start of a specification and its name
- The other lines must start with `> -` (a bullet list item in a blockquote) or is a sub-bullet
    - If the line begins with `GIVEN`, or is a sub-bullet of the line that begins with `GIVEN`, it sets up a data context (such as a string input, a valid data schema, etc.)
    - If the line begins with `USE`, it sets up a [subject](#subject-implementations)
    - Otherwise, it describes an action or assertion about an interaction target; the target may be enclosed in `_` for emphasis

An example:

```markdown
>> This is a spec
> - USE some subject
> - Perform some action on a _target_
```

Blockquotes without a spec name declaration are considered continuations of the most recently declared spec:

```markdown
>> Spec #1
> - This belongs to Spec #1

> - This blockquote also belongs
>   - to Spec #1

[...some other text...]

>> Spec #2

> - This blockquote belongs to Spec #2
```

#### Language standard

Every executable spec is transpiled into program code. The higher the quality of the language of the specification, the more likely the transpiled code is to be correct. Executable specification thus are required to follow a language standard to ensure their quality.

These properties are desired:

- **Precise** - An executable spec should explicitly state both the action to be performed and its target
    
    Good:
    
    - Input in the _search bar_: "squirrel"
    - Click the _search button_
    - Verify that there is at least one _search result_
    
    Bad:
    
    - Input a search phrase
    - Run search
    - Verify the results

- **Comprehensive** - Executable specs in a project, collectively, should consider both the positive and negative cases
    
    Example:

    ```markdown
    >> Test positive case
    > - GIVEN:
    >   - The search page
    >   - A valid query
    > - USE a browser
    > - Input the query in the search bar
    > - Assert there is at least one result in the search result area
    
    >> Test negative case
    > - GIVEN:
    >   - The search page
    >   - An invalid query
    > - USE a browser
    > - Input the query in the search bar
    > - Assert there is no result
    ```

## Use of LLMs

Spaceport employs a broad set of LLMs. Most critically, two are used for rewriting and transpiling:

1. A **Rewriter** LLM rewrites the reference sources into executable specs--in the process, it will try to understand the expected behavior of the system and enumerate most likely combinations of user actions, in both positive and negative cases. It will also point out any ambiguities in the spec.

   The output of the Rewriter is written into an project's artifact file. Currently, each rewriting completely overwrites any existing content, but in the future, it will be able to work incrementally, for example, by incorporating answers to the open questions.

2. A **Transpiler** LLM transforms the executable specs into code. The full documentation of `T` functions are rendered into its system prompt.

### AI vendors

By default, both the Rewriter and Transpiler use Claude 3.5 Sonnet for generation. It produces specs and code of higher quality than Claude 3.5 Haiku and GPT-4o do.

The Rewriter also uses an embedding model to find the most relevant reference sources for each spec. By default, it uses `text-embedding-3-small` from OpenAI.

If you prefer to also use OpenAI's models for rewriting and transpiling, you can set the the following environment variables inside `"$(sp tc get-config-dir)"/.env`:

- `SPACEPORT_SPECCER_LLM_VENDOR` - The vendor of the LLM; must be one of `openai` or `anthropic`
- `SPACEPORT_SPECCER_LLM_MODEL` - The model to use; must be a valid chat completion model from the vendor

## Test code

Spaceport runs a Python-based DSL for testing. Simply put, it is a subset of regular Python code with the special `T` functions that model what users would do with your software. 

> [!NOTE]
> The DSL is in its infancy and certain concepts are not yet stable. Also, without proper tooling, it can be hard to debug test code, especially when it comes to TSL and function signatures. We are working to improve this.

### Subject implementations

Subjects are standardized interfaces for working with the tested software or its environments. A subject can be a web app, SQL database, API service, or any other interactive entity. When interacting with a subject, your users usually only work on a specific component of it (an action's target), like a button, a DB table, or a single web page.

`spaceport.subject` module provides the fundamental abstraction over subjects and targets:

- `Subject` is the abstract base class for all subject implementations; it is reponsible for setting up the connection with an underlying subject and getting an appropriate handle to the target component(s) that the user is interested in.
- `Handle` is the abstract base class for target handles; it is responsible for providing methods to interact with the target component(s) and inspecting their states. It is not named `Target` because a handle does not always point to the same target. Its binding with a target component on the subject is always established right before an operation is performed.

In addtion, `spaceport.op` module defines a suite of operation interfaces that are implemented by target handles. A very basic subject implementation might look like this:

```python
from spaceport.subject import Subject, Handle, TSL
from spaceport.op import gui

class ButtonHandle(Handle, gui.Click):
    async def click(self):
        ...

class GUISubject(Subject):
    async def search(self, tsl: TSL, op_name: str) -> Handle:
        # Search for the target using TSL (see below)
        # The function name (op_name) serves as a hint for the search
        ...
```

Subject implementations can be bundled into packages and published to PyPI. Spaceport comes with a built-in implementation package called `spaceport_simpl`. `spaceport.op` and `spaceport_simpl` are self-documented so you can refer to them for more details.

### Target Search Language (TSL)

TSL is a language for specifying which target to interact with. The first argument of every `T` function call (except for `T.use()`) is a TSL expression, and it is passed to the subject-in-use's `search()` method under the hood to get a target handle.

A TSL expression is a slash-separated path that starts with ``//``, optionally prefixed by a cardinality marker and a dialect. The cardinality marker specifies how to handle the case when multiple targets match the query. When it is included, it must be followed by a ``:``. For example, ``all://...`` indicates that the target is a collection of items. The dialect indicates, in a loose manner, what subject types the target belongs to. For example, ``gui//...`` indicates that the target is an element of a graphical user interface.

Run `sp transpile --print-preamble --tsl` to see the system prompt for generating TSL expressions. It contains more details about currently supported TSL dialects.

### Test code interpreter

The test code interpreter is implemented in the `spaceport.tpyi` module. Its major role is to execute `T` function calls and provide tracing information.

Roughly speaking, a `T` function call:

```python
T.some_op(tsl, **kwargs)
```

is transformed into this Python code:

```python
# Get the subject in use as specified by T.use()
subject = get_subject_in_use()  

# Get the target handle
handle = await subject.search(tsl, op_name="some_op")  

# Bind the handle to the current context
async with handle.bind():  
    # Perform the operation
    await handle.some_op(**kwargs)  
```

## Workspaces and projects

### Project artifacts

Each Spaceport project should have a project artifact, which is the source of truth for executable specs and test code.

A project artifact is just a Markdown file with special syntax for executable specs and test code. Artifacts generated by Spaceport usually contain the following sections:

- A summary section that summarizes the project being specified and tested
- A details section that describes its behavior in more detail
- An open questions section that lists the open questions that the Rewriter could not answer and needs further clarification
- An executables section that contains the executable specs and other commentary content

After transpliation, test code will be inserted into the executables section, right after corresponding executable specs.

You generally do not need to edit a project artifact's metadata, and only need to edit its content when Spaceport's LLMs are not working as expected.

> [!WARNING]
> As mentioned in the README, consider adding `sp-projects/*.md` to your code formatter's ignore list. 
> 
> Formatters like Prettier tend to make these changes that break Spaceport:
> - Changing `>>` to `> >`. But Spaceport only recognizes `>>` as the defining marker of a spec's name. Without it, a new spec's block will be considered a continuation of the previous spec.
> - Inserting a newline between a spec block and a contiguous code block. This breaks Spaceport's convention that a code block is immediately after its corresponding spec. If you re-run code generation for the spec afterwards, the existing code block will not be overwritten, and will still be considered part of the spec's test script.

### Manifests

Each Spaceport workspace contains a workspace manifest (the `spaceport.yaml` file) and an environment manifest (the `sp-env.yaml` file).

#### Workspace manifest

The workspace manifest is used primarily to describe the projects in the workspace.

It contains the following fields:

- `name` - The name of the workspace
- `projects` - A list of projects in the workspace, each with the following fields:
  - `name` - The name of the project
  - `artifact` - The path to the artifact file for the project or a `true` value for using the default path
  - `sources` - The reference sources of the project, including:
    - `primary` - The primary source of the project; must be a file
    - `other` - A list of secondary sources of the project; can be files or directories

  Either `artifact` or `sources` must be specified.


Example:

```yaml
projects:
# Project with a hand-written artifact placed at the default path `sp-projects/<project name>.md`
- name: project-1 
    artifact: true

# Project with a hand-written artifact placed at a custom path
- name: project-2
    artifact: ~/docs/specs.md

# Project with reference sources
# The generated artifact will be placed at the default path
- name: project-3
    sources:
    primary: primary-source-file
    other:
    - other-source-1
    - other-source-2
```

#### Environment manifest

The environment manifest primarily contains metadata about test [subjects](#subject-implementations) that serve as interfaces with the test environment.

It contains the following fields:

- `impl_pkgs` - The implementation packages to be loaded for the workspace
- `factories` - The subject factories to be used by the workspace
- `subjects` - The subjects to be used by the workspace

If a `sp-env.yaml` file is not found, Spaceport will use the default environment manifest and create one such file when tests are run. Or you may use `sp env add-manifest` to create it manually.
