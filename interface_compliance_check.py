import argparse
from nornir import InitNornir
from nornir_netmiko import netmiko_send_command
from nornir_utils.plugins.functions import print_result
import re
import os
import datetime
from collections import defaultdict
from nornir import InitNornir
from nornir_netmiko import netmiko_send_command
from nornir_utils.plugins.functions import print_result
import re
import os
import datetime
from collections import defaultdict
import logging
import sys
import socks
import socket
import yaml

def initialize_nornir(config):
    """Initialize Nornir with configuration from config.yaml"""
    from nornir.core.inventory import Defaults, Inventory
    
    
    return InitNornir(
        runner={
            "plugin": "threaded",
            "options": {
                "num_workers": 100,
            },
        },
        inventory={
            "plugin": "SimpleInventory",
            "options": {
                "host_file": config["inventory"]["hosts_file"],
                "group_file": config["inventory"]["groups_file"],
                }
        },
        defaults={
            "username": config['auth']['username'],
            "password": config['auth']['password']
        }
        
    )

def load_config(config_file='config.yaml'):
    """Load configuration from YAML file with CLI override support"""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    return config

def validate_config(config):
    """Validate required configuration parameters"""
    required = {
        'auth': ['username', 'password'],
        'templates': ['dir'],
        'inventory': ['hosts_file', 'groups_file'],
        'connection': ['platform', 'timeout', 'session_timeout'],
        'output': ['dir']
    }
    
    for section, keys in required.items():
        if section not in config:
            print(f"Missing required section: {section}")
            sys.exit(1)
        
        for key in keys:
            if key not in config[section]:
                print(f"Missing required configuration: {section}.{key}")
                sys.exit(1)
            
            if not config[section][key] and section in ['auth']:
                print(f"Empty required value: {section}.{key}")
                sys.exit(1)
    
    return True

def find_matching_template(description, parsed_templates):
    if not description:
        return None
    
    # Exakte Übereinstimmung
    if description + '.txt' in parsed_templates:
        return parsed_templates[description + '.txt']
    
    # Teilübereinstimmung
    for template_name, template_content in parsed_templates.items():
        template_base = template_name.rsplit('.', 1)[0]  # Entfernt die .txt Endung
        if template_base in description:
            return template_content
    
    return None


def generate_report(results, parsed_files, config_dir):
    """Generate HTML report with compliance statistics and template details"""
    now = datetime.datetime.now()
    report_filename = "compliance_report_{0}.html".format(now.strftime('%Y%m%d_%H%M%S'))
    
    # Initialize statistics
    total_switches = len(results)
    compliant_switches = 0
    non_compliant_switches = 0
    failed_switches = 0
    total_interfaces = 0
    compliant_interfaces = 0
    non_compliant_interfaces = 0
    skipped_interfaces = 0
    
    # Collect statistics
    for host, multi_result in results.items():
        if multi_result.failed:
            failed_switches += 1
            continue
            
        # Get result from first task
        result = multi_result[0].result
        lines = result.split('\n')

        # Hosts status tracking
        has_non_compliant = False
        current_port = None
        host_interfaces = set()
        host_non_compliant = set()
        host_skipped = set()
        
        # Parse output line by line
        for line in lines:
            if line.startswith("GigabitEthernet"):
                current_port = line.strip(':')
                host_interfaces.add(current_port)
                total_interfaces += 1
            elif line == "Non-Compliant":
                if current_port:
                    has_non_compliant = True
                    host_non_compliant.add(current_port)
            elif "Missing commands:" in line or "Unexpected commands:" in line or "Commands to remove:" in line:
                has_non_compliant = True
            elif "Skipped Interfaces" in line:
                skipped_section = result.strip().split("Skipped Interfaces")[1].split('\n')
                for skip_line in skipped_section:
                    if ":" in skip_line:
                        port = skip_line.split(':')[0].strip()
                        if port.startswith("GigabitEthernet"):
                            host_skipped.add(port)
                            if port in host_interfaces:
                                host_interfaces.remove(port)

        # Update counters
        if has_non_compliant:
            non_compliant_switches += 1
        else:
            compliant_switches += 1
        skipped_interfaces += len(host_skipped)
        non_compliant_interfaces += len(host_non_compliant)
        compliant_interfaces += (len(host_interfaces) - len(host_non_compliant) - len(host_skipped))

    # Generate HTML report
    html_content = """
    <html>
    <head>
        <title>Compliance Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background-color: #f2f2f2; }}
            .compliant {{ color: green; }}
            .non-compliant {{ color: red; }}
            .failed {{ color: orange; }}
            .stats-container {{ 
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
            }}
            .stats-box {{
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 5px;
            }}
            .template-table {{
                margin-top: 20px;
            }}
            .template-table ul {{
                margin: 0;
                padding-left: 20px;
            }}
            .template-name {{
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <h1>Compliance Report - Generated on {0}</h1>
        
        <div class="stats-container">
            <div class="stats-box">
                <h2>Switch Statistics</h2>
                <table>
                    <tr><td>Total Switches:</td><td>{1}</td></tr>
                    <tr><td>Compliant Switches:</td><td class="compliant">{2}</td></tr>
                    <tr><td>Non-Compliant Switches:</td><td class="non-compliant">{3}</td></tr>
                    <tr><td>Failed Switches:</td><td class="failed">{4}</td></tr>
                </table>
            </div>
            
            <div class="stats-box">
                <h2>Interface Statistics</h2>
                <table>
                    <tr><td>Total Interfaces:</td><td>{5}</td></tr>
                    <tr><td>Compliant Interfaces:</td><td class="compliant">{6}</td></tr>
                    <tr><td>Non-Compliant Interfaces:</td><td class="non-compliant">{7}</td></tr>
                    <tr><td>Skipped Interfaces:</td><td>{8}</td></tr>
                </table>
            </div>
        </div>

        <h2>Template Details:</h2>
        <table class="template-table">
            <tr>
                <th>Template Name</th>
                <th>Required Commands</th>
                <th>Additional Allowed Commands</th>
            </tr>
    """.format(
        now.strftime('%Y-%m-%d %H:%M:%S'),
        total_switches,
        compliant_switches,
        non_compliant_switches,
        failed_switches,
        total_interfaces,
        compliant_interfaces,
        non_compliant_interfaces,
        skipped_interfaces
    )

    # Add template details
    for template_name, template_content in parsed_files.items():
        html_content += """
            <tr>
                <td class="template-name">{0}</td>
                <td><ul>{1}</ul></td>
                <td><ul>{2}</ul></td>
            </tr>
        """.format(
            template_name,
            "".join("<li>{}</li>".format(cmd) for cmd in template_content['required']),
            "".join("<li>{}</li>".format(cmd) for cmd in template_content['additional_allowed'])
        )

    html_content += """
        </table>

        <h2>Parsed Template Files:</h2>
        <ul>
    """

    for filename in parsed_files.keys():
        html_content += "<li>{0}</li>".format(filename)

    html_content += """
        </ul>
        <p>Missing configuration files are stored in: {0}</p>
        <h2>Host Results:</h2>
        <table>
            <tr>
                <th>Host</th>
                <th>Compliance Status</th>
                <th>Details</th>
            </tr>
    """.format(config_dir)

    # Add host results
    for host, multi_result in results.items():
        if multi_result.failed:
            status = "FAILED"
            details = "Task failed: {0}".format(multi_result)
            status_class = "failed"
        else:
            result = multi_result[0].result
            port_compliance = {}
            port_description = {}
            port_missing_commands = {}
            port_unexpected_commands = {}
            port_remove_commands = {}
            skipped_ports = {}
            non_compliant_ports = []
            current_port = None
            
            for line in result.split('\n'):
                if line.startswith("GigabitEthernet"):
                    current_port = line.strip(':')
                    port_compliance[current_port] = "Compliant"  # Default to compliant
                elif line.startswith("Description:"):
                    if current_port:
                        port_description[current_port] = line.split(":", 1)[1].strip()
                elif line == "Non-Compliant":
                    if current_port:
                        port_compliance[current_port] = "Non-Compliant"
                        non_compliant_ports.append(current_port)
                elif line.startswith("Missing commands:"):
                    if current_port:
                        missing_cmds = line.split(":", 1)[1].strip()
                        port_missing_commands[current_port] = missing_cmds
                        port_compliance[current_port] = "Non-Compliant"
                        non_compliant_ports.append(current_port)
                elif line.startswith("Unexpected commands:"):
                    if current_port:
                        unexpected_cmds = line.split(":", 1)[1].strip()
                        port_unexpected_commands[current_port] = unexpected_cmds
                        port_compliance[current_port] = "Non-Compliant"
                        non_compliant_ports.append(current_port)
                elif line.startswith("Commands to remove:"):
                    if current_port:
                        remove_cmds = line.split(":", 1)[1].strip()
                        port_remove_commands[current_port] = remove_cmds
                        port_compliance[current_port] = "Non-Compliant"
                        non_compliant_ports.append(current_port)
                elif "Skipped Interfaces" in line:
                    skipped_section = result.split("Skipped Interfaces")[1].strip().split('\n')
                    for skipped_line in skipped_section:
                        if ': ' in skipped_line:
                            port, desc = skipped_line.split(': ', 1)
                            skipped_ports[port.strip()] = desc.strip()
            
            if non_compliant_ports:
                status = "NON-COMPLIANT"
                status_class = "non-compliant"
            else:
                status = "COMPLIANT"
                status_class = "compliant"

            details = "<h3>Non-Compliant Interfaces:</h3>"
            if non_compliant_ports:
                details += "<ul>"
                for port in non_compliant_ports:
                    port_details = []
                    description = port_description.get(port, "No description")
                    details += f"<li><strong>{port}</strong> ({description})<ul>"
                    
                    if port in port_missing_commands:
                        details += f"<li>Missing commands: {port_missing_commands[port]}</li>"
                    
                    if port in port_unexpected_commands:
                        details += f"<li>Unexpected commands: {port_unexpected_commands[port]}</li>"
                    
                    if port in port_remove_commands:
                        details += f"<li>Commands to remove: {port_remove_commands[port]}</li>"
                    
                    details += "</ul></li>"
                details += "</ul>"
            else:
                details += "<p>All interfaces are compliant.</p>"

            if skipped_ports:
                details += "<h3>Skipped Interfaces:</h3><ul>"
                for port, description in skipped_ports.items():
                    details += "<li>{0}: {1}</li>".format(port, description)
                details += "</ul>"

        html_content += """
            <tr>
                <td>{0}</td>
                <td class="{1}">{2}</td>
                <td>{3}</td>
            </tr>
        """.format(host, status_class, status, details)

    html_content += """
        </table>
    </body>
    </html>
    """

    with open(report_filename, 'w') as report_file:
        report_file.write(html_content)
    
    return report_filename

def generate_missing_config_files(results, parsed_files):
    """Generate missing config files while preserving template command order"""
    config_dir = "missing_configs"
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    for host, multi_result in results.items():
        if not multi_result.failed:
            result = multi_result[0].result
            missing_config = []
            interfaces_data = {}
            current_interface = None
            skip_mode = False
            
            # First parse all interfaces and their data from results
            for line in result.split('\n'):
                if "Skipped Interfaces" in line:
                    skip_mode = True
                    continue
                
                if not skip_mode:
                    if line.startswith("GigabitEthernet"):
                        current_interface = line.strip(':')
                        interfaces_data[current_interface] = {
                            'description': None,
                            'missing_commands': [],
                            'remove_commands': [],
                            'unexpected_commands': []
                        }
                    elif line.startswith("Description:") and current_interface:
                        interfaces_data[current_interface]['description'] = line.split(":", 1)[1].strip()
                    elif line.startswith("Missing commands:") and current_interface:
                        commands = [cmd.strip() for cmd in line.split(":", 1)[1].strip().split(",")]
                        interfaces_data[current_interface]['missing_commands'] = commands
                    elif line.startswith("Commands to remove:") and current_interface:
                        commands = [cmd.strip() for cmd in line.split(":", 1)[1].strip().split(",")]
                        interfaces_data[current_interface]['remove_commands'] = commands
                    elif line.startswith("Unexpected commands:") and current_interface:
                        commands = [cmd.strip() for cmd in line.split(":", 1)[1].strip().split(",")]
                        interfaces_data[current_interface]['unexpected_commands'] = commands
            
            # Generate missing config for each interface
            for interface, data in interfaces_data.items():
                if not data['description']:
                    continue
                
                # Find matching template based on description
                matching_template = None
                template_content = None
                
                for template_name, content in parsed_files.items():
                    template_base = template_name.split('.')[0]
                    if template_base in data['description']:
                        matching_template = template_name
                        template_content = content
                        break
                
                # Skip if no matching template or no changes needed
                if not matching_template or not (data['missing_commands'] or data['remove_commands']):
                    continue
                
                # Start interface config block
                interface_config = [f"interface {interface}"]
                if data['description']:
                    interface_config.append(f" description {data['description']}")
                
                # Track which commands have been added/removed
                processed_missing = []
                processed_remove = []
                
                # Process commands in template order
                if template_content:
                    # First handle all commands in the original template order
                    for cmd in template_content['required']:
                        cmd_text = cmd.strip()
                        
                        if cmd_text.startswith('-'):  # Command to be removed
                            remove_cmd = cmd_text[1:].strip()
                            # Check if this command needs to be removed
                            for to_remove in data['remove_commands']:
                                if to_remove.strip() == remove_cmd:
                                    interface_config.append(f" no {remove_cmd}")
                                    processed_remove.append(to_remove)
                                    break
                        else:  # Regular command
                            # Check if this command is missing
                            for missing in data['missing_commands']:
                                if missing.strip() == cmd_text:
                                    interface_config.append(f" {cmd_text}")
                                    processed_missing.append(missing)
                                    break
                
                interface_config.append("!")
                missing_config.extend(interface_config)
            
            if missing_config:
                filename = os.path.join(config_dir, "{}_missing_config.txt".format(host))
                with open(filename, 'w') as f:
                    f.write("\n".join(missing_config))
    
    return config_dir

def check_interface_compliance(config, required_commands, additional_allowed_commands=None):
    """Check interface compliance with template requirements"""
    if additional_allowed_commands is None:
        additional_allowed_commands = []
    
    # Split the config into lines and clean
    config_lines = [line.strip() for line in config.split('\n') if line.strip()]
    
    # Process required commands
    standard_commands = []
    remove_commands = []
    
    for cmd in required_commands:
        cmd = cmd.strip()
        if cmd.startswith('-'):
            remove_commands.append(cmd[1:].strip())
        else:
            standard_commands.append(cmd)
    
    # Track compliance
    found_commands = set()
    unexpected_commands = []
    commands_to_remove = []
    
    # Check each config line against requirements
    for line in config_lines:
        if not line or line.startswith('interface'):
            continue
        
        # Check against standard commands
        matched_standard = False
        for cmd in standard_commands:
            if line == cmd:
                found_commands.add(cmd)
                matched_standard = True
                break
        
        # Check against additional allowed commands
        matched_allowed = False
        if not matched_standard:
            for cmd in additional_allowed_commands:
                if line == cmd:
                    matched_allowed = True
                    break
        
        # Check against commands to remove
        matched_remove = False
        for cmd in remove_commands:
            if line == cmd:
                commands_to_remove.append(cmd)
                matched_remove = True
                break
        
        # If not matched anywhere, it's unexpected
        if not (matched_standard or matched_allowed or matched_remove):
            unexpected_commands.append(line)
    
    # Identify missing commands
    missing_commands = set(standard_commands) - found_commands
    
    # Determine overall compliance
    is_compliant = not (missing_commands or commands_to_remove or unexpected_commands)
    
    if is_compliant:
        return "Compliant"
    else:
        result = ["Non-Compliant"]
        if missing_commands:
            result.append("Missing commands: {}".format(", ".join(missing_commands)))
        if unexpected_commands:
            result.append("Unexpected commands: {}".format(", ".join(unexpected_commands)))
        if commands_to_remove:
            result.append("Commands to remove: {}".format(", ".join(commands_to_remove)))
        return "\n".join(result)

def parse_intf_template_files_individually(directory_path):
    """Parse interface template files with improved handling of command formats"""
    result = {}
    errors = []

    try:
        for filename in os.listdir(directory_path):
            if filename.endswith('.txt'):
                file_path = os.path.join(directory_path, filename)
                try:
                    with open(file_path, 'r') as file:
                        required = []
                        additional_allowed = []
                        for line in file:
                            line = line.strip()
                            if not line or line.startswith('#'):
                                continue  # Skip empty lines and comments
                            elif line.startswith('+'):
                                additional_allowed.append(line[1:].strip())
                            else:
                                # Store the full line exactly as it appears
                                required.append(line)
                        
                        result[filename] = {
                            "required": required,
                            "additional_allowed": additional_allowed
                        }
                except IOError:
                    errors.append(f"Error reading file {filename}")

    except FileNotFoundError:
        errors.append(f"Directory {directory_path} not found.")
    except PermissionError:
        errors.append(f"Permission denied for directory {directory_path}.")

    return result, errors


def parse_interfaces(config):
    """Parse interface configurations from running config"""
    interfaces = {}
    current_interface = None
    
    for line in config.splitlines():
        line = line.strip()
        if line.lower().startswith('interface'):
            current_interface = line.split()[1]
            interfaces[current_interface] = {
                'config': [],
                'description': None
            }
        elif current_interface and line and not line.startswith('!'):
            if line.lower().startswith('description'):
                interfaces[current_interface]['description'] = line[11:].strip()
            else:
                interfaces[current_interface]['config'].append(line)
        elif line.startswith('!'):
            current_interface = None
    
    return interfaces


def parse_intf_template_files_individually(directory_path):
    result = {}
    errors = []

    try:
        for filename in os.listdir(directory_path):
            if filename.endswith('.txt'):
                file_path = os.path.join(directory_path, filename)
                try:
                    with open(file_path, 'r') as file:
                        required = []
                        additional_allowed = []
                        for line in file:
                            line = line.strip()
                            if line.startswith('#'):
                                continue  # Ignoriere Kommentarzeilen
                            elif line.startswith('+'):
                                additional_allowed.append(line[1:].strip())
                            elif line:
                                required.append(line)
                        
                        result[filename] = {
                            "required": required,
                            "additional_allowed": additional_allowed
                        }
                except IOError:
                    errors.append(f"Fehler beim Lesen der Datei {filename}")

    except FileNotFoundError:
        errors.append(f"Das Verzeichnis {directory_path} wurde nicht gefunden.")
    except PermissionError:
        errors.append(f"Keine Berechtigung, auf das Verzeichnis {directory_path} zuzugreifen.")

    return result, errors



    interfaces = {}
    current_interface = None
    
    for line in config.splitlines():
        line = line.strip()
        if line.lower().startswith('interface'):
            current_interface = line.split()[1]
            interfaces[current_interface] = {
                'config': [],
                'description': None
            }
        elif current_interface and line and not line.startswith('!'):
            if line.lower().startswith('description'):
                interfaces[current_interface]['description'] = line[11:].strip()
            else:
                interfaces[current_interface]['config'].append(line)
        elif line.startswith('!'):
            current_interface = None
    
    return interfaces

def check_interface_compliance(config, required_commands, additional_allowed_commands=None):
    if additional_allowed_commands is None:
        additional_allowed_commands = []
    
    # Separating commands into standard commands and commands that should be removed
    standard_commands = [cmd for cmd in required_commands if not cmd.startswith('-')]
    remove_commands = [cmd[1:].strip() for cmd in required_commands if cmd.startswith('-')]
    
    config_lines = config.split('\n')
    found_commands = set()
    unexpected_commands = []
    commands_to_remove = []

    for line in config_lines:
        line = line.strip()
        if not line or line.startswith('interface'):
            continue
        
        # Check for match with required commands
        matched_required = False
        for cmd in standard_commands:
            if line.startswith(cmd):
                found_commands.add(cmd)
                matched_required = True
                break
        
        # Check for match with additional allowed commands
        matched_allowed = False
        if not matched_required:
            for cmd in additional_allowed_commands:
                if line.startswith(cmd):
                    matched_allowed = True
                    break

        # Check for commands that should be removed
        matched_remove = False
        for cmd in remove_commands:
            if line.startswith(cmd):
                commands_to_remove.append(cmd)
                matched_remove = True
                break
        
        # If no match found, it's an unexpected command
        if not (matched_required or matched_allowed or matched_remove):
            unexpected_commands.append(line)
    
    # Find missing commands
    missing_commands = set(standard_commands) - found_commands

    is_compliant = not (missing_commands or commands_to_remove or unexpected_commands)
    
    if is_compliant:
        return "Compliant"
    else:
        result = ["Non-Compliant"]  # Start with Non-Compliant in first line
        if missing_commands:
            result.append("Missing commands: {}".format(", ".join(missing_commands)))
        if unexpected_commands:
            result.append("Unexpected commands: {}".format(", ".join(unexpected_commands)))
        if commands_to_remove:
            result.append("Commands to remove: {}".format(", ".join(commands_to_remove)))
        return "\n".join(result)


def check_switch_compliance(task, parsed_templates):
    """Check compliance for all interfaces on a switch"""
    host = str(task.host)
    print("Processing: {}".format(host))

    result = task.run(netmiko_send_command, command_string="show running-config")
    config = result[0].result

    interfaces = parse_interfaces(config)
    compliant_interfaces = {}
    non_compliant_interfaces = {}
    skipped_interfaces = {}

    for interface, intf_details in interfaces.items():
        if re.match(r'^GigabitEthernet', interface, re.IGNORECASE):
            description = intf_details['description']
            matching_template = find_matching_template(description, parsed_templates)
            
            if matching_template:
                required = matching_template['required']
                additional_allowed = matching_template['additional_allowed']

                config_str = "\n".join(intf_details['config'])
                compliance_result = check_interface_compliance(config_str, required, additional_allowed)
                if compliance_result != "Compliant":
                    non_compliant_interfaces[interface] = {
                        'compliance': compliance_result,
                        'description': description
                    }
                else:
                    compliant_interfaces[interface] = {
                        'compliance': "Compliant",
                        'description': description
                    }
            else:
                skipped_interfaces[interface] = description

    result = ""
    if compliant_interfaces:
        result += "Compliant Interfaces:\n"
        for interface, details in compliant_interfaces.items():
            result += "{}:\n".format(interface)
            if details['description']:
                result += "Description: {}\n".format(details['description'])
            result += "{}\n\n".format(details['compliance'])

    if non_compliant_interfaces:
        result += "Non-Compliant Interfaces:\n"
        for interface, details in non_compliant_interfaces.items():
            result += "{}:\n".format(interface)
            if details['description']:
                result += "Description: {}\n".format(details['description'])
            result += "{}\n\n".format(details['compliance'])
    
    if skipped_interfaces:
        result += "Skipped Interfaces (no matching template):\n"
        for interface, description in skipped_interfaces.items():
            result += "{}: {}\n".format(interface, description or "No description")
    
    return result.strip() if result else "No GigabitEthernet interfaces found"


def configure_proxy(host="127.0.0.1", port=1084, enabled=True):
    """Configure SOCKS5 proxy settings"""
    if enabled:
        try:
            socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, host, port)
            socket.socket = socks.socksocket
            print(f"Proxy configured successfully: {host}:{port}")
        except Exception as e:
            print(f"Error configuring proxy: {e}")
            return False
    return True


# Main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Interface Compliance Checker")

    # Required arguments
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to the configuration file (default: config.yaml)")
    parser.add_argument("-t", "--templates", default="interface_templates", help="Path to the interface templates directory (default: interface_templates)")
    parser.add_argument("-o", "--output", default=".", help="Directory to store output files (default: current directory)")

    #Optional arguments

    parser.add_argument("-f", "--filter", help="Optional filter string for hostname prefix")  

    # Optional SOCKS5 proxy settigs
    parser.add_argument("--proxy-enabled", action="store_true", help="Enable SOCKS5 proxy")
    parser.add_argument("--proxy-host", default="127.0.0.1", help="Proxy host (default: 127.0.0.1)")
    parser.add_argument("--proxy-port", type=int, default=1084, help="Proxy port (default: 1084)")
    
    # Parse arguments
    args = parser.parse_args()


    # Initialize nornir
    nr = InitNornir(config_file=args.config) 

    # Check proxy Settings
    if args.proxy_enabled:
        if not configure_proxy(args.proxy_host, args.proxy_port):
            print("Failed to configure proxy")
            sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Einlesen der Template-Dateien
    parsed_files, errors = parse_intf_template_files_individually(args.templates)

    if errors:
        print("\nAufgetretene Fehler beim Einlesen der Templates:")
        for error in errors:
            print(error)

    # Initialize Nornir
    #nr = InitNornir(config_file=args.config)
    
    # Apply host filter if specified
    
    if args.filter:
        nr = nr.filter(lambda host: args.filter in host.name)
        
    
    print("Hosts in inventory:")
    for host in nr.inventory.hosts:
        print(f"- {host}")

    # Run the task
    results = nr.run(task=check_switch_compliance, parsed_templates=parsed_files)

    # Generate missing config files
    config_dir = os.path.join(args.output, "missing_configs")
    config_dir = generate_missing_config_files(results, parsed_files)

    # Print the results
    failed_hosts = []
    for host, result in results.items():
        if result.failed:
            print(f"Task failed on host {host}: {result}")
            failed_hosts.append(host)
        else:
            print(f"\nResults for host {host}:")
            print(result.result)

    if failed_hosts:
        print("\nThe Task failed on the following Hosts:")
        print('--------------------------------------------')
        for host in failed_hosts:
            print(host)
    else:
        print("\nTask completed successfully on all hosts.")

    # Generate and save the report
    report_file = generate_report(results, parsed_files, config_dir)
    report_path = os.path.join(args.output, report_file)
    print(f"\nDetailed report saved to: {report_path}")
    print(f"Missing configuration files are stored in: {config_dir}")