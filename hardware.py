#!/usr/bin/env python3
"""
INFATOOL - Hardware Information Module
Collects CPU, GPU, RAM, and device hardware information.
"""

import os
import platform
import subprocess
from pathlib import Path
from datetime import datetime


class HardwareInfo:
    """Collect hardware-related information with graceful error handling."""
    
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
    
    def _safe_read_lines(self, filepath, max_lines=50):
        """Safely read multiple lines from a file."""
        try:
            path = Path(filepath)
            if path.exists() and path.is_file():
                lines = path.read_text().split('\n')[:max_lines]
                return [line.strip() for line in lines if line.strip()]
            return []
        except (IOError, OSError, PermissionError):
            return []
        except Exception:
            return []
    
    def get_cpu_info(self):
        """Collect CPU information from /proc/cpuinfo."""
        cpu_info = {
            "model": "NOT AVAILABLE",
            "vendor": "NOT AVAILABLE",
            "architecture": platform.machine() or "NOT AVAILABLE",
            "cores": 0,
            "threads": 0,
            "frequency_mhz": "NOT AVAILABLE",
            "features": [],
            "cores_details": []
        }
        
        # Try reading /proc/cpuinfo
        cpuinfo_lines = self._safe_read_lines('/proc/cpuinfo', max_lines=200)
        
        if cpuinfo_lines:
            processors = []
            current_processor = {}
            
            for line in cpuinfo_lines:
                if line.startswith('processor'):
                    if current_processor:
                        processors.append(current_processor)
                    current_processor = {}
                    try:
                        current_processor['id'] = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        current_processor['id'] = "UNKNOWN"
                
                elif ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    # Map common CPU info fields
                    if key in ['model name', 'model', 'cpu']:
                        current_processor['model'] = value
                    elif key == 'vendor_id':
                        current_processor['vendor'] = value
                    elif key in ['cpu mhz', 'clock', 'bogomips']:
                        current_processor['frequency'] = value
                    elif key == 'features':
                        current_processor['features'] = value.split()
                    elif key == 'cpu cores':
                        try:
                            current_processor['cores'] = int(value)
                        except ValueError:
                            pass
                    elif key == 'siblings':
                        try:
                            current_processor['threads'] = int(value)
                        except ValueError:
                            pass
                    elif key == 'hardware':
                        current_processor['hardware'] = value
                    elif key == 'revision':
                        current_processor['revision'] = value
                    elif key == 'serial':
                        current_processor['serial'] = value
            
            if current_processor:
                processors.append(current_processor)
            
            if processors:
                # Get main CPU info from first processor
                first_cpu = processors[0]
                cpu_info['model'] = first_cpu.get('model', 'NOT AVAILABLE')
                cpu_info['vendor'] = first_cpu.get('vendor', 'NOT AVAILABLE')
                cpu_info['frequency_mhz'] = first_cpu.get('frequency', 'NOT AVAILABLE')
                cpu_info['features'] = first_cpu.get('features', [])
                cpu_info['hardware'] = first_cpu.get('hardware', 'NOT AVAILABLE')
                cpu_info['revision'] = first_cpu.get('revision', 'NOT AVAILABLE')
                
                # Count cores and threads
                cpu_info['cores'] = len(processors)
                cpu_info['threads'] = first_cpu.get('threads', len(processors))
                
                # Store all processor details
                cpu_info['cores_details'] = processors
        
        # If /proc/cpuinfo didn't work, try alternative methods
        if cpu_info['model'] == "NOT AVAILABLE":
            # Try lscpu command
            lscpu_output = self._safe_command('lscpu')
            if lscpu_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                for line in lscpu_output.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()
                        
                        if key in ['model name', 'model']:
                            cpu_info['model'] = value
                        elif key == 'vendor id':
                            cpu_info['vendor'] = value
                        elif key == 'architecture':
                            cpu_info['architecture'] = value
                        elif key == 'cpu(s)':
                            try:
                                cpu_info['cores'] = int(value)
                            except ValueError:
                                pass
                        elif key == 'cpu mhz':
                            cpu_info['frequency_mhz'] = value
        
        # Try sysconf for core count
        if cpu_info['cores'] == 0:
            try:
                cpu_info['cores'] = os.cpu_count() or 0
                cpu_info['threads'] = os.cpu_count() or 0
            except Exception:
                pass
        
        return cpu_info
    
    def get_gpu_info(self):
        """Collect GPU information if available."""
        gpu_info = {
            "status": "NOT AVAILABLE",
            "model": "NOT AVAILABLE",
            "driver": "NOT AVAILABLE"
        }
        
        # Try different methods to get GPU info
        
        # Method 1: lspci (Linux)
        lspci_output = self._safe_command('lspci | grep -i vga')
        if lspci_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            gpu_info['status'] = "AVAILABLE"
            gpu_info['model'] = lspci_output
            gpu_info['source'] = 'lspci'
            return gpu_info
        
        # Method 2: Check /proc/device-tree for ARM devices
        device_tree_gpu = self._safe_read_file('/proc/device-tree/gpu/gpu-model')
        if device_tree_gpu not in ["NOT AVAILABLE", "RESTRICTED"]:
            gpu_info['status'] = "AVAILABLE"
            gpu_info['model'] = device_tree_gpu
            gpu_info['source'] = 'device-tree'
            return gpu_info
        
        # Method 3: Check Android/Termux specific GPU info
        if os.environ.get('TERMUX_VERSION'):
            # Try to get GPU info from Android properties
            gpu_model = self._safe_command('getprop ro.hardware.egl')
            if gpu_model not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                gpu_info['status'] = "AVAILABLE"
                gpu_info['model'] = gpu_model
                gpu_info['source'] = 'android-property'
                return gpu_info
            
            # Check for Mali GPU
            mali_info = self._safe_read_file('/proc/mali/version')
            if mali_info not in ["NOT AVAILABLE", "RESTRICTED"]:
                gpu_info['status'] = "AVAILABLE"
                gpu_info['model'] = f"Mali GPU: {mali_info}"
                gpu_info['source'] = 'mali'
                return gpu_info
        
        # Method 4: Check /sys/class/graphics
        if Path('/sys/class/graphics').exists():
            try:
                graphics_devices = os.listdir('/sys/class/graphics')
                if graphics_devices:
                    gpu_info['status'] = "AVAILABLE"
                    gpu_info['model'] = f"Graphics devices: {', '.join(graphics_devices)}"
                    gpu_info['source'] = 'sysfs'
                    return gpu_info
            except (IOError, OSError):
                pass
        
        return gpu_info
    
    def get_ram_info(self):
        """Collect RAM information."""
        ram_info = {
            "total": "NOT AVAILABLE",
            "available": "NOT AVAILABLE",
            "used": "NOT AVAILABLE",
            "free": "NOT AVAILABLE",
            "swap_total": "NOT AVAILABLE",
            "swap_free": "NOT AVAILABLE",
            "buffers": "NOT AVAILABLE",
            "cached": "NOT AVAILABLE"
        }
        
        # Method 1: /proc/meminfo (most reliable)
        meminfo_lines = self._safe_read_lines('/proc/meminfo', max_lines=50)
        
        if meminfo_lines:
            for line in meminfo_lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    # Convert kB to human-readable
                    if 'kb' in value.lower():
                        try:
                            kb_value = int(value.split()[0])
                            human_readable = self._format_bytes(kb_value * 1024)
                            value = human_readable
                        except (ValueError, IndexError):
                            pass
                    
                    # Map memory info
                    if key == 'memtotal':
                        ram_info['total'] = value
                    elif key == 'memavailable':
                        ram_info['available'] = value
                    elif key == 'memfree':
                        ram_info['free'] = value
                    elif key == 'swaptotal':
                        ram_info['swap_total'] = value
                    elif key == 'swapfree':
                        ram_info['swap_free'] = value
                    elif key == 'buffers':
                        ram_info['buffers'] = value
                    elif key == 'cached':
                        ram_info['cached'] = value
            
            # Calculate used memory
            if ram_info['total'] != "NOT AVAILABLE" and ram_info['free'] != "NOT AVAILABLE":
                try:
                    total_bytes = self._parse_bytes(ram_info['total'])
                    free_bytes = self._parse_bytes(ram_info['free'])
                    used_bytes = total_bytes - free_bytes
                    ram_info['used'] = self._format_bytes(used_bytes)
                except (ValueError, TypeError):
                    pass
        
        # Method 2: free command (fallback)
        if ram_info['total'] == "NOT AVAILABLE":
            free_output = self._safe_command('free -h')
            if free_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                lines = free_output.split('\n')
                if len(lines) > 1:
                    # Parse second line (Mem:)
                    mem_line = lines[1].split()
                    if len(mem_line) >= 7:
                        ram_info['total'] = mem_line[1]
                        ram_info['used'] = mem_line[2]
                        ram_info['free'] = mem_line[3]
                        ram_info['available'] = mem_line[6] if len(mem_line) > 6 else "NOT AVAILABLE"
                
                # Parse swap line if exists
                if len(lines) > 2:
                    swap_line = lines[2].split()
                    if len(swap_line) >= 3:
                        ram_info['swap_total'] = swap_line[1]
                        ram_info['swap_free'] = swap_line[2]
        
        return ram_info
    
    def get_soc_info(self):
        """Collect System on Chip (SoC) information for ARM devices."""
        soc_info = {
            "status": "NOT AVAILABLE",
            "model": "NOT AVAILABLE",
            "manufacturer": "NOT AVAILABLE",
            "revision": "NOT AVAILABLE"
        }
        
        # Check if it's ARM architecture
        machine = platform.machine().lower()
        if 'arm' not in machine and 'aarch' not in machine:
            soc_info['status'] = "NOT APPLICABLE"
            return soc_info
        
        # Method 1: /proc/device-tree
        device_tree_model = self._safe_read_file('/proc/device-tree/model')
        if device_tree_model not in ["NOT AVAILABLE", "RESTRICTED"]:
            soc_info['status'] = "AVAILABLE"
            soc_info['model'] = device_tree_model.strip('\x00')
            soc_info['source'] = 'device-tree'
            return soc_info
        
        # Method 2: /proc/cpuinfo hardware field
        cpuinfo_lines = self._safe_read_lines('/proc/cpuinfo', max_lines=50)
        for line in cpuinfo_lines:
            if line.lower().startswith('hardware'):
                try:
                    hardware_value = line.split(':')[1].strip()
                    soc_info['status'] = "AVAILABLE"
                    soc_info['model'] = hardware_value
                    soc_info['source'] = 'cpuinfo'
                    return soc_info
                except IndexError:
                    pass
        
        # Method 3: Android properties for Termux
        if os.environ.get('TERMUX_VERSION'):
            board = self._safe_command('getprop ro.product.board')
            if board not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                soc_info['status'] = "AVAILABLE"
                soc_info['model'] = board
                soc_info['source'] = 'android-property'
                return soc_info
        
        return soc_info
    
    def get_device_info(self):
        """Collect device manufacturer and model information."""
        device_info = {
            "manufacturer": "NOT AVAILABLE",
            "model": "NOT AVAILABLE",
            "product": "NOT AVAILABLE"
        }
        
        # Method 1: DMI info (Linux)
        sys_vendor = self._safe_read_file('/sys/devices/virtual/dmi/id/sys_vendor')
        product_name = self._safe_read_file('/sys/devices/virtual/dmi/id/product_name')
        board_vendor = self._safe_read_file('/sys/devices/virtual/dmi/id/board_vendor')
        board_name = self._safe_read_file('/sys/devices/virtual/dmi/id/board_name')
        
        if sys_vendor not in ["NOT AVAILABLE", "RESTRICTED"]:
            device_info['manufacturer'] = sys_vendor
        if product_name not in ["NOT AVAILABLE", "RESTRICTED"]:
            device_info['model'] = product_name
        elif board_name not in ["NOT AVAILABLE", "RESTRICTED"]:
            device_info['model'] = board_name
        if board_vendor not in ["NOT AVAILABLE", "RESTRICTED"]:
            device_info['manufacturer'] = board_vendor
        
        # Method 2: Android properties for Termux
        if os.environ.get('TERMUX_VERSION'):
            manufacturer = self._safe_command('getprop ro.product.manufacturer')
            model = self._safe_command('getprop ro.product.model')
            product = self._safe_command('getprop ro.product.name')
            
            if manufacturer not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                device_info['manufacturer'] = manufacturer
            if model not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                device_info['model'] = model
            if product not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                device_info['product'] = product
        
        return device_info
    
    def _format_bytes(self, bytes_value):
        """Convert bytes to human-readable format."""
        try:
            bytes_value = float(bytes_value)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_value < 1024.0:
                    return f"{bytes_value:.1f} {unit}"
                bytes_value /= 1024.0
            return f"{bytes_value:.1f} PB"
        except (ValueError, TypeError):
            return "NOT AVAILABLE"
    
    def _parse_bytes(self, size_str):
        """Parse human-readable size string to bytes."""
        try:
            parts = size_str.split()
            value = float(parts[0])
            unit = parts[1].upper() if len(parts) > 1 else 'B'
            
            multipliers = {
                'B': 1,
                'KB': 1024,
                'MB': 1024**2,
                'GB': 1024**3,
                'TB': 1024**4
            }
            
            return int(value * multipliers.get(unit, 1))
        except (ValueError, IndexError):
            return 0
    
    def collect(self):
        """Collect all hardware information."""
        
        self.data = {
            "cpu": self.get_cpu_info(),
            "gpu": self.get_gpu_info(),
            "ram": self.get_ram_info(),
            "soc": self.get_soc_info(),
            "device": self.get_device_info(),
            "architecture": {
                "machine": platform.machine() or "NOT AVAILABLE",
                "processor": platform.processor() or "NOT AVAILABLE",
                "platform": platform.platform() or "NOT AVAILABLE"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return self.data
    
    def get_data(self):
        """Return collected data."""
        return self.data
    
    def print_summary(self):
        """Print a human-readable summary."""
        print("HARDWARE INFORMATION")
        print("-" * 40)
        
        cpu_info = self.data.get('cpu', {})
        ram_info = self.data.get('ram', {})
        gpu_info = self.data.get('gpu', {})
        soc_info = self.data.get('soc', {})
        device_info = self.data.get('device', {})
        
        print(f"CPU Model: {cpu_info.get('model', 'N/A')}")
        print(f"CPU Vendor: {cpu_info.get('vendor', 'N/A')}")
        print(f"CPU Cores: {cpu_info.get('cores', 'N/A')}")
        print(f"CPU Threads: {cpu_info.get('threads', 'N/A')}")
        print(f"CPU Frequency: {cpu_info.get('frequency_mhz', 'N/A')} MHz")
        
        if gpu_info.get('status') == "AVAILABLE":
            print(f"GPU: {gpu_info.get('model', 'N/A')}")
        else:
            print(f"GPU: {gpu_info.get('status', 'N/A')}")
        
        print(f"RAM Total: {ram_info.get('total', 'N/A')}")
        print(f"RAM Available: {ram_info.get('available', 'N/A')}")
        print(f"RAM Used: {ram_info.get('used', 'N/A')}")
        
        if soc_info.get('status') == "AVAILABLE":
            print(f"SoC: {soc_info.get('model', 'N/A')}")
        
        if device_info.get('manufacturer') != "NOT AVAILABLE":
            print(f"Manufacturer: {device_info.get('manufacturer', 'N/A')}")
        if device_info.get('model') != "NOT AVAILABLE":
            print(f"Device Model: {device_info.get('model', 'N/A')}")


# Standalone test
if __name__ == "__main__":
    hw_info = HardwareInfo()
    hw_info.collect()
    hw_info.print_summary()
    
    # Print JSON output
    import json
    print("\nJSON Output:")
    print(json.dumps(hw_info.get_data(), indent=2, default=str))
