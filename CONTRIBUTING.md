# Contributing to rst_queue

Thank you for your interest in contributing to **rst_queue**! We welcome contributions from everyone.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps which reproduce the problem** with as many details as possible
- **Provide specific examples** to demonstrate the steps
- **Describe the behavior you observed** and **what you expected to see**
- **Include screenshots and animated GIFs** if possible
- **Include your environment details** (OS, Rust version, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

- **Use a clear and descriptive title**
- **Provide a step-by-step description** of the suggested enhancement
- **Provide specific examples** to demonstrate the steps
- **Explain why this enhancement would be useful**

### Pull Requests

- Fill in the required template
- Follow the Rust and Python style guides
- Include appropriate test cases
- Update documentation as needed
- End all files with a newline

## Development Setup

### Prerequisites

- Rust 1.70+ (https://rustup.rs/)
- Python 3.8+ (https://www.python.org/)
- Git

### Building from Source

```bash
# Clone the repository
git clone https://github.com/suraj202923/rst_queue.git
cd rst_queue

# Build Rust components
cargo build --release

# Install Python development dependencies
pip install -e .

# Run tests
cargo test --release
```

## Style Guides

### Rust Code

- Follow [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)
- Use `cargo fmt` to format code
- Use `cargo clippy` to check for common mistakes
- Write descriptive variable and function names

### Python Code

- Follow [PEP 8](https://pep8.org/) guidelines
- Use meaningful variable names
- Add docstrings to functions and classes

### Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

## License

By contributing to rst_queue, you agree that your contributions will be licensed under its MIT License.

## Code of Conduct

### Our Pledge

In the interest of fostering an open and welcoming environment, we as contributors and maintainers pledge to making participation in our project and our community a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

Examples of behavior that contributes to creating a positive environment include:

- Using welcoming and inclusive language
- Being respectful of differing opinions, viewpoints, and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

Examples of unacceptable behavior include:

- The use of sexualized language or imagery and unwelcome sexual attention or advances
- Trolling, insulting/derogatory comments, and personal or political attacks
- Public or private harassment
- Publishing others' private information without explicit permission
- Other conduct which could reasonably be considered inappropriate in a professional setting

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the project maintainers. All complaints will be reviewed and investigated and will result in a response that is deemed necessary and appropriate to the circumstances.

## Questions?

Feel free to open an issue or reach out to the maintainers.

**Happy coding! 🚀**
