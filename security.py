#!/usr/bin/env python3
"""
INFATOOL - Security Configuration Module
Collects defensive/local security information for system inventory.
"""

import os
import subprocess
import platform
import getpass
from pathlib import Path
from datetime import datetime


class SecurityInfo:
    """Collect security-related information with graceful error handling."""
    
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
    
    def check_root_status(self):
        """Check current root/sudo status."""
        root_info = {
            'is_root': False,
            'uid': 'NOT AVAILABLE',
            'gid': 'NOT AVAILABLE',
            'username': 'NOT AVAILABLE',
            'has_sudo': 'NOT AVAILABLE',
            'sudo_version': 'NOT AVAILABLE'
        }
        
        # Get user information
        try:
            root_info['username'] = getpass.getuser()
        except Exception:
            pass
        
        # Check UID/GID
        try:
            if hasattr(os, 'getuid'):
                root_info['uid'] = os.getuid()
                root_info['is_root'] = (os.getuid() == 0)
        except Exception:
            pass
        
        try:
            if hasattr(os, 'getgid'):
                root_info['gid'] = os.getgid()
        except Exception:
            pass
        
        # Check if sudo is available
        sudo_path = self._safe_command('which sudo')
        if sudo_path not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            root_info['has_sudo'] = 'YES'
            
            # Get sudo version
            sudo_version = self._safe_command('sudo --version 2>/dev/null | head -1')
            if sudo_version not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                root_info['sudo_version'] = sudo_version
        
        return root_info
    
    def check_selinux_status(self):
        """Check SELinux status if available."""
        selinux_info = {
            'status': 'NOT AVAILABLE',
            'enabled': 'NOT AVAILABLE',
            'mode': 'NOT AVAILABLE',
            'policy': 'NOT AVAILABLE'
        }
        
        # Method 1: Check /sys/fs/selinux
        if Path('/sys/fs/selinux').exists():
            selinux_info['enabled'] = 'YES'
            selinux_info['status'] = 'ENABLED'
            
            # Get enforcement mode
            enforce_file = self._safe_read_file('/sys/fs/selinux/enforce')
            if enforce_file == '1':
                selinux_info['mode'] = 'ENFORCING'
            elif enforce_file == '0':
                selinux_info['mode'] = 'PERMISSIVE'
            else:
                selinux_info['mode'] = 'UNKNOWN'
        
        # Method 2: Check /etc/selinux/config
        selinux_config = self._safe_read_file('/etc/selinux/config')
        if selinux_config not in ["NOT AVAILABLE", "RESTRICTED"]:
            for line in selinux_config.split('\n'):
                if line.startswith('SELINUX='):
                    selinux_info['mode'] = line.split('=')[1].strip()
                    selinux_info['status'] = 'CONFIGURED'
                elif line.startswith('SELINUXTYPE='):
                    selinux_info['policy'] = line.split('=')[1].strip()
        
        # Method 3: Try getenforce command
        if selinux_info['mode'] == 'NOT AVAILABLE':
            getenforce_output = self._safe_command('getenforce')
            if getenforce_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                selinux_info['mode'] = getenforce_output
                selinux_info['status'] = 'ENABLED'
                selinux_info['enabled'] = 'YES'
        
        # Method 4: Android/Termux SELinux
        if os.environ.get('TERMUX_VERSION'):
            # Android always has SELinux
            selinux_info['enabled'] = 'YES'
            selinux_info['status'] = 'ENABLED'
            
            # Try to get SELinux mode from Android properties
            selinux_mode = self._safe_command('getprop ro.build.selinux')
            if selinux_mode not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                selinux_info['mode'] = selinux_mode.upper()
            
            # Check if we can read /sys/fs/selinux/enforce
            enforce_file = self._safe_read_file('/sys/fs/selinux/enforce')
            if enforce_file == '1':
                selinux_info['mode'] = 'ENFORCING'
            elif enforce_file == '0':
                selinux_info['mode'] = 'PERMISSIVE'
        
        # If SELinux not found
        if selinux_info['status'] == 'NOT AVAILABLE':
            selinux_info['enabled'] = 'NO'
            selinux_info['status'] = 'NOT AVAILABLE'
            selinux_info['mode'] = 'DISABLED'
        
        return selinux_info
    
    def check_secure_boot(self):
        """Check Secure Boot status if available."""
        secure_boot_info = {
            'status': 'NOT AVAILABLE',
            'enabled': 'NOT AVAILABLE',
            'platform': 'NOT AVAILABLE'
        }
        
        # Method 1: Check /sys/firmware/efi (UEFI systems)
        if Path('/sys/firmware/efi').exists():
            secure_boot_info['platform'] = 'UEFI'
            
            # Try to read Secure Boot status
            secure_boot_file = self._safe_read_file('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c')
            
            if secure_boot_file not in ["NOT AVAILABLE", "RESTRICTED"]:
                # Parse the binary data (first byte indicates status)
                try:
                    if len(secure_boot_file) > 0:
                        status_byte = ord(secure_boot_file[0])
                        if status_byte == 1:
                            secure_boot_info['enabled'] = 'YES'
                            secure_boot_info['status'] = 'ENABLED'
                        elif status_byte == 0:
                            secure_boot_info['enabled'] = 'NO'
                            secure_boot_info['status'] = 'DISABLED'
                except (TypeError, IndexError):
                    pass
        
        # Method 2: Try mokutil command
        mokutil_output = self._safe_command('mokutil --sb-state')
        if mokutil_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            if 'SecureBoot enabled' in mokutil_output:
                secure_boot_info['enabled'] = 'YES'
                secure_boot_info['status'] = 'ENABLED'
            elif 'SecureBoot disabled' in mokutil_output:
                secure_boot_info['enabled'] = 'NO'
                secure_boot_info['status'] = 'DISABLED'
        
        # Method 3: Check bootctl (systemd-boot)
        bootctl_output = self._safe_command('bootctl status 2>/dev/null | grep "Secure Boot"')
        if bootctl_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            if 'enabled' in bootctl_output.lower():
                secure_boot_info['enabled'] = 'YES'
                secure_boot_info['status'] = 'ENABLED'
            elif 'disabled' in bootctl_output.lower():
                secure_boot_info['enabled'] = 'NO'
                secure_boot_info['status'] = 'DISABLED'
        
        # Android doesn't use Secure Boot in the traditional sense
        if os.environ.get('TERMUX_VERSION'):
            secure_boot_info['platform'] = 'ANDROID'
            secure_boot_info['status'] = 'NOT APPLICABLE'
            secure_boot_info['enabled'] = 'NOT APPLICABLE'
        
        return secure_boot_info
    
    def check_android_security(self):
        """Check Android-specific security properties."""
        android_security = {
            'status': 'NOT AVAILABLE',
            'selinux_mode': 'NOT AVAILABLE',
            'verified_boot': 'NOT AVAILABLE',
            'dm_verity': 'NOT AVAILABLE',
            'encryption': 'NOT AVAILABLE',
            'debug_mode': 'NOT AVAILABLE',
            'root_detected': 'NOT AVAILABLE',
            'bootloader_unlocked': 'NOT AVAILABLE'
        }
        
        if not os.environ.get('TERMUX_VERSION'):
            android_security['status'] = 'NOT APPLICABLE'
            return android_security
        
        android_security['status'] = 'AVAILABLE'
        
        # SELinux mode
        selinux_mode = self._safe_command('getprop ro.build.selinux')
        if selinux_mode not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            android_security['selinux_mode'] = selinux_mode.upper()
        
        # Verified Boot
        verified_boot = self._safe_command('getprop ro.boot.verifiedbootstate')
        if verified_boot not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            android_security['verified_boot'] = verified_boot
        
        # DM-Verity
        dm_verity = self._safe_command('getprop ro.boot.veritymode')
        if dm_verity not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            android_security['dm_verity'] = dm_verity
        
        # Encryption status
        encryption = self._safe_command('getprop ro.crypto.state')
        if encryption not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            android_security['encryption'] = encryption
        
        # Debug mode
        debug_mode = self._safe_command('getprop ro.debuggable')
        if debug_mode not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            android_security['debug_mode'] = 'ENABLED' if debug_mode == '1' else 'DISABLED'
        
        # Root detection
        root_detected = 'NO'
        su_paths = ['/system/bin/su', '/system/xbin/su', '/sbin/su', '/su/bin/su']
        for path in su_paths:
            if Path(path).exists():
                root_detected = 'YES'
                break
        
        if root_detected == 'NO':
            su_command = self._safe_command('which su 2>/dev/null')
            if su_command not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                root_detected = 'YES'
        
        android_security['root_detected'] = root_detected
        
        # Bootloader status
        bootloader = self._safe_command('getprop ro.boot.flash.locked')
        if bootloader not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            if bootloader == '0':
                android_security['bootloader_unlocked'] = 'YES'
            elif bootloader == '1':
                android_security['bootloader_unlocked'] = 'NO'
        
        return android_security
    
    def check_firewall_status(self):
        """Check firewall status if accessible."""
        firewall_info = {
            'status': 'NOT AVAILABLE',
            'type': 'NOT AVAILABLE',
            'rules': 'NOT AVAILABLE',
            'active': 'NOT AVAILABLE'
        }
        
        # Method 1: Check iptables
        iptables_output = self._safe_command('iptables -L -n 2>/dev/null | head -20')
        if iptables_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            firewall_info['type'] = 'iptables'
            firewall_info['status'] = 'AVAILABLE'
            
            # Check if there are any rules
            if 'Chain' in iptables_output and 'policy' in iptables_output.lower():
                firewall_info['active'] = 'YES'
                firewall_info['rules'] = iptables_output
            else:
                firewall_info['active'] = 'NO'
        
        # Method 2: Check nftables
        nftables_output = self._safe_command('nft list ruleset 2>/dev/null | head -20')
        if nftables_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            firewall_info['type'] = 'nftables'
            firewall_info['status'] = 'AVAILABLE'
            
            if nftables_output and len(nftables_output) > 0:
                firewall_info['active'] = 'YES'
                firewall_info['rules'] = nftables_output
            else:
                firewall_info['active'] = 'NO'
        
        # Method 3: Check ufw (Ubuntu Firewall)
        if firewall_info['status'] == 'NOT AVAILABLE':
            ufw_output = self._safe_command('ufw status 2>/dev/null')
            if ufw_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                firewall_info['type'] = 'ufw'
                firewall_info['status'] = 'AVAILABLE'
                firewall_info['rules'] = ufw_output
                
                if 'Status: active' in ufw_output:
                    firewall_info['active'] = 'YES'
                else:
                    firewall_info['active'] = 'NO'
        
        # Method 4: Check firewalld
        if firewall_info['status'] == 'NOT AVAILABLE':
            firewalld_output = self._safe_command('firewall-cmd --state 2>/dev/null')
            if firewalld_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                firewall_info['type'] = 'firewalld'
                firewall_info['status'] = 'AVAILABLE'
                firewall_info['active'] = firewalld_output.upper()
        
        return firewall_info
    
    def check_file_permissions(self):
        """Check important file permissions."""
        file_permissions = {
            'status': 'AVAILABLE',
            'files': []
        }
        
        # List of important files to check
        important_files = [
            '/etc/passwd',
            '/etc/shadow',
            '/etc/group',
            '/etc/sudoers',
            '/etc/ssh/sshd_config',
            '/etc/hosts',
            '/etc/resolv.conf'
        ]
        
        for filepath in important_files:
            try:
                path = Path(filepath)
                if path.exists():
                    stat = path.stat()
                    permissions = oct(stat.st_mode & 0o777)
                    owner_uid = stat.st_uid
                    owner_gid = stat.st_gid
                    
                    # Try to get owner names
                    owner = 'UNKNOWN'
                    group = 'UNKNOWN'
                    try:
                        import pwd
                        import grp
                        owner = pwd.getpwuid(owner_uid).pw_name
                        group = grp.getgrgid(owner_gid).gr_name
                    except (ImportError, KeyError):
                        pass
                    
                    file_permissions['files'].append({
                        'path': filepath,
                        'permissions': permissions,
                        'owner': owner,
                        'group': group
                    })
            except (OSError, PermissionError):
                file_permissions['files'].append({
                    'path': filepath,
                    'permissions': 'RESTRICTED',
                    'owner': 'RESTRICTED',
                    'group': 'RESTRICTED'
                })
        
        if not file_permissions['files']:
            file_permissions['status'] = 'NOT AVAILABLE'
        
        return file_permissions
    
    def check_debug_environment(self):
        """Check for debug/developer environment indicators."""
        debug_info = {
            'status': 'AVAILABLE',
            'python_debug': 'DISABLED',
            'developer_mode': 'NOT AVAILABLE',
            'debugging_tools': [],
            'environment_indicators': []
        }
        
        # Check Python debug mode
        if __debug__:
            debug_info['python_debug'] = 'ENABLED'
        
        # Check for common debugging tools
        debug_tools = ['gdb', 'strace', 'ltrace', 'valgrind', 'lldb']
        for tool in debug_tools:
            tool_path = self._safe_command(f'which {tool} 2>/dev/null')
            if tool_path not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                debug_info['debugging_tools'].append({
                    'tool': tool,
                    'path': tool_path
                })
        
        # Check environment variables for debug indicators
        debug_env_vars = ['DEBUG', 'PYTHONDEBUG', 'PYTHONINSPECT', 'PYTHONVERBOSE']
        for var in debug_env_vars:
            if os.environ.get(var):
                debug_info['environment_indicators'].append({
                    'variable': var,
                    'value': os.environ.get(var)
                })
        
        # Android developer mode
        if os.environ.get('TERMUX_VERSION'):
            dev_mode = self._safe_command('getprop ro.debuggable')
            if dev_mode not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                debug_info['developer_mode'] = 'ENABLED' if dev_mode == '1' else 'DISABLED'
        
        return debug_info
    
    def collect(self):
        """Collect all security information."""
        
        self.data = {
            "user": self.check_root_status(),
            "selinux": self.check_selinux_status(),
            "secure_boot": self.check_secure_boot(),
            "android_security": self.check_android_security(),
            "firewall": self.check_firewall_status(),
            "file_permissions": self.check_file_permissions(),
            "debug_environment": self.check_debug_environment(),
            "summary": {
                "root_status": "DETECTED" if self.check_root_status().get('is_root') else "NOT DETECTED",
                "selinux_status": self.check_selinux_status().get('mode', 'UNKNOWN'),
                "firewall_status": self.check_firewall_status().get('active', 'UNKNOWN'),
                "secure_boot": self.check_secure_boot().get('enabled', 'UNKNOWN')
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return self.data
    
    def get_data(self):
        """Return collected data."""
        return self.data
    
    def print_summary(self):
        """Print a human-readable summary."""
        print("SECURITY INFORMATION")
        print("-" * 40)
        
        # User/Root status
        user_info = self.data.get('user', {})
        print(f"User: {user_info.get('username', 'N/A')}")
        print(f"UID: {user_info.get('uid', 'N/A')}")
        print(f"Root: {'YES' if user_info.get('is_root') else 'NO'}")
        print(f"Sudo: {user_info.get('has_sudo', 'N/A')}")
        
        # SELinux
        selinux_info = self.data.get('selinux', {})
        print(f"\nSELinux: {selinux_info.get('status', 'N/A')}")
        print(f"SELinux Mode: {selinux_info.get('mode', 'N/A')}")
        
        # Secure Boot
        secure_boot = self.data.get('secure_boot', {})
        print(f"\nSecure Boot: {secure_boot.get('status', 'N/A')}")
        print(f"Secure Boot Enabled: {secure_boot.get('enabled', 'N/A')}")
        
        # Firewall
        firewall = self.data.get('firewall', {})
        print(f"\nFirewall: {firewall.get('status', 'N/A')}")
        print(f"Firewall Active: {firewall.get('active', 'N/A')}")
        
        # Android Security (if applicable)
        android_security = self.data.get('android_security', {})
        if android_security.get('status') == 'AVAILABLE':
            print(f"\nAndroid Security:")
            print(f"  SELinux: {android_security.get('selinux_mode', 'N/A')}")
            print(f"  Verified Boot: {android_security.get('verified_boot', 'N/A')}")
            print(f"  Encryption: {android_security.get('encryption', 'N/A')}")
            print(f"  Root Detected: {android_security.get('root_detected', 'N/A')}")
            print(f"  Debug Mode: {android_security.get('debug_mode', 'N/A')}")
        
        # Debug Environment
        debug_env = self.data.get('debug_environment', {})
        print(f"\nDebug Environment:")
        print(f"  Python Debug: {debug_env.get('python_debug', 'N/A')}")
        print(f"  Debug Tools: {len(debug_env.get('debugging_tools', []))}")
        
        # File Permissions
        file_perms = self.data.get('file_permissions', {})
        print(f"\nFile Permissions:")
        for file_info in file_perms.get('files', [])[:5]:  # Show first 5 files
            print(f"  {file_info.get('path', 'N/A')}: {file_info.get('permissions', 'N/A')}")


# Standalone test
if __name__ == "__main__":
    sec_info = SecurityInfo()
    sec_info.collect()
    sec_info.print_summary()
    
    # Print JSON output
    import json
    print("\nJSON Output:")
    print(json.dumps(sec_info.get_data(), indent=2, default=str))
