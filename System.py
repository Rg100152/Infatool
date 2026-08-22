# Create system.py using heredoc
cat > system.py << 'EOF'
#!/usr/bin/env python3
"""
INFATOOL - System Information Module
Collects operating system, kernel, and environment information.
"""

import os
import platform
import socket
import subprocess
import sys
import getpass
from datetime import datetime
from pathlib import Path


class SystemInfo:
    """Collect system-related information with graceful error handling."""
    
    def __init__(self):
        self.data = {}
        self.errors = []
    
    def _safe_read_file(self, filepath, default="NOT AVAILABLE"):
        """Safely read a file, returning default on error."""
        try:
            path = Path(filepath)
            if path.exists() and path.is_file():
                content = path.read_text().strip()
                return content if content else default
            return default
        except (IOError, OSError, PermissionError):
            return "RESTRICTED"
        except Exception:
            return default
    
    def _safe_command(self, command, timeout=5):
        """Safely execute a command, returning output or error status."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return result.stdout.strip() or "NOT AVAILABLE"
            return "NOT AVAILABLE"
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except (OSError, subprocess.SubprocessError):
            return "RESTRICTED"
        except Exception:
            return "NOT AVAILABLE"
    
    def detect_termux(self):
        """Detect if running in Termux environment."""
        termux_indicators = [
            os.environ.get('TERMUX_VERSION', ''),
            os.environ.get('PREFIX', ''),
            os.environ.get('ANDROID_DATA', '')
        ]
        
        # Check for Termux-specific paths
        if Path('/data/data/com.termux').exists():
            return True
        
        # Check environment variables
        if any(termux_indicators):
            return True
        
        # Check for Termux in package prefix
        if 'com.termux' in os.environ.get('PATH', ''):
            return True
        
        return False
    
    def get_environment_type(self):
        """Determine the execution environment type."""
        is_termux = self.detect_termux()
        
        if is_termux:
            return "TERMUX"
        elif sys.platform.startswith('linux'):
            return "LINUX"
        elif sys.platform == 'darwin':
            return "MACOS"
        else:
            return "UNKNOWN"
    
    def get_os_release_info(self):
        """Extract information from /etc/os-release."""
        os_info = {}
        
        try:
            content = self._safe_read_file('/etc/os-release')
            if content in ["NOT AVAILABLE", "RESTRICTED"]:
                return os_info
            
            for line in content.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip('"').strip("'")
                    os_info[key] = value
        
        except Exception:
            pass
        
        return os_info
    
    def get_android_properties(self):
        """Get Android-specific properties if available."""
        android_info = {}
        
        if not self.detect_termux():
            return android_info
        
        # Try to get common Android properties
        props_to_check = [
            'ro.product.model',
            'ro.product.manufacturer',
            'ro.build.version.release',
            'ro.build.version.sdk'
        ]
        
        for prop in props_to_check:
            value = self._safe_command(f'getprop {prop}')
            if value not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                android_info[prop.replace('ro.', '')] = value
        
        return android_info
    
    def collect(self):
        """Collect all system information."""
        
        # Environment detection
        environment_type = self.get_environment_type()
        is_termux = environment_type == "TERMUX"
        
        # OS release information
        os_release = self.get_os_release_info()
        
        # Distribution identification
        distribution = "NOT AVAILABLE"
        if is_termux:
            distribution = "Termux (Android)"
        elif 'NAME' in os_release:
            distribution = os_release.get('NAME', 'Linux')
        elif Path('/etc/debian_version').exists():
            distribution = "Debian"
        elif Path('/etc/redhat-release').exists():
            distribution = self._safe_read_file('/etc/redhat-release')
        
        # Uptime
        uptime = "NOT AVAILABLE"
        uptime_raw = self._safe_read_file('/proc/uptime')
        if uptime_raw not in ["NOT AVAILABLE", "RESTRICTED"]:
            try:
                uptime_seconds = float(uptime_raw.split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                uptime = f"{days}d {hours}h {minutes}m"
            except (ValueError, IndexError):
                uptime = "NOT AVAILABLE"
        
        # Shell
        shell = os.environ.get('SHELL', 'NOT AVAILABLE')
        
        # Compile system data
        self.data = {
            "operating_system": {
                "name": platform.system() or "NOT AVAILABLE",
                "distribution": distribution,
                "version": os_release.get('VERSION', 'NOT AVAILABLE') if os_release else 'NOT AVAILABLE',
                "kernel_version": platform.release() or "NOT AVAILABLE",
                "kernel_name": platform.system() or "NOT AVAILABLE",
                "build": os_release.get('VERSION_ID', 'NOT AVAILABLE') if os_release else 'NOT AVAILABLE'
            },
            "environment": {
                "type": environment_type,
                "is_termux": is_termux,
                "platform": sys.platform,
                "python_version": sys.version.split()[0],
                "hostname": socket.gethostname() or "NOT AVAILABLE",
                "architecture": platform.machine() or "NOT AVAILABLE",
                "processor": platform.processor() or "NOT AVAILABLE"
            },
            "user": {
                "username": getpass.getuser() or "NOT AVAILABLE",
                "uid": getattr(os, 'getuid', lambda: "NOT AVAILABLE")(),
                "gid": getattr(os, 'getgid', lambda: "NOT AVAILABLE")(),
                "home": os.path.expanduser('~') or "NOT AVAILABLE",
                "shell": shell,
                "is_root": self._check_root()
            },
            "runtime": {
                "uptime": uptime,
                "current_time": datetime.now().isoformat(),
                "boot_time": self._get_boot_time()
            },
            "android": self.get_android_properties() if is_termux else {}
        }
        
        return self.data
    
    def _check_root(self):
        """Check if running with root privileges."""
        try:
            if hasattr(os, 'geteuid'):
                return os.geteuid() == 0
            return False
        except Exception:
            return False
    
    def _get_boot_time(self):
        """Get system boot time from /proc/stat."""
        btime = self._safe_read_file('/proc/stat')
        if btime not in ["NOT AVAILABLE", "RESTRICTED"]:
            for line in btime.split('\n'):
                if line.startswith('btime'):
                    try:
                        timestamp = int(line.split()[1])
                        return datetime.fromtimestamp(timestamp).isoformat()
                    except (ValueError, IndexError):
                        break
        return "NOT AVAILABLE"
    
    def get_data(self):
        """Return collected data."""
        return self.data
    
    def print_summary(self):
        """Print a human-readable summary."""
        print("SYSTEM INFORMATION")
        print("-" * 40)
        
        os_info = self.data.get('operating_system', {})
        env_info = self.data.get('environment', {})
        user_info = self.data.get('user', {})
        runtime_info = self.data.get('runtime', {})
        
        print(f"OS: {os_info.get('distribution', 'N/A')}")
        print(f"Kernel: {os_info.get('kernel_version', 'N/A')}")
        print(f"Architecture: {env_info.get('architecture', 'N/A')}")
        print(f"Environment: {env_info.get('type', 'N/A')}")
        print(f"Hostname: {env_info.get('hostname', 'N/A')}")
        print(f"User: {user_info.get('username', 'N/A')}")
        print(f"Shell: {user_info.get('shell', 'N/A')}")
        print(f"Uptime: {runtime_info.get('uptime', 'N/A')}")
        
        if env_info.get('is_termux'):
            android_info = self.data.get('android', {})
            if android_info:
                print(f"Android Model: {android_info.get('product.model', 'N/A')}")
                print(f"Manufacturer: {android_info.get('product.manufacturer', 'N/A')}")
                print(f"Android Version: {android_info.get('build.version.release', 'N/A')}")


# Standalone test
if __name__ == "__main__":
    sys_info = SystemInfo()
    sys_info.collect()
    sys_info.print_summary()
EOF
