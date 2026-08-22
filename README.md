# INFATOOL

![Version](https://img.shields.io/badge/version-1.0-blue)
![Python](https://img.shields.io/badge/python-3.7%2B-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Termux-orange)
![License](https://img.shields.io/badge/license-MIT-red)

**Linux & Termux System Intelligence CLI**

A professional cybersecurity-oriented command-line utility for local system discovery, diagnostics, inventory, and reporting.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Commands](#commands)
- [Modules](#modules)
- [Output Files](#output-files)
- [Project Structure](#project-structure)
- [Security Principles](#security-principles)
- [Performance](#performance)
- [Compatibility](#compatibility)
- [Future Roadmap](#future-roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## 🔍 Overview

INFATOOL is a Python-based command-line utility designed to collect and organize detailed information about the local Linux or Termux environment. It provides a professional cybersecurity-oriented terminal interface while remaining focused on legitimate local system discovery, diagnostics, inventory, and reporting.

The tool is:
- **Lightweight** - No external dependencies
- **Modular** - Each module can run independently
- **Portable** - Works on Linux and Android (Termux)
- **Professional** - Clean cybersecurity terminal aesthetic
- **Safe** - Local inventory only, no exploitation

---

## ✨ Features

### Core Capabilities
- 🔍 **Environment Detection** - Automatically detects Linux or Termux
- 🖥️ **System Information** - OS, kernel, architecture, user info
- 🔧 **Hardware Detection** - CPU, GPU, RAM, SoC information
- 🌐 **Network Inventory** - Interfaces, IPs, routing, DNS
- 💾 **Storage Analysis** - Filesystems, mount points, usage
- 🛡️ **Security Configuration** - SELinux, firewall, permissions

### Technical Features
- ✅ **Zero Dependencies** - Pure Python standard library
- 📊 **JSON Reports** - Machine-readable output
- 🎨 **Color Terminal UI** - Professional cybersecurity aesthetic
- 🔄 **Graceful Degradation** - Handles restricted access
- 📈 **Scan History** - Tracks previous scans
- ⚡ **Fast Execution** - Completes in seconds

---

## 🚀 Installation

### Prerequisites
- Python 3.7 or higher
- Linux or Termux environment
- No additional packages required

### Quick Install

```bash
# Clone or download the repository
git clone https://github.com/yourusername/infatool.git
cd infatool

# Verify setup
python3 setup_check.py

# Make scripts executable (optional)
chmod +x main.py system.py hardware.py network.py storage.py security.py
