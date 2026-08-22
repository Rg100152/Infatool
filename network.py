#!/usr/bin/env python3
"""
INFATOOL - Network Information Module
Collects network interfaces, IP addresses, routing, and DNS configuration.
"""

import os
import socket
import subprocess
import platform
from pathlib import Path
from datetime import datetime


class NetworkInfo:
    """Collect network-related information with graceful error handling."""
    
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
    
    def get_network_interfaces(self):
        """Collect network interface information."""
        interfaces = []
        
        # Method 1: Using socket and ioctl (Linux)
        try:
            import fcntl
            import struct
            
            # Get all interface names
            ifconfig_output = self._safe_command('ip addr show')
            if ifconfig_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                # Parse ip command output
                current_interface = None
                
                for line in ifconfig_output.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # New interface starts with number
                    if line[0].isdigit() and ':' in line:
                        if current_interface:
                            interfaces.append(current_interface)
                        
                        # Parse interface name
                        parts = line.split(':')
                        if len(parts) >= 2:
                            iface_name = parts[1].strip()
                            current_interface = {
                                'name': iface_name,
                                'type': 'unknown',
                                'status': 'DOWN',
                                'mac': 'NOT AVAILABLE',
                                'ipv4': [],
                                'ipv6': [],
                                'flags': []
                            }
                    
                    elif current_interface:
                        # Parse link/ether (MAC address)
                        if 'link/' in line:
                            link_parts = line.split()
                            if len(link_parts) >= 2:
                                current_interface['type'] = link_parts[1]
                                if len(link_parts) >= 3:
                                    current_interface['mac'] = link_parts[2]
                            
                            # Check if interface is UP
                            if 'UP' in line:
                                current_interface['status'] = 'UP'
                        
                        # Parse inet (IPv4)
                        elif 'inet ' in line:
                            inet_parts = line.split()
                            if len(inet_parts) >= 2:
                                ipv4_info = {
                                    'address': inet_parts[1],
                                    'netmask': 'NOT AVAILABLE',
                                    'broadcast': 'NOT AVAILABLE'
                                }
                                
                                # Extract netmask and broadcast
                                for part in inet_parts[2:]:
                                    if part.startswith('brd'):
                                        ipv4_info['broadcast'] = part.split(' ')[0]
                                
                                current_interface['ipv4'].append(ipv4_info)
                        
                        # Parse inet6 (IPv6)
                        elif 'inet6 ' in line:
                            inet6_parts = line.split()
                            if len(inet6_parts) >= 2:
                                ipv6_address = inet6_parts[1]
                                current_interface['ipv6'].append(ipv6_address)
                
                if current_interface:
                    interfaces.append(current_interface)
            
            else:
                # Fallback to ifconfig
                ifconfig_output = self._safe_command('ifconfig -a')
                if ifconfig_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                    interfaces = self._parse_ifconfig(ifconfig_output)
        
        except ImportError:
            # fcntl not available, try alternative methods
            ifconfig_output = self._safe_command('ifconfig -a')
            if ifconfig_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                interfaces = self._parse_ifconfig(ifconfig_output)
        
        # Method 2: /proc/net/dev (always available)
        if not interfaces:
            interfaces = self._parse_proc_net_dev()
        
        # Method 3: Python socket (last resort)
        if not interfaces:
            try:
                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
                interfaces.append({
                    'name': 'system',
                    'type': 'unknown',
                    'status': 'UP',
                    'mac': 'NOT AVAILABLE',
                    'ipv4': [{'address': ip_address, 'netmask': 'NOT AVAILABLE', 'broadcast': 'NOT AVAILABLE'}],
                    'ipv6': [],
                    'flags': []
                })
            except (socket.gaierror, socket.herror):
                pass
        
        return interfaces
    
    def _parse_ifconfig(self, output):
        """Parse ifconfig output."""
        interfaces = []
        current_interface = None
        
        for line in output.split('\n'):
            if not line.strip():
                continue
            
            # Check if this is a new interface
            if not line.startswith(' ') and not line.startswith('\t'):
                if current_interface:
                    interfaces.append(current_interface)
                
                # Parse interface name
                iface_name = line.split(':')[0].split()[0]
                current_interface = {
                    'name': iface_name,
                    'type': 'unknown',
                    'status': 'DOWN',
                    'mac': 'NOT AVAILABLE',
                    'ipv4': [],
                    'ipv6': [],
                    'flags': []
                }
                
                # Check flags
                if 'UP' in line:
                    current_interface['status'] = 'UP'
                
                # Extract flags
                if '<' in line and '>' in line:
                    flags_str = line[line.index('<')+1:line.index('>')]
                    current_interface['flags'] = flags_str.split(',')
            
            elif current_interface:
                # Parse details
                if 'HWaddr' in line or 'ether' in line:
                    mac_parts = line.split('HWaddr')
                    if len(mac_parts) > 1:
                        current_interface['mac'] = mac_parts[1].strip().split()[0]
                    else:
                        mac_parts = line.split('ether')
                        if len(mac_parts) > 1:
                            current_interface['mac'] = mac_parts[1].strip().split()[0]
                
                if 'inet addr:' in line:
                    inet_parts = line.split('inet addr:')
                    if len(inet_parts) > 1:
                        ipv4_info = {
                            'address': inet_parts[1].split()[0],
                            'netmask': 'NOT AVAILABLE',
                            'broadcast': 'NOT AVAILABLE'
                        }
                        
                        # Extract netmask
                        if 'Mask:' in line:
                            mask_parts = line.split('Mask:')
                            if len(mask_parts) > 1:
                                ipv4_info['netmask'] = mask_parts[1].split()[0]
                        
                        current_interface['ipv4'].append(ipv4_info)
                
                if 'inet6 addr:' in line:
                    inet6_parts = line.split('inet6 addr:')
                    if len(inet6_parts) > 1:
                        ipv6_address = inet6_parts[1].split('/')[0]
                        current_interface['ipv6'].append(ipv6_address)
        
        if current_interface:
            interfaces.append(current_interface)
        
        return interfaces
    
    def _parse_proc_net_dev(self):
        """Parse /proc/net/dev for interface information."""
        interfaces = []
        lines = self._safe_read_lines('/proc/net/dev', max_lines=50)
        
        for line in lines[2:]:  # Skip header lines
            if ':' in line:
                iface_name = line.split(':')[0].strip()
                interfaces.append({
                    'name': iface_name,
                    'type': 'unknown',
                    'status': 'UNKNOWN',
                    'mac': 'NOT AVAILABLE',
                    'ipv4': [],
                    'ipv6': [],
                    'flags': []
                })
        
        return interfaces
    
    def get_routing_info(self):
        """Collect routing table information."""
        routes = []
        
        # Method 1: ip route
        ip_route_output = self._safe_command('ip route show')
        if ip_route_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            for line in ip_route_output.split('\n'):
                if line.strip():
                    routes.append({
                        'type': 'route',
                        'destination': line.strip()
                    })
        
        # Method 2: /proc/net/route
        if not routes:
            route_lines = self._safe_read_lines('/proc/net/route', max_lines=50)
            
            for line in route_lines[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 11:
                        routes.append({
                            'interface': parts[0],
                            'destination': parts[1],
                            'gateway': parts[2],
                            'flags': parts[3],
                            'mask': parts[7]
                        })
        
        return routes
    
    def get_dns_info(self):
        """Collect DNS configuration."""
        dns_info = {
            'nameservers': [],
            'search_domains': [],
            'config_file': 'NOT AVAILABLE'
        }
        
        # Method 1: /etc/resolv.conf
        resolv_content = self._safe_read_file('/etc/resolv.conf')
        if resolv_content not in ["NOT AVAILABLE", "RESTRICTED"]:
            dns_info['config_file'] = '/etc/resolv.conf'
            
            for line in resolv_content.split('\n'):
                line = line.strip()
                if line.startswith('nameserver'):
                    dns_info['nameservers'].append(line.split()[1])
                elif line.startswith('search'):
                    dns_info['search_domains'].extend(line.split()[1:])
                elif line.startswith('domain'):
                    dns_info['search_domains'].append(line.split()[1])
        
        # Method 2: systemd-resolve (if available)
        if not dns_info['nameservers']:
            resolve_output = self._safe_command('systemd-resolve --status')
            if resolve_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                for line in resolve_output.split('\n'):
                    if 'DNS Servers:' in line:
                        dns_line = line.split('DNS Servers:')[1].strip()
                        dns_info['nameservers'].extend(dns_line.split())
        
        # Method 3: Android/Termux specific
        if not dns_info['nameservers'] and os.environ.get('TERMUX_VERSION'):
            # Try to get DNS from Android properties
            for prop in ['net.dns1', 'net.dns2']:
                dns_value = self._safe_command(f'getprop {prop}')
                if dns_value not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                    dns_info['nameservers'].append(dns_value)
        
        return dns_info
    
    def get_hostname_info(self):
        """Collect hostname information."""
        hostname_info = {
            'hostname': 'NOT AVAILABLE',
            'fqdn': 'NOT AVAILABLE',
            'ip_address': 'NOT AVAILABLE'
        }
        
        try:
            hostname_info['hostname'] = socket.gethostname()
        except socket.error:
            pass
        
        try:
            hostname_info['fqdn'] = socket.getfqdn()
        except socket.error:
            pass
        
        try:
            hostname_info['ip_address'] = socket.gethostbyname(hostname_info['hostname'])
        except (socket.error, socket.gaierror):
            # Try localhost
            try:
                hostname_info['ip_address'] = socket.gethostbyname('localhost')
            except socket.error:
                pass
        
        return hostname_info
    
    def get_listening_ports(self):
        """Collect listening ports information (local inventory only)."""
        listening_ports = []
        
        # Use ss command (modern replacement for netstat)
        ss_output = self._safe_command('ss -tuln')
        if ss_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            for line in ss_output.split('\n')[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 5:
                        listening_ports.append({
                            'protocol': parts[0],
                            'local_address': parts[4],
                            'state': 'LISTEN'
                        })
        
        # Fallback to netstat
        if not listening_ports:
            netstat_output = self._safe_command('netstat -tuln')
            if netstat_output not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
                for line in netstat_output.split('\n')[2:]:  # Skip headers
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 4:
                            listening_ports.append({
                                'protocol': parts[0],
                                'local_address': parts[3],
                                'state': 'LISTEN'
                            })
        
        return listening_ports
    
    def get_loopback_info(self):
        """Collect loopback interface information."""
        loopback_info = {
            'status': 'NOT AVAILABLE',
            'ipv4': '127.0.0.1',
            'ipv6': '::1'
        }
        
        # Check loopback interface
        lo_status = self._safe_command('ip addr show lo')
        if lo_status not in ["NOT AVAILABLE", "RESTRICTED", "TIMEOUT"]:
            loopback_info['status'] = 'UP' if 'UP' in lo_status else 'DOWN'
        
        return loopback_info
    
    def collect(self):
        """Collect all network information."""
        
        interfaces = self.get_network_interfaces()
        
        self.data = {
            "hostname": self.get_hostname_info(),
            "interfaces": interfaces,
            "interface_count": len(interfaces),
            "active_interfaces": sum(1 for i in interfaces if i.get('status') == 'UP'),
            "routing": self.get_routing_info(),
            "dns": self.get_dns_info(),
            "loopback": self.get_loopback_info(),
            "listening_ports": self.get_listening_ports(),
            "timestamp": datetime.now().isoformat()
        }
        
        return self.data
    
    def get_data(self):
        """Return collected data."""
        return self.data
    
    def print_summary(self):
        """Print a human-readable summary."""
        print("NETWORK INFORMATION")
        print("-" * 40)
        
        hostname_info = self.data.get('hostname', {})
        print(f"Hostname: {hostname_info.get('hostname', 'N/A')}")
        print(f"FQDN: {hostname_info.get('fqdn', 'N/A')}")
        print(f"Local IP: {hostname_info.get('ip_address', 'N/A')}")
        
        print(f"\nInterfaces: {self.data.get('interface_count', 0)}")
        print(f"Active: {self.data.get('active_interfaces', 0)}")
        
        interfaces = self.data.get('interfaces', [])
        for interface in interfaces:
            if interface.get('status') == 'UP':
                print(f"\n  {interface.get('name', 'N/A')} ({interface.get('status', 'N/A')})")
                print(f"    Type: {interface.get('type', 'N/A')}")
                print(f"    MAC: {interface.get('mac', 'N/A')}")
                
                ipv4_list = interface.get('ipv4', [])
                if ipv4_list:
                    for ipv4 in ipv4_list:
                        print(f"    IPv4: {ipv4.get('address', 'N/A')}")
                
                ipv6_list = interface.get('ipv6', [])
                if ipv6_list:
                    for ipv6 in ipv6_list[:2]:  # Show only first 2 IPv6 addresses
                        print(f"    IPv6: {ipv6}")
        
        dns_info = self.data.get('dns', {})
        nameservers = dns_info.get('nameservers', [])
        if nameservers:
            print(f"\nDNS Servers:")
            for ns in nameservers[:3]:  # Show first 3 nameservers
                print(f"  - {ns}")
        
        listening_ports = self.data.get('listening_ports', [])
        if listening_ports:
            print(f"\nListening Ports: {len(listening_ports)}")
            for port in listening_ports[:5]:  # Show first 5 ports
                print(f"  - {port.get('protocol', 'N/A')} {port.get('local_address', 'N/A')}")


# Standalone test
if __name__ == "__main__":
    net_info = NetworkInfo()
    net_info.collect()
    net_info.print_summary()
    
    # Print JSON output
    import json
    print("\nJSON Output:")
    print(json.dumps(net_info.get_data(), indent=2, default=str))
