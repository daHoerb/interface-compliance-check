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

def generate_missing_config_files(results):
    config_dir = "missing_configs"
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    for host, result in results.items():
        if not result.failed:
            missing_config = []
            current_interface = None
            skip_mode = False
            current_interface_config = []
            
            for line in result.result.split('\n'):
                if "Skipped Interfaces" in line:
                    skip_mode = True
                    continue
                
                if not skip_mode:
                    if line.startswith("GigabitEthernet"):
                        # Speichere vorherige Interface-Konfiguration wenn vorhanden
                        if current_interface and current_interface_config:
                            missing_config.extend(["interface " + current_interface])
                            missing_config.extend(current_interface_config)
                            missing_config.append("!")
                        
                        current_interface = line.strip(':')
                        current_interface_config = []
                    elif line.startswith("Missing commands:"):
                        commands = line.split(":", 1)[1].strip().split(", ")
                        current_interface_config.extend([" " + cmd for cmd in commands])
                    elif line.startswith("Commands to remove:"):
                        commands = line.split(":", 1)[1].strip().split(", ")
                        current_interface_config.extend([" no " + cmd for cmd in commands])
            
            # Füge das letzte Interface hinzu, wenn es Konfigurationen hat
            if current_interface and current_interface_config:
                missing_config.extend(["interface " + current_interface])
                missing_config.extend(current_interface_config)
                missing_config.append("!")
            
            if missing_config:
                filename = os.path.join(config_dir, "{}_missing_config.txt".format(host))
                with open(filename, 'w') as f:
                    f.write("\n".join(missing_config))
    
    return config_dir


def generate_report(results, parsed_files, config_dir):
    now = datetime.datetime.now()
    report_filename = "compliance_report_{0}.html".format(now.strftime('%Y%m%d_%H%M%S'))
    
    html_content = """
    <html>
    <head>
        <title>Compliance Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background-color: #f2f2f2; }}
            .compliant {{ color: green; }}
            .non-compliant {{ color: red; }}
            .failed {{ color: orange; }}
        </style>
    </head>
    <body>
        <h1>Compliance Report - Generated on {0}</h1>
        <h2>Parsed Template Files:</h2>
        <ul>
    """.format(now.strftime('%Y-%m-%d %H:%M:%S'))

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

    for host, result in results.items():
        if result.failed:
            status = "FAILED"
            details = "Task failed: {0}".format(result)
            status_class = "failed"
        else:
            port_groups = defaultdict(list)
            skipped_ports = {}
            non_compliant_ports = []
            
            for line in result.result.split('\n'):
                if line.startswith("GigabitEthernet"):
                    current_port = line.strip(':')
                elif line.startswith("Description:"):
                    current_description = line.split(":", 1)[1].strip()
                elif line.startswith("Missing commands:"):
                    missing_commands = line
                    port_groups[missing_commands].append((current_port, current_description))
                    non_compliant_ports.append(current_port)
                elif "Skipped Interfaces" in line:
                    skipped_section = result.result.split("Skipped Interfaces")[1].strip().split('\n')
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

            details = "<h3>Non-Compliant Interfaces:</h3><ul>"
            for missing_commands, ports in port_groups.items():
                details += "<li>{0}<ul>".format(missing_commands)
                for port, description in ports:
                    details += "<li>{0} ({1})</li>".format(port, description)
                details += "</ul></li>"
            details += "</ul>"

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


def parse_interfaces(config):
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
    
    allowed_commands = [cmd for cmd in required_commands if not cmd.startswith('-')] + additional_allowed_commands
    remove_commands = [cmd[1:].strip() for cmd in required_commands if cmd.startswith('-')]
    
    config_lines = config.split('\n')
    found_commands = set()
    unexpected_commands = []
    commands_to_remove = []

    for line in config_lines:
        line = line.strip()
        if not line or line.startswith('interface'):
            continue
        
        if line in allowed_commands:
            found_commands.add(line)
        elif line in remove_commands:
            commands_to_remove.append(line)
        elif not any(line.startswith(allowed) for allowed in allowed_commands):
            unexpected_commands.append(line)
    
    missing_commands = set(cmd for cmd in required_commands if not cmd.startswith('-')) - found_commands

    if not missing_commands and not unexpected_commands and not commands_to_remove:
        return "Compliant"
    else:
        result = "Non-Compliant.\n"
        if missing_commands:
            result += "Missing commands: {}\n".format(", ".join(missing_commands))
        if unexpected_commands:
            result += "Unexpected commands: {}\n".format(", ".join(unexpected_commands))
        if commands_to_remove:
            result += "Commands to remove: {}\n".format(", ".join(commands_to_remove))
        return result.strip()

def check_switch_compliance(task, parsed_templates):
    host = str(task.host)
    print("Processing: {}".format(host))

    result = task.run(netmiko_send_command, command_string="show running-config")
    config = result[0].result

    print (config)

    interfaces = parse_interfaces(config)

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
                skipped_interfaces[interface] = description

    if not non_compliant_interfaces and not skipped_interfaces:
        return "All checked interfaces are compliant"
    else:
        result = ""
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
        
        return result.strip()

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
        nr.filter(lambda host: args.filter in host.name)
    
    print("Hosts in inventory:")
    for host in nr.inventory.hosts:
        print(f"- {host}")

    # Run the task
    results = nr.run(task=check_switch_compliance, parsed_templates=parsed_files)

    # Generate missing config files
    config_dir = os.path.join(args.output, "missing_configs")
    config_dir = generate_missing_config_files(results)

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
