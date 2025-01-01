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
