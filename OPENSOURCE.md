# rst_queue - Open Source Project

Welcome to **rst_queue**, a high-performance async queue system built with Rust and Crossbeam, with Python support.

## About

This project is maintained by **Suraj Kalbande** (Data Architect) and is open source under the MIT License.

## Quick Links

- 📖 [Contributing Guidelines](CONTRIBUTING.md)
- 👥 [Contributors](CONTRIBUTORS.md)
- 📄 [License](LICENSE)

## Getting Started

See [README.md](README.md) for full documentation.

### Quick Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/rst_queue.git
cd rst_queue

# Build
cargo build --release

# Run examples
cargo run --release --bin queue_example
python python_example.py
```

## Features

- ✨ **Python-Ready**: Use from Python with `rst_queue` module
- 🔄 **Dual Execution Modes**: Sequential and Parallel processing
- 🔒 **Thread-Safe**: Uses Arc and Mutex for safe concurrent access
- ⚡ **Zero-Copy**: Efficient channel-based message passing
- 🛠️ **Flexible**: Support for custom worker functions
- 📦 **Simple API**: Easy to use and integrate

## Project Links

- 📝 [Full Documentation](README.md)
- 🐛 [Report Issues](https://github.com/yourusername/rst_queue/issues)
- 🤝 [Contribute](CONTRIBUTING.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you have any questions or need help, feel free to open an issue on GitHub.

---

**Made with ❤️ by Suraj Kalbande**
