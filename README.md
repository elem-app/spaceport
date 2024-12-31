# Spaceport

> [!WARNING]
> Spaceport is currently a proof-of-concept. The documentation may be incomplete and the features are unstable and not well-tested.

Spaceport is a novel approach to automating system and end-to-end testing.

It turns specs[^1] into test code and executes them.

Even better, if your product doesn't have a proper spec (yet), Spaceport can read through reference sources (READMEs, docs, comments, unit tests, ...) and write one for you.

[^1]: Specs generated by Spaceport or written in a special language style will have better outcomes. See [how it works](#how-it-works).

## A simple demo

Suppose we want to test that Wikipedia has a page about spaceport.

0. [Install Spaceport and the `browser` extension](#installing-spaceport)

1. Prepare a spec defining the expected behavior. Use your favorite text editor to create a `wiki.md` file with the following content:

   ```markdown
   ## Spaceport on Wikipedia

   Wikipedia should have a page about "spaceport".

   >> Searching for "spaceport" yields a Wikipedia page
   > - GIVEN:
   >   - Wikipedia homepage: https://en.wikipedia.org/wiki/Main_Page
   > - USE a browser
   > - Go to the Wikipedia homepage
   > - Input "spaceport" into the search bar and click the search button
   > - Verify the new page's heading contains "spaceport"
   ```

   Spaceport uses a minimal set of special syntax (`>>`, `> -`, `GIVEN`, and `USE`), and the rest is just plain English. The writing style has to be detailed and unambiguous. Don't worry if this seems tedious - Spaceport can automatically generate these detailed specs for you.

2. Add a Spaceport project named `wiki`:

   ```sh
   sp add wiki -a wiki.md
   ```

3. Generate the test code:

   ```sh
   sp code wiki
   ```

   The generated code is written into `wiki.md` right after the blockquote. Yes, you do not need to manually write implementations for the specs.

4. Run the test:

   ```sh
   sp test wiki
   ```

## How it works

At its core, Spaceport performs three tasks:

1. **Writing specs** - Including feature specs and [executable specs](docs/Reference.md#executable-specs) based on less-structured reference sources
2. **Generating [test code](docs/Reference.md#test-code)** - From executable specs
3. **Running tests** - In dedicated test environments

The first two tasks make use of LLMs. The third task relies on a built-in library that provides functionality for interacting with various types of test subjects.

A feature spec is, a specification of features, that describes their expected behavior. It does not concern itself with the implementation details. On the other hand, tests are always about the details. Otherwise, how could we pre-empt when a user makes an unexpected move on our product?

Enter the executable spec. It is a semi-structured break-down of _expected behavior_ into clear, imperative steps. Each step precisely describes what action should a user take and what outcome should be observed.

For example, this can be a feature spec:

- Spaceport CLI allows users to initialize a workspace

And this is an executable spec:

```markdown
> - USE a shell terminal
> - Type `sp init` and press Enter
> - USE a file system
> - Check that a workspace manifest is created
```

The LLMs are designed to generate executable specs that are as detailed as possible, and then translate them into a Python DSL. The Python DSL allows for easy encapsulation of the rich testing functionality provided by various frameworks like Playwright and SQLAlchemy.

For example, the above spec can be translated line-by-line into the following code:

```py .test
# With the terminal
T.use("terminal")
T.input_text("term//input", "sp init")
T.input_enter("term//input")
T.wait_till_complete("term//")

# With the file system
T.use("fs")
T.has_some("fs//spaceport.yaml")
```

Spaceport then loads actual implementations of these `T` functions and runs the test.

## Quick start

### Prerequisites

- Python 3.12 (required, support for older versions of Python is WIP)
- Docker (optional, for containerized testing)
- Anthropic API key (strongly recommended for spec and code generation; can be replaced with OpenAI's API key)
- OpenAI API key (required for text embedding)

### Installation

#### Step 1. Install the CLI

We recommend installing the CLI in an isolated environment so its dependencies do not conflict with your other Python code.

With [pipx](https://pypa.github.io/pipx/):

```sh
pipx install spaceport
```

or with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install spaceport
```

#### Step 2. Install extensions (optional)

To reduce package size, some testing functionality is implemented as extensions. You can install them with the following command:

```sh
sp tc install <extension>...
```

Available extensions are:

- `container` - For testing in Docker containers - you also need to have Docker installed
- `browser` - For testing web applications
- (WIP) `sqldb` - For testing SQL databases

#### Step 3. Set up API keys

Spaceport uses the OpenAI API for text embedding and the Anthropic API for spec and code generation. You need to set both keys inside the CLI config directory with an `.env` file.

```sh
# Get the toolchain config directory
export SPACEPORT_DOTENV="$(sp tc get-config-dir)/.env"

# Set the API keys
echo "SPACEPORT_OPENAI_API_KEY=<your OpenAI API key>" >> $SPACEPORT_DOTENV
echo "SPACEPORT_ANTHROPIC_API_KEY=<your Anthropic API key>" >> $SPACEPORT_DOTENV
```

See [here](docs/Guides.md#change-ai-vendors) on how to change the AI vendors.

### Typical workflow

A typical workflow is as follows:

1. (Optional) Use `sp init` to initialize a workspace
2. Prepare reference sources for a project and use `sp add` to add the project to the workspace (it initializes the workspace if not already done)
3. Use `sp make` to generate executable specs from the reference sources
4. Specify the test environment in `sp-env.yaml` and the fixtures in the generated specs
5. Use `sp code` to generate test code from the specs
6. Use `sp test` to run the tests

Steps 3-6 are deliberately designed to be incremental, so that you may review and edit the generated contents before proceeding to the next step.

#### Step 1. Initialize a workspace

Spaceport works in workspaces. A workspace is a directory containing a `spaceport.yaml` file (the workspace manifest). It may also contain a `sp-env.yaml` file (the environment manifest), a `sp-projects` directory for project artifacts.

> [!TIP]
> We recommend setting up the Spaceport workspace directly inside your code repo, so you can manage the code and specs in sync, and conveniently integrate Spaceport into the CI/CD pipeline.

Just run the following command in the directory you want to set up as a workspace. This will create a workspace manifest automatically.

```sh
sp init
```

#### Step 2. Prepare reference sources and add a project

You may have multiple projects in a workspace so that different specs can be tested in different projects, each with its own or shared environment manifests.

A project should have an [artifact](docs/Reference.md#project-artifacts) file, either prepared by you or generated by Spaceport, as the source of truth for executable specs and test code. Artifacts are placed under the `sp-projects` directory by default.

To auto-generate a project's artifact, Spaceport relies on one primary reference source and may have multiple secondary reference sources ("other sources"). This distinction allows Spaceport to generate more spot-on specs by focusing on the primary source and only using other sources for context.

Note that a source does not need to be a file of source code. It can be any text file, such as a README, a business plan, a conversation transcript, etc.

Run `sp add` to add a project to the workspace and specify its primary and other sources.

```sh
sp add <project name> -p <primary source> -o <other source 1> -o <other source 2> ...
```

#### Step 3. Generate specs

This command generates an artifact for the added project.

```sh
sp make <project name>
```

The artifact will be named `<project name>.md` and placed in the `sp-projects` directory. It contains the following contents:

- A `## Summary` section that summarizes the project
- A `## Details` section that describes the project in more detail
- A `## Open Questions` section that lists the open questions that the Rewriter could not answer and needs your help
- A `## Executables` section that contains the executable specs and other commentary content

An [executable spec](docs/Reference.md#executable-specs) consists of consecutive blockquotes that describe a single scenario. Its format is as follows:

```markdown
>> <spec name>
> - GIVEN:
>   - <context 1>
>   - <context 2>
>   - ...
> - USE <tool> with <some context>
> - <some action>
> - <some verification>
```

Only executable specs are further transformed into test code.

#### Step 4. Specify the test environment and fixtures

> [!NOTE]
> Admittedly, this step is more manual and complex than the others. There are several permanent and temporary limitations:
> - First and foremost, details about test environments are NOT part of the specs. Given this, we have not made and no plan to make Spaceport automatically detect and configure the test environment. We are exploring ways to make this easier, but in the end, test environment configuration is a task that is best left to you.
> - Second, Spaceport does not have a built-in way to generate test fixtures today. This is a feature we are working on but can be a bit tricky to get right.

If you plan to run tests in a local environment, then you do not need to do anything with the environment manifest. For tests with Docker, see [here](docs/Guides.md#testing-with-docker).

However, you do need to specify data fixtures in the generated specs. Open the project artifact file and look for bullet points after 'GIVEN' (case sensitive). Each bullet point is a fixture that _Spaceport thinks_ the spec requires. 

Here is an example taken from the generated artifact for Spaceport CLI:

```markdown
>> Generate specifications for a project
> - GIVEN:
>   - a workspace directory
>   - a project name with source files
>   - verifiable condition for generated specs
```

What you need to do is add descriptions of the required data after each bullet point:

```markdown
>> Generate specifications for a project
> - GIVEN:
>   - a workspace directory: `fixtures/test-project`
>   - a project name with source files: project name - `test-project`, primary source - `docs.md`
>   - verifiable condition for generated specs: `sp-projects/test-project.md` is generated; it contains blockquotes that start with `>>` and followed by lines that start with `> -`
```

You can see that simple data structures can just be provided as-is. Complex conditions can be described in natural language on the same line. We are working on a more rigid data validation system to make complex conditions easier to write and test (see [roadmap](docs/Roadmap.md)).

You may find more details about the environment manifest in the [reference](docs/Reference.md#manifests).

#### Step 5. Generate test code

> [!WARNING]
> Be careful when using code formatters (like Prettier) on artifact files. Their default settings may mess with some special syntax that Spaceport relies on, leading to failed or incorrect code generation and execution.
>
> Consider adding `sp-projects/*.md` to your code formatter's ignore list.

Run the following command to generate test code for all specs in a project:

```sh
sp code <project name>
```

The generated code is placed immediately after each executable spec in the project artifact like this:

````markdown
>> Generate specifications for a project
> - GIVEN:
>   - a workspace directory: `fixtures/test-project`
>   - a project name with source files: project - `test-project`, primary source - `docs.md`
> - USE a terminal
> - Change directory to the workspace directory
> - Run `sp make {project_name}`
```py .test
# GIVEN:
# - a workspace directory: `fixtures/test-project`
# - a project name with source files: project - `test-project`, primary source - `docs.md`
workspace_dir = "fixtures/test-project"
project_name = "test-project"

# USE a terminal
T.use("terminal")

# Change directory to the workspace directory
T.set_working_dir("term//", workspace_dir)

# Run `sp make {project_name}`
T.input_text("term//input", f"sp make {project_name}")
T.input_enter("term//input")
T.wait_till_complete("term//")
```
````

#### Step 6. Run tests

Run all tests in a project:

```sh
sp test <project name>
```

A test report will be printed out.

## How is Spaceport different

### vs. unit tests and integration tests

Spaceport does not replace unit tests and integration tests but complements them. It excels at end-to-end and system testing by simulating real user interactions. For testing internal APIs and components, it is often easier to stick with your existing unit testing strategy.

### vs. using an LLM to write tests directly

While LLMs can write general test code, Spaceport provides several benefits over direct generation:

- More reliable: Spaceport's generation process is more controlled and stable, making the generated code more reliable and less likely to be wrong or contain bugs
- More interpretable: Spaceport uses a natural language format for specs and ties test code strictly to the spec, making it easier to understand and debug the tests
- Less boilerplate: Spaceport's generation process is more efficient, reducing boilerplate code

### vs. Cucumber/SpecFlow

Spaceport shares some similarities with Cucumber/SpecFlow in that both use natural language to describe test scenarios. However, there are key differences:

- Auto-generation: Spaceport can auto-generate executable specs AND test code from existing documentation, while Cucumber/SpecFlow requires manually writing Gherkin specs and implementing step definitions
- Language flexibility: Spaceport's spec format is more flexible and natural, less constrained by stringent syntactic requirements

## Next steps

- Check out the [guides](docs/Guides.md) for practical examples and tips, especially how to review and edit generated content and debug tests.
- Learn more about the core concepts and inner workings of Spaceport in the [reference](docs/Reference.md).
- Review the [Spaceport CLI](docs/CLI.md) documentation for available CLI commands and their usage.
- Keep an eye on the [roadmap](docs/Roadmap.md) for upcoming features and improvements.
