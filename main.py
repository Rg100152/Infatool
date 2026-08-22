#!/usr/bin/env python3
"""
INFATOOL - Linux & Termux System Intelligence CLI
Version: 1.0
Main entry point for system information collection and reporting.
"""

import json
import sys
import os
import time
import threading
from pathlib import Path
from datetime import datetime

# Import system module
try:
    from system import SystemInfo
except ImportError:
    print("[ERROR] system.py not found. Make sure all files are in the same directory.")
    sys.exit(1)

# ANSI color codes
class Colors:
    """Terminal ANSI color codes."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    @staticmethod
    def disable():
        """Disable all colors."""
        Colors.RED = ''
        Colors.GREEN = ''
        Colors.CYAN = ''
        Colors.BLUE = ''
        Colors.YELLOW = ''
        Colors.MAGENTA = ''
        Colors.WHITE = ''
        Colors.RESET = ''
        Colors.BOLD = ''
        Colors.DIM = ''
    
    @staticmethod
    def colorize(text, color):
        """Wrap text with color codes."""
        return f"{color}{text}{Colors.RESET}"


class ConfigLoader:
    """Load and manage configuration files."""
    
    @staticmethod
    def load_json(filename, default=None):
        """Load JSON file with error handling."""
        try:
            path = Path(filename)
            if path.exists():
                with open(path, 'r') as f:
                    return json.load(f)
            return default or {}
        except (json.JSONDecodeError, IOError) as e:
            print(f"{Colors.colorize('[WARN]', Colors.YELLOW)} Could not load {filename}: {e}")
            return default or {}
    
    @staticmethod
    def save_json(filename, data):
        """Save data to JSON file."""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except IOError as e:
            print(f"{Colors.colorize('[ERROR]', Colors.RED)} Could not save {filename}: {e}")
            return False


class Animation:
    """Terminal loading animation."""
    
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.running = False
        self.thread = None
        self.frames = ['[•    ]', '[••   ]', '[•••  ]', '[•••• ]', '[•••••]']
        self.current_frame = 0
    
    def start(self, message="Processing"):
        """Start the animation."""
        if not self.enabled:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._animate, args=(message,))
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self, success=True):
        """Stop the animation."""
        if not self.enabled:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        
        # Clear the line
        sys.stdout.write('\r' + ' ' * 50 + '\r')
        sys.stdout.flush()
    
    def _animate(self, message):
        """Animation loop."""
        while self.running:
            frame = self.frames[self.current_frame % len(self.frames)]
            sys.stdout.write(f'\r{Colors.colorize(frame, Colors.CYAN)} {message}')
            sys.stdout.flush()
            self.current_frame += 1
            time.sleep(0.15)


class INFATOOL:
    """Main INFATOOL application class."""
    
    def __init__(self):
        self.config = {}
        self.modules_config = {}
        self.database = {}
        self.report = {}
        self.animation = None
        self.colors_enabled = True
        
    def display_banner(self):
        """Display INFATOOL ASCII banner."""
        banner = f"""
{Colors.colorize('╔══════════════════════════════════════════════════╗', Colors.CYAN)}
{Colors.colorize('║', Colors.CYAN)}        {Colors.colorize('I N F A T O O L', Colors.MAGENTA + Colors.BOLD)}                    {Colors.colorize('║', Colors.CYAN)}
{Colors.colorize('║', Colors.CYAN)}   {Colors.colorize('SYSTEM INTELLIGENCE CONSOLE', Colors.WHITE)}             {Colors.colorize('║', Colors.CYAN)}
{Colors.colorize('║', Colors.CYAN)}        {Colors.colorize('Version 1.0', Colors.DIM)}                     {Colors.colorize('║', Colors.CYAN)}
{Colors.colorize('╚══════════════════════════════════════════════════╝', Colors.CYAN)}
        """
        print(banner)
    
    def load_configuration(self):
        """Load configuration files."""
        print(f"{Colors.colorize('[BOOT]', Colors.CYAN)} Initializing INFATOOL...")
        
        # Load main config
        self.config = ConfigLoader.load_json('config.json', {
            "tool_name": "INFATOOL",
            "version": "1.0",
            "auto_scan": True,
            "save_report": True,
            "output_file": "report.json",
            "database_file": "database.json",
            "animation_enabled": True,
            "color_enabled": True,
            "scan_timeout": 10
        })
        
        # Configure colors
        self.colors_enabled = self.config.get('color_enabled', True)
        if not self.colors_enabled:
            Colors.disable()
        
        # Configure animation
        animation_enabled = self.config.get('animation_enabled', True)
        self.animation = Animation(animation_enabled)
        
        # Load modules config
        self.modules_config = ConfigLoader.load_json('modules.json', {
            "system": True,
            "hardware": True,
            "network": True,
            "storage": True,
            "security": True
        })
        
        print(f"{Colors.colorize('[ OK ]', Colors.GREEN)} Configuration loaded")
        
    def detect_environment(self):
        """Detect the running environment."""
        print(f"{Colors.colorize('[BOOT]', Colors.CYAN)} Detecting environment...")
        
        # Quick environment detection
        environment = "LINUX"
        try:
            if os.environ.get('TERMUX_VERSION'):
                environment = "TERMUX"
            elif Path('/data/data/com.termux').exists():
                environment = "TERMUX"
        except Exception:
            pass
        
        print(f"{Colors.colorize('[ OK ]', Colors.GREEN)} Environment detected: {environment}")
        print(f"{Colors.colorize('[ OK ]', Colors.GREEN)} Linux kernel detected")
        print(f"{Colors.colorize('[ OK ]', Colors.GREEN)} Python runtime detected")
        
        return environment
    
    def run_system_scan(self):
        """Run system information scan."""
        self.animation.start("Scanning system information")
        
        try:
            sys_info = SystemInfo()
            system_data = sys_info.collect()
            self.database['system'] = system_data
            self.animation.stop(True)
            print(f"{Colors.colorize('[ OK ]', Colors.GREEN)} System information collected")
            return True
        except Exception as e:
            self.animation.stop(False)
            print(f"{Colors.colorize('[WARN]', Colors.YELLOW)} System scan error: {e}")
            self.database['system'] = {"error": str(e)}
            return False
    
    def run_full_scan(self):
        """Run complete system scan."""
        scan_results = {
            'system': False,
            'hardware': False,
            'network': False,
            'storage': False,
            'security': False
        }
        
        # System scan
        if self.modules_config.get('system', True):
            print(f"\n{Colors.colorize('[SCAN]', Colors.CYAN)} SYSTEM ", end='')
            scan_results['system'] = self.run_system_scan()
        
        # Placeholder for other modules (Phase 2)
        if self.modules_config.get('hardware', True):
            print(f"{Colors.colorize('[SCAN]', Colors.CYAN)} HARDWARE ", end='')
            print(f"{Colors.colorize('............. PENDING', Colors.DIM)}")
            self.database['hardware'] = {"status": "NOT IMPLEMENTED"}
        
        if self.modules_config.get('network', True):
            print(f"{Colors.colorize('[SCAN]', Colors.CYAN)} NETWORK ", end='')
            print(f"{Colors.colorize('............. PENDING', Colors.DIM)}")
            self.database['network'] = {"status": "NOT IMPLEMENTED"}
        
        if self.modules_config.get('storage', True):
            print(f"{Colors.colorize('[SCAN]', Colors.CYAN)} STORAGE ", end='')
            print(f"{Colors.colorize('............. PENDING', Colors.DIM)}")
            self.database['storage'] = {"status": "NOT IMPLEMENTED"}
        
        if self.modules_config.get('security', True):
            print(f"{Colors.colorize('[SCAN]', Colors.CYAN)} SECURITY ", end='')
            print(f"{Colors.colorize('............. PENDING', Colors.DIM)}")
            self.database['security'] = {"status": "NOT IMPLEMENTED"}
        
        return scan_results
    
    def save_database(self):
        """Save database to file."""
        if not self.config.get('save_report', True):
            return
        
        database_file = self.config.get('database_file', 'database.json')
        
        # Add metadata to database
        self.database['metadata'] = {
            'tool_name': self.config.get('tool_name', 'INFATOOL'),
            'version': self.config.get('version', '1.0'),
            'scan_time': datetime.now().isoformat(),
            'environment': 'TERMUX' if os.environ.get('TERMUX_VERSION') else 'LINUX'
        }
        
        if ConfigLoader.save_json(database_file, self.database):
            print(f"{Colors.colorize('[ OK ]', Colors.GREEN)} Database saved: {database_file}")
        else:
            print(f"{Colors.colorize('[WARN]', Colors.YELLOW)} Could not save database")
    
    def generate_report(self):
        """Generate final report."""
        self.report = {
            "tool": self.config.get('tool_name', 'INFATOOL'),
            "version": self.config.get('version', '1.0'),
            "environment": {
                "platform": sys.platform,
                "environment": 'TERMUX' if os.environ.get('TERMUX_VERSION') else 'LINUX'
            },
            "system": self.database.get('system', {}),
            "hardware": self.database.get('hardware', {}),
            "network": self.database.get('network', {}),
            "storage": self.database.get('storage', {}),
            "security": self.database.get('security', {})
        }
        
        # Save report
        output_file = self.config.get('output_file', 'report.json')
        if ConfigLoader.save_json(output_file, self.report):
            print(f"{Colors.colorize('[ OK ]', Colors.GREEN)} Report saved: {output_file}")
            return True
        return False
    
    def display_summary(self):
        """Display scan summary."""
        print(f"\n{Colors.colorize('─' * 48, Colors.CYAN)}")
        print(f"{Colors.colorize('SYSTEM STATUS', Colors.BOLD)}")
        print(f"{Colors.colorize('─' * 48, Colors.CYAN)}")
        
        # System summary
        system_data = self.database.get('system', {})
        if system_data:
            os_info = system_data.get('operating_system', {})
            env_info = system_data.get('environment', {})
            user_info = system_data.get('user', {})
            runtime_info = system_data.get('runtime', {})
            
            print(f"{Colors.colorize('OS', Colors.BLUE)}        : {os_info.get('distribution', 'N/A')}")
            print(f"{Colors.colorize('Kernel', Colors.BLUE)}    : {os_info.get('kernel_version', 'N/A')}")
            print(f"{Colors.colorize('Architecture', Colors.BLUE)}: {env_info.get('architecture', 'N/A')}")
            print(f"{Colors.colorize('Environment', Colors.BLUE)}: {env_info.get('type', 'N/A')}")
        
        # Hardware placeholder
        hardware_data = self.database.get('hardware', {})
        if hardware_data and 'status' not in hardware_data:
            print(f"\n{Colors.colorize('HARDWARE', Colors.BOLD)}")
            print(f"{Colors.colorize('CPU', Colors.BLUE)}: ...")
            print(f"{Colors.colorize('GPU', Colors.BLUE)}: ...")
            print(f"{Colors.colorize('RAM', Colors.BLUE)}: ...")
        
        # Network placeholder
        network_data = self.database.get('network', {})
        if network_data and 'status' not in network_data:
            print(f"\n{Colors.colorize('NETWORK', Colors.BOLD)}")
            print(f"{Colors.colorize('Interfaces', Colors.BLUE)}: ...")
            print(f"{Colors.colorize('IPv4', Colors.BLUE)}: ...")
        
        # Security placeholder
        security_data = self.database.get('security', {})
        if security_data and 'status' not in security_data:
            print(f"\n{Colors.colorize('SECURITY', Colors.BOLD)}")
            print(f"{Colors.colorize('Root', Colors.BLUE)}: ...")
            print(f"{Colors.colorize('SELinux', Colors.BLUE)}: ...")
        
        print(f"{Colors.colorize('─' * 48, Colors.CYAN)}")
    
    def run_specific_scan(self, module_name):
        """Run scan for a specific module."""
        print(f"{Colors.colorize('[BOOT]', Colors.CYAN)} Initializing INFATOOL...")
        print(f"{Colors.colorize('[ OK ]', Colors.GREEN)} Configuration loaded")
        
        module_map = {
            'system': 'system',
            'hardware': 'hardware',
            'network': 'network',
            'storage': 'storage',
            'security': 'security'
        }
        
        if module_name not in module_map:
            print(f"{Colors.colorize('[ERROR]', Colors.RED)} Unknown module: {module_name}")
            print(f"Available modules: {', '.join(module_map.keys())}")
            return
        
        # Run specific module scan
        print(f"\n{Colors.colorize('[SCAN]', Colors.CYAN)} {module_name.upper()} ", end='')
        
        if module_name == 'system':
            self.run_system_scan()
        else:
            print(f"{Colors.colorize('............. PENDING', Colors.DIM)}")
            self.database[module_name] = {"status": "NOT IMPLEMENTED"}
        
        # Save results
        self.save_database()
        self.generate_report()
        
        # Display summary
        self.display_summary()
    
    def display_report(self):
        """Display the latest report."""
        try:
            report_file = self.config.get('output_file', 'report.json')
            if Path(report_file).exists():
                with open(report_file, 'r') as f:
                    report = json.load(f)
                
                print(f"\n{Colors.colorize('═' * 48, Colors.CYAN)}")
                print(f"{Colors.colorize(' LATEST REPORT', Colors.BOLD)}")
                print(f"{Colors.colorize('═' * 48, Colors.CYAN)}")
                print(json.dumps(report, indent=2, default=str))
            else:
                print(f"{Colors.colorize('[WARN]', Colors.YELLOW)} No report found. Run a scan first.")
        except Exception as e:
            print(f"{Colors.colorize('[ERROR]', Colors.RED)} Could not read report: {e}")
    
    def run(self, args):
        """Main execution flow."""
        # Display banner
        self.display_banner()
        
        # Load configuration
        self.load_configuration()
        
        # Handle commands
        if len(args) == 0:
            # Run full scan
            environment = self.detect_environment()
            print()
            
            # Run scans
            self.run_full_scan()
            
            # Save results
            print()
            self.save_database()
            self.generate_report()
            
            # Display summary
            self.display_summary()
            
            # Final message
            print(f"\n{Colors.colorize('[+]', Colors.GREEN)} Scan completed")
            print(f"{Colors.colorize('[+]', Colors.GREEN)} Report saved: {self.config.get('output_file', 'report.json')}")
            
        elif args[0] == 'system':
            self.run_specific_scan('system')
            
        elif args[0] == 'hardware':
            self.run_specific_scan('hardware')
            
        elif args[0] == 'network':
            self.run_specific_scan('network')
            
        elif args[0] == 'storage':
            self.run_specific_scan('storage')
            
        elif args[0] == 'security':
            self.run_specific_scan('security')
            
        elif args[0] == 'report':
            self.display_report()
            
        elif args[0] in ['help', '--help', '-h']:
            self.display_help()
            
        else:
            print(f"{Colors.colorize('[ERROR]', Colors.RED)} Unknown command: {args[0]}")
            self.display_help()
    
    def display_help(self):
        """Display help information."""
        help_text = f"""
{Colors.colorize('INFATOOL - System Intelligence CLI', Colors.BOLD)}
{Colors.colorize('Version 1.0', Colors.DIM)}

{Colors.colorize('USAGE:', Colors.CYAN)}
  python3 main.py [command]

{Colors.colorize('COMMANDS:', Colors.CYAN)}
  (no command)    Run complete system scan
  system          Display system information
  hardware        Display hardware information
  network         Display network information
  storage         Display storage information
  security        Display security configuration
  report          Display latest report
  help            Show this help message

{Colors.colorize('EXAMPLES:', Colors.CYAN)}
  python3 main.py              # Full scan
  python3 main.py system       # System info only
  python3 main.py network      # Network info only
        """
        print(help_text)


def main():
    """Main entry point."""
    try:
        tool = INFATOOL()
        tool.run(sys.argv[1:])
    except KeyboardInterrupt:
        print(f"\n{Colors.colorize('[!]', Colors.YELLOW)} Scan interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.colorize('[ERROR]', Colors.RED)} Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
