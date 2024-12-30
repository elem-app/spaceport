# Guides

The guides provide practical tips and examples of how to use Spaceport.

## Must-reads

It is recommended that you should read this section in order to work with Spaceport successfully.

### The mental model

Spaceport is an automation tool for specifying and testing the expected behavior of a system.

In order to specify, it needs to help you write specs and code about the system. It does this in two steps:

```
               1. Rewriting            2. Transpiling
┌────────────────┐       ┌────────────────┐       ┌────────────────┐
│   References   │   →   │     Specs      │   →   │  Test Scripts  │
│     (text)     │   →   │     (text)     │   →   │     (code)     │
└────────────────┘       └────────────────┘       └────────────────┘
```

1. **Rewriting** is the process of generating specs from reference sources. First, feature specs are synthesized from product requirements, issues, documentation, or code for the business logic. Then, they are transformed into executable specs, which are more granular and are about design/implementation details.  
   If you have an executable spec, you can skip this step.
2. **Transpiling** is the process of generating test scripts from executable specs.

Afterwards, Spaceport can execute the test scripts to verify the expected behavior.

All the specs and test code are stored in the project's artifact file for you to review and edit.

### Working with project artifacts

Each Spaceport project has an artifact that contains all the specs and their test code. It is a Markdown file that works like a Jupyter notebook--except for some special syntax for executable specs and test code, the rest are commentary. Feel free to put relevant information in there to facilitate and documentation and communication.

**Executable specs** are Markdown blockquotes that start with `>>` followed by nested lists:

```markdown
>> Name of the spec
> - GIVEN:
>   - some fixtures
>   - some other fixtures
> - USE a subject to interact with
> - Perform some actions
```

The only special markers are: 

- `>>` for spec name declaration
- List-inside-blockquote for spec content
- `GIVEN` for fixture declarations (covered in step 4 of the [typical workflow](../README.md#typical-workflow))
- `USE` for subject uses (see reference about [subject implementations](Reference.md#subject-implementations))

The rest are just plain English. However, they should be written in a specific style--each point should describe exactly one user action in precise, unambiguous terms. When editing these points, you should adhere to this style and describe clearly what the user is doing.

**Test code** are enclosed in Markdown code blocks with the language identifier `py .test` like this:

````markdown
```py .test
T.use("container-1")
T.set_working_dir("fs//", "tmp")
T.create_file("fs//file.txt", "Hello, world!")
```
````

The special `T` namespace exposes all test operations as standalone functions. We will talk about it soon.

Spaceport-generated test code is placed right after its corresponding spec like this:

````markdown
>> Name of the spec
> - ...
> - last line of the spec
```py .test
T.use(...)
T.some_op(...)
```
````

> [!NOTE]
> You may use Copilot or other AI assistants to help you write commentary and edit specs. But be careful when they touch the code.  
> Because the code involves special `T` functions, Spaceport uses a specialized prompt with its coding agent and generates more reliable code than general AI assistants.

### Basics of generated code

In the [reference](Reference.md#test-code), you may find more details about the generated code. But it suffices to know the following:

- The generated code is valid Python code with a built-in `T` namespace.
- Every function call under the `T` namespace imitates a user action on the system being tested. They are defined by abstract base classes in the `spaceport.op` module. Each abstract method inside these classes is automatically transformed by Spaceport into a `T` function with the same name. For example, `spaceport.op.fs.CreateFile.create_file()` is transformed into `T.create_file()`.
- Except for `T.use()`, a `T` function always works on a so-called [subject](Reference.md#subject-implementations). A `T.use()` sets up the subject for the `T` function calls that follow it.
  
  In this example, the second `T.use()` switches the subject in use to `browser-1`:
  ```py
  T.use("container-1")

  # Uses 'container-1' subject
  T.set_working_dir("fs//", "tmp")
  T.create_file("fs//file.txt", "Hello, world!")

  T.use("browser-1")

  # Uses 'browser-1' subject
  T.goto_url("gui//", "https://example.com")
  ```

- The first argument of `T.use()` is the name of the subject to use. It should appear in `sp-env.yaml` under the `subjects` section. The rest are keyword arguments passed to either the subject's class constructor or its factory's `create()` method.
- The first argument of a normal `T` function specifies a specific component of the subject for your user to interact with. You generally do not need to modify it, but if you are unsure, refer to the [Target Search Language (TSL)](Reference.md#target-search-language-tsl) section in the reference.  
  
  The rest of the arguments are specified by the corresponding abstract method.

### Debugging tips

By default, `sp test` prints out a detailed traceback for each test failure, plus the local variables used by the test script at the point of failure.

However, since `T` functions are quite "magic", it can be hard to see why a particular function call failed. The following common issues can help you debug the problem.

#### Missing `T.use()`

Spaceport may fail to generate a "USE" bullet point in the executable spec, and subsequently miss out on the `T.use()` call during transpilation. If you see an error message saying "No subject provided" or "Operation x not found on handle", it is likely that a `T.use()` call should be added before the failed statement.

#### Incorrect relative paths

File system, bash, and container subjects have an internal state for the current working directory. All relative paths are relative to the current working directory. This means that a path provided as a fixture need to be relative to the current working directory when it is used.

For example, consider this scenario, where the `data.csv` file is located in the `fixtures` directory:

````markdown
> - GIVEN:
>   - a base directory `fixtures`
>   - a data file `fixtures/data.csv`
```py .test
T.set_working_dir("fs//", "fixtures")
T.open_document("sdoc//", "fixtures/data.csv")  # ERROR
```
````

You may either modify the file path so it is relative to `fixtures`, or remove the `T.set_working_dir()` call.

#### Unsupported operations

If a subject is provided with `T.use()`, but an error "Operation x not found on handle" is still raised, it is highly possible that Spaceport has generated incorrect spec. For example, it may try to use a structured document editor to open a Markdown file.

The only fix today is to manually edit the spec or the code to remove the unsupported operation and use an alternative, based on the documentation inside `spaceport.op`. We are working on additional tooling to support faster lookup of operation usages so you can more easily find the correct operation to use.

## Change AI vendors

By default, Spaceport uses Claude 3.5 Sonnet for spec and code generation. Its output is of higher quality than that of Claude 3.5 Haiku and GPT-4o.

The spec generation also employs an embedding model to find the most relevant reference sources for each spec. By default, it uses `text-embedding-3-small` from OpenAI.

If you prefer to also use OpenAI's models for spec and code generation, you can set the the following environment variables inside `"$(sp tc get-config-dir)"/.env`:

- `SPACEPORT_SPECCER_LLM_VENDOR` - The vendor of the LLM; must be one of `openai` or `anthropic`
- `SPACEPORT_SPECCER_LLM_MODEL` - The model to use; must be a valid chat completion model from the vendor

## Testing CLI apps

Not surprisingly, the Spaceport CLI is tested with Spaceport. If you clone the Spaceport repo, you can run `sp list` in the root directory to see the Spaceport projects that specify and test the CLI.
