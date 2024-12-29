# Guides

The guides provide practical tips and examples of how to use Spaceport.

## Must-reads

It is recommended that you should read this section in order to work with Spaceport successfully.

### Working with project artifacts

Each Spaceport project has an artifact that contains all the specs and their test code. It is a Markdown file that works like a Jupyter notebook--except for special blocks, the rest are commentary. Feel free to put relevant information in there to facilitate and documentation and communication.

The special blocks include:

- Blockquotes starting with `>>` followed by nested lists are [executable specs](Reference.md#executable-specs). 
  - Specifically, sub-bullet points after 'GIVEN' are fixtures that you need to provide. The [typical workflow](../README.md#typical-workflow) (step 4) covers how.
  - 'USE' bullet points specify test subjects to be used in the spec. They are a unique concept in Spaceport and detailed in the [reference](Reference.md#subject-implementations).
  - The other bullet points, as you can see, are just plain English. However, they should be written in a specific style--each point should describe exactly one user action in precise, unambiguous terms. When editing these points, you should adhere to this style and describe clearly what the user is doing.
- Code blocks whose language identifier is `py .test` are test code that Spaceport will attempt to run.
  - You may edit the code as you see fit--a big part of it is standard Python.
  - The code includes special `T` functions that will be explained in the following section.

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


## Testing CLI apps

Not surprisingly, the Spaceport CLI is tested with Spaceport. If you clone the Spaceport repo, you can run `sp list` in the root directory to see the Spaceport projects that specify and test the CLI.
