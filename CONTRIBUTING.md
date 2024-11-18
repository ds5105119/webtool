# Development - Contributing

## Developing

If you already cloned the [webtool repository](https://github.com/ds5105119/webtool) and you want to deep dive in the code, here are some guidelines to set up your environment.

### Virtual environment

Follow the [instructions](https://python-poetry.org/docs/) to create and activate a virtual environment with Poetry for the internal code of webtool.

### Install requirements using poetry

After activating the environment, install the required packages:

```console
 poetry install
```

### Using your local Webtool

If you create a Python file that imports and uses Webtool, and run it with the Python from your local environment, it will use your cloned local Webtool source code.

And if you update that local Webtool source code when you run that Python file again, it will use the fresh version of Webtool you just edited.

That way, you don't have to "install" your local version to be able to test every change.

### Format the code

There is a script that you can run that will format and clean all your code:

```console
poetry run ruff check
```

There is a script that you can run locally to test all the code and generate coverage reports:

```console
poetry run coverage run --omit="tests*" -m pytest
```

## Docs

First, make sure you set up your environment as described above, that will install all the requirements.

### Docs live

During local development, there is a script that builds the site and checks for any changes, live-reloading:

```console
mkdocs serve
```

It will serve the documentation on http://127.0.0.1:8000.

You can also run docs live with other port

```console
mkdocs serve -a localhost:8001
```

That way, you can edit the documentation/source files and see the changes live.

### Docs Structure

The documentation uses [MkDocs](https://www.mkdocs.org/).
