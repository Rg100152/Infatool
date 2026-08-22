#!/usr/bin/env python3
"""
INFATOOL - Storage Information Module
Collects filesystem, mount points, disk usage, and storage type information.
"""

import os
import subprocess
import platform
from pathlib import Path
from datetime import datetime


class StorageInfo:
    """Collect storage-related information with graceful error handling."""
    
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
    
    def _safe_read_lines(self, filepath, max_lines=100):
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
    
    def _format_bytes(self, bytes_value):
        """Convert bytes to human-readable format."""
        try:
            bytes_value = float(bytes_value)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
                if bytes_value < 1024.0:
                    return f"{bytes_value:.1f} {unit}"
                bytes_value /= 1024.0
            return f"{bytes_value:.1f} EB"
        except (ValueError, TypeError):
            return "NOT AVAILABLE"
    
    def _parse_size_to_bytes(self, size_str):
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
                'TB': 1024**4,
                'PB': 1024**5
            }
            
            return int(value * multipliers.get(unit, 1))
        except (ValueError, IndexError):
            return 0
    
    def get_filesystem_info(self):
        """Collect filesystem information from /proc/filesystems."""
        filesystems = []
        
        lines = self._safe_read_lines('/proc/filesystems', max_lines=50)
        for line in lines:
            if line.strip() and not line.startswith('nodev'):
                filesystems.append(line.strip())
        
        # Also get nodev filesystems
        nodev_filesystems = []
        for line in lines:
            if line.startswith('nodev'):
                fs_name = line.replace('nodev', '').strip()
                if fs_name:
                    nodev_filesystems.append(fs_name)
        
        return {
            "supported": filesystems,
            "nodev_supported": nodev_filesystems,
            "count": len(filesystems)
        }
    
    def get_mount_points(self):
        """Collect mount point information."""
        mounts = []
        
        # Method 1: Parse /proc/mounts (most reliable)
        mount_lines = self._safe_read_lines('/proc/mounts', max_lines=100)
        
        for line in mount_lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    mount_info = {
                        'device': parts[0],
                        'mount_point': parts[1],
                        'filesystem': parts[2],
                        'options': parts[3].split(','),
                        'dump': parts[4] if len(parts) > 4 else '0',
                        'fsck': parts[5] if len(parts) > 5 else '0'
                    }
                    mounts.append(mount_info)
        
        # Method 2: Try mount command
        if not mounts:
            mount_output = self._safe_command('mount')
            if mount_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                for line in mount_output.split('\n'):
                    if line.strip() and ' on ' in line:
                        parts = line.split(' on ')
                        if len(parts) >= 2:
                            device = parts[0].strip()
                            rest = parts[1].split(' type ')
                            if len(rest) >= 2:
                                mount_point = rest[0].strip()
                                fs_and_options = rest[1].split(' (')
                                filesystem = fs_and_options[0].strip()
                                options = []
                                if len(fs_and_options) > 1:
                                    options = fs_and_options[1].replace(')', '').split(',')
                                
                                mounts.append({
                                    'device': device,
                                    'mount_point': mount_point,
                                    'filesystem': filesystem,
                                    'options': options,
                                    'dump': '0',
                                    'fsck': '0'
                                })
        
        return mounts
    
    def get_disk_usage(self):
        """Collect disk usage information for mount points."""
        disk_usage = []
        
        # Method 1: Use os.statvfs for each mount point
        mounts = self.get_mount_points()
        
        for mount in mounts:
            mount_point = mount.get('mount_point', '')
            if not mount_point:
                continue
            
            try:
                stat = os.statvfs(mount_point)
                
                total_bytes = stat.f_blocks * stat.f_frsize
                free_bytes = stat.f_bfree * stat.f_frsize
                available_bytes = stat.f_bavail * stat.f_frsize
                used_bytes = total_bytes - free_bytes
                
                if total_bytes > 0:
                    usage_percent = (used_bytes / total_bytes) * 100
                else:
                    usage_percent = 0
                
                disk_info = {
                    'mount_point': mount_point,
                    'filesystem': mount.get('filesystem', 'unknown'),
                    'device': mount.get('device', 'unknown'),
                    'total': self._format_bytes(total_bytes),
                    'total_bytes': total_bytes,
                    'used': self._format_bytes(used_bytes),
                    'used_bytes': used_bytes,
                    'free': self._format_bytes(free_bytes),
                    'free_bytes': free_bytes,
                    'available': self._format_bytes(available_bytes),
                    'available_bytes': available_bytes,
                    'usage_percent': round(usage_percent, 2)
                }
                
                disk_usage.append(disk_info)
                
            except (OSError, PermissionError):
                # Skip mount points we can't access
                continue
            except Exception:
                continue
        
        # Method 2: Try df command for additional info
        if not disk_usage:
            df_output = self._safe_command('df -h')
            if df_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                for line in df_output.split('\n')[1:]:  # Skip header
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 6:
                            try:
                                usage_percent = float(parts[4].replace('%', ''))
                            except ValueError:
                                usage_percent = 0
                            
                            disk_info = {
                                'mount_point': parts[5],
                                'filesystem': 'unknown',
                                'device': parts[0],
                                'total': parts[1],
                                'total_bytes': self._parse_size_to_bytes(parts[1]),
                                'used': parts[2],
                                'used_bytes': self._parse_size_to_bytes(parts[2]),
                                'free': parts[3],
                                'free_bytes': self._parse_size_to_bytes(parts[3]),
                                'available': parts[3],
                                'available_bytes': self._parse_size_to_bytes(parts[3]),
                                'usage_percent': usage_percent
                            }
                            
                            disk_usage.append(disk_info)
        
        return disk_usage
    
    def get_storage_type(self):
        """Determine storage type (SSD, HDD, eMMC, etc.)."""
        storage_type = {
            'status': 'NOT AVAILABLE',
            'type': 'NOT AVAILABLE',
            'rotational': 'NOT AVAILABLE',
            'model': 'NOT AVAILABLE'
        }
        
        # Method 1: Check /sys/block for device types
        try:
            if Path('/sys/block').exists():
                block_devices = os.listdir('/sys/block')
                
                for device in block_devices:
                    if device.startswith(('sd', 'mmc', 'nvme', 'vd')):
                        # Check rotational flag
                        rotational = self._safe_read_file(f'/sys/block/{device}/queue/rotational')
                        device_model = self._safe_read_file(f'/sys/block/{device}/device/model')
                        
                        if rotational == '0':
                            storage_type['rotational'] = 'NO'
                            if device.startswith('mmc'):
                                storage_type['type'] = 'eMMC/SD'
                            elif device.startswith('nvme'):
                                storage_type['type'] = 'NVMe SSD'
                            else:
                                storage_type['type'] = 'SSD'
                        elif rotational == '1':
                            storage_type['rotational'] = 'YES'
                            storage_type['type'] = 'HDD'
                        
                        if device_model not in ["NOT AVAILABLE", "RESTRICTED"]:
                            storage_type['model'] = device_model
                        
                        storage_type['status'] = 'AVAILABLE'
                        storage_type['device'] = device
                        break
        
        except (IOError, OSError):
            pass
        
        # Method 2: Android/Termux specific
        if storage_type['status'] == 'NOT AVAILABLE' and os.environ.get('TERMUX_VERSION'):
            # Android devices typically use eMMC or UFS
            storage_type['type'] = 'eMMC/UFS (Android)'
            storage_type['status'] = 'AVAILABLE'
            
            # Try to get more info
            for prop in ['ro.boot.hardware', 'ro.hardware']:
                value = self._safe_command(f'getprop {prop}')
                if value not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                    storage_type['model'] = value
                    break
        
        return storage_type
    
    def get_inode_info(self):
        """Collect inode usage information."""
        inode_info = []
        
        # Try df -i command
        df_inode_output = self._safe_command('df -i')
        if df_inode_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            for line in df_inode_output.split('\n')[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            inode_percent = float(parts[4].replace('%', ''))
                        except ValueError:
                            inode_percent = 0
                        
                        inode_info.append({
                            'mount_point': parts[5],
                            'inodes': parts[1],
                            'iused': parts[2],
                            'ifree': parts[3],
                            'iused_percent': inode_percent
                        })
        
        return inode_info
    
    def get_swap_info(self):
        """Collect swap space information."""
        swap_info = {
            'total': 'NOT AVAILABLE',
            'used': 'NOT AVAILABLE',
            'free': 'NOT AVAILABLE',
            'devices': []
        }
        
        # Method 1: Read /proc/swaps
        swap_lines = self._safe_read_lines('/proc/swaps', max_lines=20)
        
        for line in swap_lines[1:]:  # Skip header
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    swap_info['devices'].append({
                        'device': parts[0],
                        'type': parts[1],
                        'size': parts[2],
                        'used': parts[3],
                        'priority': parts[4] if len(parts) > 4 else '0'
                    })
        
        # Calculate totals
        total_swap = 0
        used_swap = 0
        for device in swap_info['devices']:
            try:
                total_swap += int(device['size'])
                used_swap += int(device['used'])
            except (ValueError, KeyError):
                pass
        
        if total_swap > 0:
            swap_info['total'] = self._format_bytes(total_swap * 1024)  # Convert from KB
            swap_info['used'] = self._format_bytes(used_swap * 1024)
            free_swap = total_swap - used_swap
            swap_info['free'] = self._format_bytes(free_swap * 1024)
        
        # Method 2: Try swapon command
        if not swap_info['devices']:
            swapon_output = self._safe_command('swapon --show')
            if swapon_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                swap_info['total'] = "AVAILABLE"
                swap_info['devices'] = swapon_output.split('\n')[1:]  # Skip header
        
        return swap_info
    
    def collect(self):
        """Collect all storage information."""
        
        disk_usage = self.get_disk_usage()
        total_storage = 0
        used_storage = 0
        
        for disk in disk_usage:
            total_storage += disk.get('total_bytes', 0)
            used_storage += disk.get('used_bytes', 0)
        
        self.data = {
            "filesystems": self.get_filesystem_info(),
            "mounts": self.get_mount_points(),
            "mount_count": len(self.get_mount_points()),
            "disk_usage": disk_usage,
            "storage_type": self.get_storage_type(),
            "inode_info": self.get_inode_info(),
            "swap": self.get_swap_info(),
            "summary": {
                "total_storage": self._format_bytes(total_storage),
                "total_storage_bytes": total_storage,
                "used_storage": self._format_bytes(used_storage),
                "used_storage_bytes": used_storage,
                "free_storage": self._format_bytes(total_storage - used_storage),
                "free_storage_bytes": total_storage - used_storage,
                "usage_percent": round((used_storage / total_storage * 100), 2) if total_storage > 0 else 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return self.data
    
    def get_data(self):
        """Return collected data."""
        return self.data
    
    def print_summary(self):
        """Print a human-readable summary."""
        print("STORAGE INFORMATION")
        print("-" * 40)
        
        # Storage type
        storage_type = self.data.get('storage_type', {})
        if storage_type.get('status') == 'AVAILABLE':
            print(f"Storage Type: {storage_type.get('type', 'N/A')}")
            if storage_type.get('model') != 'NOT AVAILABLE':
                print(f"Storage Model: {storage_type.get('model', 'N/A')}")
        
        # Summary
        summary = self.data.get('summary', {})
        print(f"\nTotal Storage: {summary.get('total_storage', 'N/A')}")
        print(f"Used Storage: {summary.get('used_storage', 'N/A')}")
        print(f"Free Storage: {summary.get('free_storage', 'N/A')}")
        print(f"Usage: {summary.get('usage_percent', 'N/A')}%")
        
        # Disk usage details
        print(f"\nMount Points:")
        disk_usage = self.data.get('disk_usage', [])
        for disk in disk_usage[:10]:  # Show first 10 mount points
            print(f"  {disk.get('mount_point', 'N/A')}: {disk.get('total', 'N/A')} total, {disk.get('used', 'N/A')} used, {disk.get('usage_percent', 'N/A')}%")
        
        # Swap
        swap = self.data.get('swap', {})
        if swap.get('total') != 'NOT AVAILABLE':
            print(f"\nSwap Total: {swap.get('total', 'N/A')}")
            print(f"Swap Used: {swap.get('used', 'N/A')}")
            print(f"Swap Free: {swap.get('free', 'N/A')}")


# Standalone test
if __name__ == "__main__":
    storage_info = StorageInfo()
    storage_info.collect()
    storage_info.print_summary()
    
    # Print JSON output
    import json
    print("\nJSON Output:")
    print(json.dumps(storage_info.get_data(), indent=2, default=str))
