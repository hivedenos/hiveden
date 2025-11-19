# Welcome to Hiveden! :honeybee:

[![Build Status](https://travis-ci.org/your-username/hiveden.svg?branch=main)](https://travis-ci.org/your-username/hiveden)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Hiveden** is a powerful and user-friendly tool for managing your personal server. Whether you're a seasoned DevOps engineer or just getting started with server administration, Hiveden is here to make your life easier. Our goal is to provide a comprehensive and intuitive solution for managing containers, packages, storage, and more, all from a single, unified interface.

We are an open and welcoming community, and we'd love for you to be a part of it. If you're interested in contributing, have a great idea, or just want to say hi, please don't hesitate to get in touch!

## :rocket: Getting Started

Getting started with Hiveden is easy. Just follow these simple steps to set up your development environment and start using Hiveden.

### Prerequisites

- Python 3.7+
- `pip`
- `virtualenv` (recommended)

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/hiveden/hiveden.git
    cd hiveden
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the dependencies:**

    We provide two separate requirements files:
    - `requirements.txt`: For the core application.
    - `requirements-dev.txt`: For development, including testing tools.

    To install all the necessary dependencies for development, run:

    ```bash
    pip install -r requirements-dev.txt
    ```

4.  **Install Hiveden in editable mode:**

    This will allow you to make changes to the code and see them reflected immediately.

    ```bash
    pip install -e .
    ```

## :computer: Running the Application

Hiveden provides both a command-line interface (CLI) and a REST API for managing your server.

### Command-Line Interface (CLI)

The CLI is the primary way to interact with Hiveden. You can get a list of all the available commands by running:

```bash
hiveden --help
```

Here are some examples of what you can do with the Hiveden CLI:

- **Apply a configuration:**

  ```bash
  hiveden apply --config my-config.yaml
  ```

- **List Docker containers:**

  ```bash
  hiveden docker list-containers --only-managed
  ```

- **Install a system package:**

  ```bash
  hiveden pkgs install htop
  ```

### REST API

Hiveden also provides a REST API for programmatic access. To run the API server, use the `server` command:

```bash
hiveden server --host 0.0.0.0 --port 8000
```

Once the server is running, you can access the interactive API documentation (Swagger UI) at `http://localhost:8000/docs`.

## :gear: Configuration

Hiveden is configured using a single YAML file, `config.yaml`. This file allows you to define the desired state of your server in a declarative way. The CLI searches for this file in the following locations, in order:

1. The path specified by the `--config` flag.
2. `config.yaml` in the current directory.
3. `~/.config/hiveden/config.yaml`
4. `/etc/hiveden/config.yaml`

Here's an example of what the configuration file looks like:

```yaml
# Example configuration for Hiveden

docker:
  # The name of the Docker network to use.
  network_name: hiveden-net

  # A list of containers to manage.
  containers:
    - name: my-container
      image: ubuntu:latest
      command: sleep infinity
      env:
        - name: MY_VAR
          value: my_value
      ports:
        - host_port: 8080
          container_port: 80
```

## :test_tube: Running Tests

We use `pytest` for testing. To run the test suite, simply run the following command from the root of the project:

```bash
pytest
```

## :handshake: Contributing

We love contributions from the community! If you'd like to contribute to Hiveden, please follow these steps:

1.  **Fork the repository** on GitHub.
2.  **Create a new branch** for your feature or bug fix.
3.  **Make your changes** and add tests for them.
4.  **Ensure the tests pass** by running `pytest`.
5.  **Submit a pull request** with a clear and detailed description of your changes.

If you have any questions, please don't hesitate to open an issue on GitHub.

## :page_with_curl: License

Hiveden is open-source software licensed under the [MIT License](https://opensource.org/licenses/MIT).
