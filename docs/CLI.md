# Spaceport CLI

Spaceport CLI is a command line interface for the Spaceport framework. It features a set of commands for managing workspaces and projects, and for generating and testing executable specifications.

## Workspace commands

### Creating a workspace

#### Synopsis

```sh
sp init
```

#### Description

Creates a new workspace in the current directory. This command will create a `spaceport.yaml` file in the current directory.

### Adding a project

#### Synopsis

```sh
sp add <project> [options]
```

#### Description

Adds a new project to the workspace. Either `-a` or `-p` must be set.

This command will run `sp init` first if `spaceport.yaml` does not exist in the current directory. It then updates the workspace manifest to include the new project.

#### Options

`-a [<path>]`  
`--artifact [<path>]`  
&nbsp;&nbsp;&nbsp;&nbsp;The path to the artifact file to use for the project. If the option is set but a path is not provided, will use the default path for the project name. If the artifact file does not exist, will create it.  
&nbsp;&nbsp;&nbsp;&nbsp;Cannot be used with the `-p` and `-o` options.

`-p <path>`  
`--primary <path>`  
&nbsp;&nbsp;&nbsp;&nbsp;The path to the primary source of the project. This is the source that will be used as a starting point to generate the executable specifications.  
&nbsp;&nbsp;&nbsp;&nbsp;Cannot be used with the `-a` option.

`-o <path>`  
`--other <path>`  
&nbsp;&nbsp;&nbsp;&nbsp;The path to the other source of the project. This option can be repeated multiple times to add multiple other sources. These are the sources that will be used as references to generate the executable specifications.  
&nbsp;&nbsp;&nbsp;&nbsp;Cannot be used with the `-a` option.

### Generating executable specifications

#### Synopsis

```sh
sp make [options] [<project>...]
```

#### Description

Generates executable specs for the given projects.

#### Options

`--all`  
&nbsp;&nbsp;&nbsp;&nbsp;Generates executable specs for all projects in the workspace.  
&nbsp;&nbsp;&nbsp;&nbsp;Cannot be used when any project is specified.

### Generating test code

#### Synopsis

```sh
# First form
sp code [options] [<project>...]

# Second form
sp code [options] <project> [-s <spec>...]
```

#### Description

In its first form, generates test code for the given projects. In its second form, generates test code for the given specifications in the given project.

#### Options

`--all`  
&nbsp;&nbsp;&nbsp;&nbsp;Generates the test code for all projects in the workspace.  
&nbsp;&nbsp;&nbsp;&nbsp;Cannot be used in the second form or when any project is specified.

`-s <spec>`  
`--spec <spec>`  
&nbsp;&nbsp;&nbsp;&nbsp;The specification to generate test code for. This option can be repeated multiple times to specify multiple specifications.  
&nbsp;&nbsp;&nbsp;&nbsp;Can only be used when one single project is specified. Cannot be used with the `--all` option.

### Testing specifications

#### Synopsis

```sh
sp test <project> [-s <spec>...] [other options]
```

#### Description

Tests the given specifications in the given project. If no specifications are given, will test all specifications in the project.

Prints a human-readable summary to stdout by default.

#### Options

`-s <spec>`  
`--spec <spec>`  
&nbsp;&nbsp;&nbsp;&nbsp;The specification to test. This option can be repeated multiple times to specify multiple specifications.

`--json <path>`  
&nbsp;&nbsp;&nbsp;&nbsp;Outputs the test results in JSON format to the given path.

`--junit-xml <path>`  
&nbsp;&nbsp;&nbsp;&nbsp;Outputs the test results in JUnit XML format to the given path.

### Renaming a project

#### Synopsis

```sh
sp rename <old name> <new name>
```

#### Description

Renames a project. If the project's artifact exists, its metadata will be updated to reflect the new name. If the file path is not explicitly set, the default artifact file will be updated to the new name as well.

### Listing projects and specs

#### Synopsis

```sh
sp list [<project>...]
```

#### Description

Lists the given projects and specs in the workspace. If no projects are given, will list all projects in the workspace.

## Environment commands

Environment commands are used to work with the `sp-env.yaml` file.

All environment commands are subcommands of `sp env`.

### Creating an environment manifest

#### Synopsis

```sh
sp env add-manifest <template>...
```

#### Description

Add a template manifest to the workspace.

Multiple templates can be added at once. Available templates are:

- `local` - For testing on the local machine.
- `container` - For testing in a Docker container.
- `browser` - For testing with a web browser.

Some templates may contain values that are `<NOT_GIVEN>`. These values must be filled in by the user.

### Checking the environment manifest

#### Synopsis

```sh
sp env check-manifest
```

#### Description

Checks the environment manifest. Reports missing manifest file or not-given values as errors.

## Toolchain commands

Toolchain commands are used to manage the Spaceport toolchain, including the CLI itself.

All toolchain commands are subcommands of `sp tc`.

### Installing extensions

#### Synopsis

```sh
sp tc install [options] <extension>...
```

#### Description

Installs the specified extensions.

To reduce package size, certain features are not installed by default. Extensions enable these features by installing the necessary dependencies.

Extensions include:

- `simpl.browser` - Adds subject implementation for web browsers
- `simpl.container` - Adds subject implementation for Docker containers

After installing an extension, if it has a corresponding env manifest template, the template will be added, unless the `--skip-post` option is used.

#### Options

`--skip-post`  
&nbsp;&nbsp;&nbsp;&nbsp;Skip post-install actions, including adding template env manifest.

### Listing extensions

#### Synopsis

```sh
sp tc list-exts
```

#### Description

Lists all installed extensions.

Note that this command will only list extensions that have been installed via `sp tc install`.

### Getting the config directory

#### Synopsis

```sh
sp tc get-config-dir
```

#### Description

Gets the path to the toolchain config directory.

### Checking the toolchain configuration

#### Synopsis

```sh
sp tc check-config
```

#### Description

Checks the toolchain configuration. Reports missing or invalid configuration as errors.
